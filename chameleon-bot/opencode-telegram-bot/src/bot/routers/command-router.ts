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
import { writeFileSync, readFileSync, existsSync, mkdirSync } from "fs";
import { fileURLToPath } from "url";
import path from "path";

// ── Per-user routing mode (persisted to .chameleon/user_modes.json) ───
const MODES_FILE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../.chameleon/user_modes.json");
const userPreferOc = new Map<number, boolean>();

function loadModes(): void {
  try {
    if (existsSync(MODES_FILE)) {
      const data = JSON.parse(readFileSync(MODES_FILE, "utf-8")) as Record<string, boolean>;
      for (const [key, val] of Object.entries(data)) userPreferOc.set(Number(key), val);
    }
  } catch { /* ignore corrupt file */ }
}

function saveModes(): void {
  try {
    const dir = path.resolve(MODES_FILE, "..");
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    const obj: Record<string, boolean> = {};
    for (const [key, val] of userPreferOc) obj[String(key)] = val;
    writeFileSync(MODES_FILE, JSON.stringify(obj, null, 2));
  } catch { /* ignore write errors */ }
}

function setMode(chatId: number, useOc: boolean): void {
  userPreferOc.set(chatId, useOc);
  saveModes();
}

function preferOc(chatId: number): boolean {
  return userPreferOc.get(chatId) ?? false;
}

function getModeLabel(chatId: number): string {
  return preferOc(chatId) ? "OC-first" : "bridge-first";
}

loadModes();

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

  // ── Routing mode toggle ──────────────────────────────────────────
  bot.command("mode", async (ctx) => {
    const chatId = ctx.chat?.id;
    if (!chatId) return;
    const current = preferOc(chatId);
    const newMode = !current;
    // OC mode requires OpenCode to be running — we can't be sure here,
    // so just set it; bridge commands will fall through to chameleonCommandHandler
    setMode(chatId, newMode);
    await ctx.reply(
      `Routing mode: ${getModeLabel(chatId)}\n` +
      (newMode
        ? "All commands now go to OpenCode. No bridge used."
        : "Bridge commands use local Python; AI commands go to OpenCode.")
    );
  });

  // Chameleon workflow commands — bridge-first for basic ops, OpenCode for AI
  const chameleonCtx: ChameleonCommandDeps = {
    bot,
    ensureEventSubscription: deps.ensureEventSubscription,
  };

  // Bridge-backed commands (work without OpenCode, skip when OC-first)
  bot.command("scan", async (ctx) => {
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
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
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  bot.command("analyses", async (ctx) => {
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
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
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
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
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
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
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
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
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
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

  // ── AI-powered commands: bridge-first with OpenCode fallback ─────────
  bot.command("chameleon", async (ctx) => {
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
    const text = ctx.message?.text || "";
    const args = text.replace(/^\/chameleon\s*/i, "").trim();
    await ctx.reply("Running full tailor workflow...");
    const result = bridge.tailorCv(args.split(" ")[0] || "");
    if (result.success) {
      const data = result.data as Record<string, unknown> || {};
      await ctx.reply((data.output as string) || "CV tailored successfully.");
    } else {
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  bot.command("cover_letter", async (ctx) => {
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
    const text = ctx.message?.text || "";
    const args = text.replace(/^\/cover_letter\s*/i, "").trim();
    if (!args) {
      await ctx.reply("Usage: /cover_letter <job-description-text>");
      return;
    }
    await ctx.reply("Generating cover letter...");
    const result = bridge.coverLetter(args);
    if (result.success) {
      const data = result.data as Record<string, unknown> || {};
      await ctx.reply((data.cover_letter as string) || "Cover letter generated.");
    } else {
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  bot.command("question", async (ctx) => {
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
    const text = ctx.message?.text || "";
    const qText = text.replace(/^\/question\s*/i, "").trim();
    if (!qText) {
      await ctx.reply("Usage: /question <your question>");
      return;
    }
    await ctx.reply("Answering question...");
    const result = bridge.answerQuestion(qText);
    if (result.success) {
      const data = result.data as Record<string, unknown> || {};
      await ctx.reply((data.answer as string) || "Question answered.");
    } else {
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  bot.command("score", async (ctx) => {
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
    const text = ctx.message?.text || "";
    const analysisId = text.replace(/^\/score\s*/i, "").trim();
    if (!analysisId) {
      await ctx.reply("Usage: /score <analysis-id>");
      return;
    }
    await ctx.reply("Scoring CV...");
    const result = bridge.scoreJob(analysisId);
    if (result.success) {
      const data = result.data as Record<string, unknown> || {};
      const score = data.score ?? data.overall_score ?? "?";
      await ctx.reply(`Score: ${score}/100\n\n${JSON.stringify(data, null, 2)}`);
    } else {
      await chameleonCommandHandler(ctx, chameleonCtx);
    }
  });

  // ── Subscribe / Unsubscribe for job alerts ──────────────────────────
  bot.command("subscribe", async (ctx) => {
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
    const chatId = ctx.chat?.id;
    if (!chatId) return;
    await ctx.reply("Subscribing to RSS job alerts...");
    const result = bridge.subscribe(String(chatId), "telegram");
    if (result.success) {
      await ctx.reply("Subscribed! You'll receive RSS job alerts here.");
    } else {
      await ctx.reply(`Subscription failed: ${result.error}`);
    }
  });

  bot.command("unsubscribe", async (ctx) => {
    if (preferOc(ctx.chat?.id ?? 0)) { await chameleonCommandHandler(ctx, chameleonCtx); return; }
    const chatId = ctx.chat?.id;
    if (!chatId) return;
    const result = bridge.unsubscribe(String(chatId), "telegram");
    if (result.success) {
      await ctx.reply("Unsubscribed from RSS job alerts.");
    } else {
      await ctx.reply(`Unsubscription failed: ${result.error}`);
    }
  });

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
