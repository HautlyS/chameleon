import type { Bot, CommandContext, Context } from "grammy";
import { processUserPrompt } from "../handlers/prompt.js";
import { logger } from "../../utils/logger.js";

export interface ChameleonCommandDeps {
  bot: Bot<Context>;
  ensureEventSubscription: (directory: string) => Promise<void>;
}

/**
 * Shared handler for Chameleon workflow commands.
 * Strips the /command prefix and sends the rest to OpenCode as a prompt,
 * where the registered chameleon skills (opencode.json) handle the routing.
 */
export async function chameleonCommandHandler(
  ctx: CommandContext<Context>,
  deps: ChameleonCommandDeps,
): Promise<void> {
  const text = ctx.message?.text;
  if (!text) return;

  // Strip the leading /command (handles both /cmd and /cmd@botname)
  const rest = text.replace(/^\/\w+(?:@\w+)?\s*/, "").trim();

  // Build a prompt the chameleon skills can parse
  const prompt = rest ? text : text.split(/\s+/)[0];

  logger.info(`[Bot] Forwarding chameleon command: ${prompt}`);

  await processUserPrompt(ctx, prompt, {
    bot: deps.bot,
    ensureEventSubscription: deps.ensureEventSubscription,
  });
}
