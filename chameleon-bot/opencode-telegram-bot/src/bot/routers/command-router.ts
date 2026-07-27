import type { Bot, Context, NextFunction } from "grammy";
import { InputFile } from "grammy";
import { config } from "../../config.js";
import { settingsCommand } from "../commands/settings-command.js";
import { opencodeStartCommand } from "../commands/opencode-start-command.js";
import { opencodeStopCommand } from "../commands/opencode-stop-command.js";
import { projectsCommand } from "../commands/projects-command.js";
import { worktreeCommand } from "../commands/worktree-command.js";
import { openCommand } from "../commands/open-command.js";
import { lsCommand } from "../commands/ls-command.js";
import { sessionsCommand } from "../commands/sessions-command.js";
import { messagesCommand } from "../commands/messages-command.js";
import { newCommand } from "../commands/new-command.js";
import { abortCommand } from "../commands/abort-command.js";
import { detachCommand } from "../commands/detach-command.js";
import { taskCommand } from "../commands/task-command.js";
import { taskListCommand } from "../commands/tasklist-command.js";
import { renameCommand } from "../commands/rename-command.js";
import { commandsCommand } from "../commands/command-catalog-command.js";
import { skillsCommand } from "../commands/skills-catalog-command.js";
import { mcpsCommand } from "../commands/mcp-catalog-command.js";
import { startCommand } from "../commands/start-command.js";
import { helpCommand } from "../commands/help-command.js";
import { statusCommand } from "../commands/status-command.js";
import {
  chameleonCommandHandler,
  type ChameleonCommandDeps,
} from "../commands/chameleon-commands.js";
import { BOT_COMMANDS } from "../commands/definitions.js";
import { logger } from "../../utils/logger.js";
import { flushPendingPrompt } from "../handlers/message-merger.js";
import { bridge } from "../../bridge/client.js";
import { existsSync } from "fs";
import { readFileSync } from "fs";
import path from "path";

interface CommandRouterDeps {
  ensureEventSubscription: (directory: string) => Promise<void>;
}

let commandsInitialized = false;

export async function ensureCommandsInitialized(ctx: Context, next: NextFunction): Promise<void> {
  if (commandsInitialized || !ctx.from || ctx.from.id !== config.telegram.allowedUserId) {
    await next();
    return;
  }

  if (!ctx.chat) {
    logger.warn("[Bot] Cannot initialize commands: chat context is missing");
    await next();
    return;
  }

  try {
    await ctx.api.setMyCommands(BOT_COMMANDS, {
      scope: {
        type: "chat",
        chat_id: ctx.chat.id,
      },
    });

    commandsInitialized = true;
    logger.debug(`[Bot] Commands initialized for authorized user (chat_id=${ctx.chat.id})`);
  } catch (err) {
    logger.error("[Bot] Failed to set commands:", err);
  }

  await next();
}

export function registerCommandRouter(bot: Bot<Context>, deps: CommandRouterDeps): void {
  bot.use(async (ctx, next) => {
    if (ctx.chat && ctx.message?.text?.startsWith("/")) {
      flushPendingPrompt(ctx.chat.id);
    }
    await next();
  });

  // Chameleon workflow commands — bridge-first for basic ops, OpenCode for AI
  const chameleonCtx: ChameleonCommandDeps = {
    bot,
    ensureEventSubscription: deps.ensureEventSubscription,
  };

  // Bridge-backed commands (work without OpenCode)
  bot.command("scan", async (ctx) => {
    const text = ctx.message?.text || "";
    const query = text.replace(/^\/scan\s*/i, "").trim();
    await ctx.reply("Scanning jobs...");
    const result = bridge.scanJobs(query);
    if (result.success && Array.isArray(result.data)) {
      const jobs = result.data as Array<Record<string, unknown>>;
      if (jobs.length === 0) {
        await ctx.reply("No jobs found.");
      } else {
        const lines = jobs.slice(0, 5).map((j) =>
          `• ${j.title} @ ${j.company}\n  ${j.url || ""}`
        );
        await ctx.reply(`Found ${jobs.length} jobs:\n\n${lines.join("\n\n")}`, { disable_web_page_preview: true });
      }
    } else {
      // Fall back to OpenCode
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  bot.command("analyses", async (ctx) => {
    const result = bridge.listAnalyses();
    if (result.success && Array.isArray(result.data)) {
      const analyses = result.data as Array<Record<string, string>>;
      if (analyses.length === 0) {
        await ctx.reply("No saved analyses.");
      } else {
        const lines = analyses.slice(0, 10).map((a) =>
          `• ${a.id} — ${a.company} / ${a.role}`
        );
        await ctx.reply(`Analyses:\n${lines.join("\n")}`);
      }
    } else {
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  bot.command("cvs", async (ctx) => {
    const result = bridge.listTailoredCvs();
    if (result.success && Array.isArray(result.data)) {
      const cvs = result.data as Array<Record<string, unknown>>;
      if (cvs.length === 0) {
        await ctx.reply("No tailored CVs.");
      } else {
        const lines = cvs.slice(0, 10).map((c) =>
          `• ${c.title} @ ${c.company} — Score: ${c.score}`
        );
        await ctx.reply(`Tailored CVs:\n${lines.join("\n")}`);
      }
    } else {
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  bot.command("render", async (ctx) => {
    const text = ctx.message?.text || "";
    const yamlPath = text.replace(/^\/render\s*/i, "").trim();
    if (!yamlPath) {
      await ctx.reply("Usage: /render <yaml_path>");
      return;
    }
    await ctx.reply("Rendering CV...");
    const result = bridge.renderCv(yamlPath);
    if (result.success) {
      const data = result.data as Record<string, unknown> || {};
      const pdfPath = data.pdf as string || "";
      if (pdfPath && existsSync(pdfPath)) {
        await ctx.replyWithDocument(new InputFile(readFileSync(pdfPath), path.basename(pdfPath)), {
          caption: `Rendered CV: ${path.basename(yamlPath)}`,
        });
      } else {
        await ctx.reply(`PDF ready: ${pdfPath || "(unknown path)"}`);
      }
    } else {
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  // Ghost — inject ATS text
  bot.command("ghost", async (ctx) => {
    const text = ctx.message?.text || "";
    const args = text.replace(/^\/ghost\s*/i, "").trim();
    const parts = args.split(/\s+/);
    const pdfPath = parts[0] || "";
    if (!pdfPath) {
      await ctx.reply("Usage: /ghost <pdf_path> [extra_terms]");
      return;
    }
    await ctx.reply("Injecting ATS ghost text...");
    const result = bridge.ghostPdf(pdfPath, undefined, parts.slice(1).join(" "));
    if (result.success) {
      const data = result.data as Record<string, unknown> || {};
      await ctx.reply(`ATS ghost injected: ${data.terms_injected} terms`);
    } else {
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  // Review — double AI review
  bot.command("review", async (ctx) => {
    const text = ctx.message?.text || "";
    const parts = text.replace(/^\/review\s*/i, "").trim().split(/\s+/);
    const yamlPath = parts[0] || "";
    if (!yamlPath || parts.length < 2) {
      await ctx.reply("Usage: /review <yaml_path> <jd_file>");
      return;
    }
    const jdFile = parts[1];
    await ctx.reply("Running double AI review...");
    const result = bridge.reviewCv(yamlPath, jdFile);
    if (result.success) {
      const data = result.data as Record<string, unknown> || {};
      const review = data.review as Record<string, unknown> || {};
      const score = review.overall_score || "?";
      const approved = data.approved ? "Yes" : "No";
      await ctx.reply(`Review score: ${score}/100\nApproved: ${approved}`);
    } else {
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  // AI-powered commands → OpenCode (no bridge equivalent)
  for (const cmd of ["chameleon", "cover_letter", "question", "score"]) {
    bot.command(cmd, (ctx) => chameleonCommandHandler(ctx, chameleonCtx));
  }

  bot.command("start", startCommand);
  bot.command("help", helpCommand);
  bot.command("status", statusCommand);
  bot.command("settings", settingsCommand);
  bot.command("opencode_start", opencodeStartCommand);
  bot.command("opencode_stop", opencodeStopCommand);
  bot.command("projects", projectsCommand);
  bot.command("worktree", worktreeCommand);
  bot.command("open", openCommand);
  bot.command("ls", lsCommand);
  bot.command("sessions", sessionsCommand);
  bot.command("messages", messagesCommand);
  bot.command("new", (ctx) => newCommand(ctx, { bot, ensureEventSubscription: deps.ensureEventSubscription }));
  bot.command("abort", abortCommand);
  bot.command("detach", detachCommand);
  bot.command("task", taskCommand);
  bot.command("tasklist", taskListCommand);
  bot.command("rename", renameCommand);
  bot.command("commands", commandsCommand);
  bot.command("skills", skillsCommand);
  bot.command("mcps", mcpsCommand);
}
