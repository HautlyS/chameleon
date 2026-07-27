import dotenv from "dotenv";
import { resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
dotenv.config({ path: resolve(__dirname, "../.env") });

import express from "express";
import {
  scanJobs,
  listAnalyses,
  listTailoredCvs,
  renderCv,
  tailorCv,
  coverLetter,
  answerQuestion,
  scoreJob,
  ghostPdf,
  reviewCv,
  subscribeWhatsApp,
  unsubscribeWhatsApp,
} from "./bridge.js";

import { readFileSync } from "fs";
import { resolve } from "path";

import {
  sendButtonMenu,
  sendListMenu,
  formatTextMenu,
  MAIN_MENU,
  mainMenuAsButtons,
  mainMenuAsListSections,
  getButtonId,
  type MenuConfig,
} from "./menus.js";

import {
  loadOpenCodeConfig,
  checkHealth,
  sendPrompt,
  abortSession,
  clearSession,
  startEventSubscription,
  markBusy,
  markIdle,
  isBusy,
  getSession,
  type OpenCodeConfig,
} from "./opencode-client.js";

const PORT = parseInt(process.env.PORT || "3001", 10);
const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || "secret";

// ── Dual-mode control ────────────────────────────────────────────────
// OC_ENABLED=false → bridge-only mode (no SDK import attempted)
// OC_ENABLED=true (default) → try to connect OpenCode

const OC_ENABLED = process.env.OC_ENABLED !== "false";
let ocConfig: OpenCodeConfig | null = null;
let ocReady = false;
let ocSubscribed = false;

function getMenuConfig(): MenuConfig {
  return {
    apiBase: process.env.EVOLUTION_API_URL || "http://localhost:8080",
    apiKey: process.env.EVOLUTION_API_KEY || "",
    instanceName: process.env.WHATSAPP_INSTANCE_NAME || "chameleon",
  };
}

// ── SSE Event State ──────────────────────────────────────────────────

const responseBuffers = new Map<string, string>();
const pendingResolves = new Map<string, (text: string) => void>();

function handleOpenCodeEvent(event: Record<string, unknown>): void {
  const type = event.type as string | undefined;
  const sessionId = event.properties?.["session.id"] as string | undefined;

  if (!sessionId) return;

  if (type === "message.part.delta") {
    const delta = (event.properties?.["message.content.delta"] as string) || "";
    const current = responseBuffers.get(sessionId) || "";
    responseBuffers.set(sessionId, current + delta);
  } else if (type === "session.idle") {
    const text = responseBuffers.get(sessionId) || "";
    responseBuffers.delete(sessionId);
    markIdle();
    const resolve = pendingResolves.get(sessionId);
    if (resolve) {
      pendingResolves.delete(sessionId);
      resolve(text);
    }
  } else if (type === "session.error") {
    const errMsg = (event.properties?.["session.error.message"] as string) || "Unknown error";
    responseBuffers.delete(sessionId);
    markIdle();
    const resolve = pendingResolves.get(sessionId);
    if (resolve) {
      pendingResolves.delete(sessionId);
      resolve(`Error: ${errMsg}`);
    }
  } else if (type === "message.updated") {
    const text = (event.properties?.["message.content"] as string) || "";
    if (text) {
      responseBuffers.set(sessionId, text);
    }
  }
}

// ── Dynamic OpenCode health check ───────────────────────────────────

async function ensureOcReady(): Promise<boolean> {
  if (!OC_ENABLED || !ocConfig) return false;
  const healthy = await checkHealth(ocConfig);
  ocReady = healthy;
  return healthy;
}

// ── Express App ──────────────────────────────────────────────────────

const app = express();
app.use(express.json());

app.get("/health", async (_req, res) => {
  const healthy = OC_ENABLED ? await ensureOcReady() : false;
  res.json({
    status: "ok",
    service: "chameleon-whatsapp",
    mode: OC_ENABLED ? "hybrid" : "bridge-only",
    opencode: healthy ? "connected" : "disconnected",
  });
});

app.post("/webhook/evolution", async (req, res) => {
  const auth = req.headers["x-webhook-secret"];
  if (auth !== WEBHOOK_SECRET) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }

  const event = req.body;
  if (!event) {
    res.status(400).json({ error: "No event body" });
    return;
  }

  res.status(200).json({ received: true });

  try {
    await handleWebhookEvent(event);
  } catch (err) {
    console.error("[chameleon-whatsapp] Event handler error:", err);
  }
});

// ── Message Routing ──────────────────────────────────────────────────

async function handleWebhookEvent(event: Record<string, unknown>): Promise<void> {
  const data = event.data as Record<string, unknown> | undefined;
  if (!data) return;

  const key = data.key as Record<string, unknown> | undefined;
  const fromMe = key?.fromMe as boolean | undefined;
  const remoteJid = key?.remoteJid as string | undefined;

  if (fromMe || !remoteJid || remoteJid === "status@broadcast") return;

  const message = data.message as Record<string, unknown> | undefined;
  if (!message) return;

  // Extract text from all supported message types
  let rawText: string | undefined;

  if (typeof message.conversation === "string") {
    rawText = message.conversation;
  } else if (message.extendedTextMessage && typeof (message.extendedTextMessage as Record<string, unknown>)["text"] === "string") {
    rawText = (message.extendedTextMessage as Record<string, unknown>)["text"] as string;
  } else if (message.buttonsResponseMessage) {
    const btn = message.buttonsResponseMessage as Record<string, unknown>;
    rawText = (btn.selectedDisplayText as string) || (btn.selectedButtonId as string);
  } else if (message.listResponseMessage) {
    const list = message.listResponseMessage as Record<string, unknown>;
    const ssr = list.singleSelectReply as Record<string, unknown> | undefined;
    rawText = (ssr?.selectedRowId as string) || (list.title as string);
  }

  if (!rawText) return;

  const text = rawText.trim();
  const sender = remoteJid;
  const lower = text.toLowerCase();

  console.log(`[chameleon-whatsapp] Message from ${sender}: ${text}`);

  const hasOc = OC_ENABLED && ocConfig;

  // ── Help (adaptive) ───────────────────────────────────────────────
  if (lower === "/help" || lower === "/menu") {
    await sendWhatsAppMessage(sender, formatTextMenu("Chameleon Bot", MAIN_MENU, [
      hasOc
        ? "AI mode: OpenCode connected — send any message for AI assistant."
        : "Bridge mode: OpenCode not connected. Set OC_ENABLED=true for AI features.",
      "Tip: some WhatsApp clients also support interactive buttons below ⬇️",
    ]));

    // Try interactive menus in parallel (best-effort)
    const mc = getMenuConfig();
    await sendListMenu(sender, "Chameleon Bot", "Choose an action:", "Commands", mainMenuAsListSections(), mc)
      .catch(() => sendButtonMenu(sender, "Chameleon Bot", "Choose:", mainMenuAsButtons(), mc))
      .catch(() => { /* fallback already handled by text menu above */ });

    return;
  }

  // ── OpenCode-specific commands ────────────────────────────────────
  if (lower === "/new") {
    if (!hasOc) {
      await sendWhatsAppMessage(sender, "OpenCode is not connected. Cannot start a session.");
      return;
    }
    clearSession();
    await sendWhatsAppMessage(sender, "New session started.");
    return;
  }

  if (lower === "/abort") {
    if (!hasOc) {
      await sendWhatsAppMessage(sender, "OpenCode is not connected. Nothing to abort.");
      return;
    }
    if (isBusy()) {
      await abortSession(ocConfig);
      await sendWhatsAppMessage(sender, "Task aborted.");
    } else {
      await sendWhatsAppMessage(sender, "Nothing to abort.");
    }
    return;
  }

  if (lower === "/status") {
    const healthy = hasOc ? await checkHealth(ocConfig) : false;
    const session = getSession();
    await sendWhatsAppMessage(sender, [
      `Mode: ${OC_ENABLED ? "hybrid" : "bridge-only"}`,
      `OpenCode: ${healthy ? "connected" : "disconnected"}`,
      `Session: ${session?.id || "none"}`,
      `Busy: ${isBusy() ? "yes" : "no"}`,
    ].join("\n"));
    return;
  }

  // ── Bridge commands (always work) ─────────────────────────────────
  if (lower.startsWith("/scan")) {
    const query = text.replace(/^\/scan\s*/i, "").trim();
    await sendWhatsAppMessage(sender, "Scanning jobs...");
    try {
      const result = scanJobs(query || undefined);
      const jobs = JSON.parse(result) as Array<Record<string, unknown>>;
      if (jobs.length === 0) {
        await sendWhatsAppMessage(sender, "No jobs found.");
      } else {
        const lines = jobs.slice(0, 5).map((j) => `${j.title} @ ${j.company}\n${j.url || ""}`);
        await sendWhatsAppMessage(sender, `Found ${jobs.length} jobs:\n\n${lines.join("\n\n")}`);
      }
    } catch (err) {
      await sendWhatsAppMessage(sender, `Scan error: ${err}`);
    }
    return;
  }

  if (lower === "/analyses") {
    try {
      const result = listAnalyses();
      const analyses = JSON.parse(result) as Array<Record<string, unknown>>;
      if (analyses.length === 0) {
        await sendWhatsAppMessage(sender, "No saved analyses.");
      } else {
        const lines = analyses.slice(0, 5).map((a) => `${a.id} — ${a.company} / ${a.role}`);
        await sendWhatsAppMessage(sender, `Analyses:\n${lines.join("\n")}`);
      }
    } catch (err) {
      await sendWhatsAppMessage(sender, `Error: ${err}`);
    }
    return;
  }

  if (lower === "/cvs") {
    try {
      const result = listTailoredCvs();
      const cvs = JSON.parse(result) as Array<Record<string, unknown>>;
      if (cvs.length === 0) {
        await sendWhatsAppMessage(sender, "No tailored CVs.");
      } else {
        const lines = cvs.slice(0, 5).map((c) => `${c.title} @ ${c.company} — Score: ${c.score}`);
        await sendWhatsAppMessage(sender, `Tailored CVs:\n${lines.join("\n")}`);
      }
    } catch (err) {
      await sendWhatsAppMessage(sender, `Error: ${err}`);
    }
    return;
  }

  if (lower.startsWith("/render")) {
    const yamlPath = text.replace(/^\/render\s*/i, "").trim();
    if (!yamlPath) {
      await sendWhatsAppMessage(sender, "Usage: /render <yaml_path>");
      return;
    }
    await sendWhatsAppMessage(sender, "Rendering CV...");
    try {
      const result = renderCv(yamlPath);
      const parsed = JSON.parse(result) as Record<string, unknown>;
      if (parsed.success) {
        await sendWhatsAppMessage(sender, `PDF ready: ${parsed.pdf}`);
        // Try to send the PDF as media
        const pdfPath = parsed.pdf as string;
        if (pdfPath) {
          try {
            await sendWhatsAppMedia(sender, pdfPath);
          } catch {}
        }
      } else {
        await sendWhatsAppMessage(sender, `Render failed: ${parsed.error}`);
      }
    } catch (err) {
      await sendWhatsAppMessage(sender, `Render error: ${err}`);
    }
    return;
  }

  // ── Chameleon AI commands (bridge-first, fall back to OpenCode) ─────
  if (lower.startsWith("/chameleon")) {
    const args = text.replace(/^\/chameleon\s*/i, "").trim();
    await sendWhatsAppMessage(sender, "Running full tailor workflow...");
    try {
      const urlOrJd = args.split(" ")[0] || "";
      const result = tailorCv(urlOrJd);
      const parsed = JSON.parse(result) as Record<string, unknown>;
      if (parsed.success) {
        let reply = parsed.output as string || "CV tailored successfully.";
        const chunks = splitMessage(reply, 4000);
        for (const chunk of chunks) {
          await sendWhatsAppMessage(sender, chunk);
        }
      } else if (hasOc && await ensureOcReady()) {
        await sendWhatsAppMessage(sender, "Bridge tailor unavailable. Trying OpenCode...");
        await sendPrompt(ocConfig, text);
        markBusy();
        const reply = await waitForResponse(180_000);
        const chunks = splitMessage(reply || "(No response)", 4000);
        for (const chunk of chunks) await sendWhatsAppMessage(sender, chunk);
      } else {
        await sendWhatsAppMessage(sender, `Tailor failed: ${parsed.error}`);
      }
    } catch (err) {
      await sendWhatsAppMessage(sender, `Error: ${err}`);
    }
    return;
  }

  if (lower.startsWith("/cover-letter")) {
    const args = text.replace(/^\/cover-letter\s*/i, "").trim();
    await sendWhatsAppMessage(sender, "Generating cover letter...");
    try {
      const result = coverLetter(args);
      const parsed = JSON.parse(result) as Record<string, unknown>;
      if (parsed.success) {
        const chunks = splitMessage(parsed.cover_letter as string || "", 4000);
        for (const chunk of chunks) await sendWhatsAppMessage(sender, chunk);
      } else if (hasOc && await ensureOcReady()) {
        await sendWhatsAppMessage(sender, "Bridge cover letter unavailable. Trying OpenCode...");
        await sendPrompt(ocConfig, text);
        markBusy();
        const reply = await waitForResponse(180_000);
        const chunks = splitMessage(reply || "(No response)", 4000);
        for (const chunk of chunks) await sendWhatsAppMessage(sender, chunk);
      } else {
        await sendWhatsAppMessage(sender, `Cover letter failed: ${parsed.error}`);
      }
    } catch (err) {
      await sendWhatsAppMessage(sender, `Error: ${err}`);
    }
    return;
  }

  if (lower.startsWith("/question")) {
    const qText = text.replace(/^\/question\s*/i, "").trim();
    if (!qText) {
      await sendWhatsAppMessage(sender, "Usage: /question <your question> [--jd <job-description>]");
      return;
    }
    await sendWhatsAppMessage(sender, "Answering question...");
    try {
      const result = answerQuestion(qText);
      const parsed = JSON.parse(result) as Record<string, unknown>;
      if (parsed.success) {
        const chunks = splitMessage(parsed.answer as string || "", 4000);
        for (const chunk of chunks) await sendWhatsAppMessage(sender, chunk);
      } else if (hasOc && await ensureOcReady()) {
        await sendWhatsAppMessage(sender, "Bridge question unavailable. Trying OpenCode...");
        await sendPrompt(ocConfig, text);
        markBusy();
        const reply = await waitForResponse(180_000);
        const chunks = splitMessage(reply || "(No response)", 4000);
        for (const chunk of chunks) await sendWhatsAppMessage(sender, chunk);
      } else {
        await sendWhatsAppMessage(sender, `Question failed: ${parsed.error}`);
      }
    } catch (err) {
      await sendWhatsAppMessage(sender, `Error: ${err}`);
    }
    return;
  }

  if (lower.startsWith("/score")) {
    const analysisId = text.replace(/^\/score\s*/i, "").trim();
    if (!analysisId) {
      await sendWhatsAppMessage(sender, "Usage: /score <analysis-id>");
      return;
    }
    await sendWhatsAppMessage(sender, "Scoring CV...");
    try {
      const result = scoreJob(analysisId);
      const parsed = JSON.parse(result) as Record<string, unknown>;
      if (!parsed.error) {
        const chunks = splitMessage(JSON.stringify(parsed, null, 2), 4000);
        for (const chunk of chunks) await sendWhatsAppMessage(sender, chunk);
      } else {
        await sendWhatsAppMessage(sender, `Score error: ${parsed.error}`);
      }
    } catch (err) {
      await sendWhatsAppMessage(sender, `Error: ${err}`);
    }
    return;
  }

  // ── ATS Ghost / Review / Subscribe ──────────────────────────────────
  if (lower.startsWith("/ghost")) {
    const args = text.replace(/^\/ghost\s*/i, "").trim();
    const parts = args.split(/\s+/);
    const pdfPath = parts[0] || "";
    if (!pdfPath) {
      await sendWhatsAppMessage(sender, "Usage: /ghost <pdf_path> [jd_text]");
      return;
    }
    await sendWhatsAppMessage(sender, "Injecting ATS ghost text...");
    try {
      const result = ghostPdf(pdfPath, parts.slice(1).join(" ") || undefined);
      const parsed = JSON.parse(result) as Record<string, unknown>;
      if (parsed.success) {
        await sendWhatsAppMessage(sender, `ATS ghost injected: ${parsed.terms_injected} terms into ${pdfPath}`);
      } else {
        await sendWhatsAppMessage(sender, `Ghost failed: ${parsed.error}`);
      }
    } catch (err) {
      await sendWhatsAppMessage(sender, `Error: ${err}`);
    }
    return;
  }

  if (lower.startsWith("/review")) {
    const args = text.replace(/^\/review\s*/i, "").trim();
    const parts = args.match(/(["'])(?:(?!\1).)*\1|\S+/g) || [];
    const clean = parts.map((p) => p.replace(/^["']|["']$/g, ""));
    const yamlPath = clean[0] || "";
    const jdText = clean.slice(1).join(" ");
    if (!yamlPath || !jdText) {
      await sendWhatsAppMessage(sender, "Usage: /review <yaml_path> <jd_text>");
      return;
    }
    await sendWhatsAppMessage(sender, "Running double AI review...");
    try {
      const result = reviewCv(yamlPath, jdText);
      const parsed = JSON.parse(result) as Record<string, unknown>;
      const review = parsed.review as Record<string, unknown> || {};
      const score = review.overall_score || "?";
      const approved = parsed.approved ? "Yes" : "No";
      await sendWhatsAppMessage(sender, `Review: ${score}/100\nApproved: ${approved}`);
    } catch (err) {
      await sendWhatsAppMessage(sender, `Error: ${err}`);
    }
    return;
  }

  if (lower === "/subscribe") {
    await sendWhatsAppMessage(sender, "Subscribing you to RSS job alerts...");
    try {
      const result = subscribeWhatsApp(sender);
      await sendWhatsAppMessage(sender, `Subscribed! You'll receive RSS job alerts at ${sender}.`);
    } catch (err) {
      await sendWhatsAppMessage(sender, `Error: ${err}`);
    }
    return;
  }

  if (lower === "/unsubscribe") {
    await sendWhatsAppMessage(sender, "Unsubscribing from RSS job alerts...");
    try {
      const result = unsubscribeWhatsApp(sender);
      await sendWhatsAppMessage(sender, "Unsubscribed from RSS job alerts.");
    } catch (err) {
      await sendWhatsAppMessage(sender, `Error: ${err}`);
    }
    return;
  }

  // ── Everything else → OpenCode (if available) ────────────────────
  if (!hasOc) {
    await sendWhatsAppMessage(sender, [
      "OpenCode is not connected. I only understand these commands:",
      "/scan, /analyses, /cvs, /render, /help, /menu",
      "To enable AI features, set OC_ENABLED=true and configure OPENCODE_API_URL.",
    ].join("\n"));
    return;
  }

  const healthy = await ensureOcReady();
  if (!healthy) {
    await sendWhatsAppMessage(sender, "OpenCode server is not responding. Try again later.");
    return;
  }

  if (isBusy()) {
    await sendWhatsAppMessage(sender, "Still working on the previous task. Send /abort to stop it, or wait.");
    return;
  }

  try {
    await sendPrompt(ocConfig, text);
    markBusy();
    await sendWhatsAppMessage(sender, "Processing...");

    const reply = await waitForResponse(120_000);

    if (!reply || reply.trim() === "") {
      await sendWhatsAppMessage(sender, "(No response from OpenCode)");
    } else {
      const chunks = splitMessage(reply, 4000);
      for (const chunk of chunks) {
        await sendWhatsAppMessage(sender, chunk);
      }
    }
  } catch (err) {
    markIdle();
    await sendWhatsAppMessage(sender, `OpenCode error: ${err}`);
  }
}

// ── OpenCode Response Collector ──────────────────────────────────────

function waitForResponse(timeoutMs: number): Promise<string> {
  const session = getSession();
  if (!session) return Promise.resolve("No active session.");

  return new Promise<string>((resolve) => {
    const timer = setTimeout(() => {
      pendingResolves.delete(session.id);
      responseBuffers.delete(session.id);
      markIdle();
      resolve("(Timed out waiting for OpenCode response)");
    }, timeoutMs);

    pendingResolves.set(session.id, (text: string) => {
      clearTimeout(timer);
      resolve(text);
    });
  });
}

function splitMessage(text: string, maxLen: number): string[] {
  if (text.length <= maxLen) return [text];
  const chunks: string[] = [];
  let remaining = text;
  while (remaining.length > 0) {
    if (remaining.length <= maxLen) {
      chunks.push(remaining);
      break;
    }
    let breakAt = remaining.lastIndexOf("\n", maxLen);
    if (breakAt <= 0) breakAt = remaining.lastIndexOf(" ", maxLen);
    if (breakAt <= 0) breakAt = maxLen;
    chunks.push(remaining.slice(0, breakAt));
    remaining = remaining.slice(breakAt).trimStart();
  }
  return chunks;
}

// ── WhatsApp Sender ──────────────────────────────────────────────────

async function sendWhatsAppMedia(to: string, filePath: string): Promise<void> {
  const apiBase = process.env.EVOLUTION_API_URL || "http://localhost:8080";
  const apiKey = process.env.EVOLUTION_API_KEY || "";
  const instanceName = process.env.WHATSAPP_INSTANCE_NAME || "chameleon";

  try {
    const absPath = resolve(filePath);
    const fileData = readFileSync(absPath);
    const filename = filePath.split("/").pop() || filePath.split("\\").pop() || "cv.pdf";
    const boundary = "----ChameleonFormBoundary";
    const encoder = new TextEncoder();

    const parts: Uint8Array[] = [];
    const push = (s: string) => parts.push(encoder.encode(s));
    const pushBytes = (b: Uint8Array) => parts.push(b);

    push(`--${boundary}\r\n`);
    push(`Content-Disposition: form-data; name="number"\r\n\r\n`);
    push(`${to}\r\n`);
    push(`--${boundary}\r\n`);
    push(`Content-Disposition: form-data; name="mediatype"\r\n\r\n`);
    push(`document\r\n`);
    push(`--${boundary}\r\n`);
    push(`Content-Disposition: form-data; name="file"; filename="${filename}"\r\n`);
    push(`Content-Type: application/pdf\r\n\r\n`);
    pushBytes(fileData);
    push(`\r\n`);
    push(`--${boundary}--\r\n`);

    const body = new Blob(parts);
    const url = `${apiBase}/message/sendMedia/${instanceName}`;
    await fetch(url, {
      method: "POST",
      headers: { apikey: apiKey },
      body,
    });
  } catch (err) {
    console.error("[chameleon-whatsapp] Media send error:", err);
  }
}

async function sendWhatsAppMessage(to: string, text: string): Promise<void> {
  const apiBase = process.env.EVOLUTION_API_URL || "http://localhost:8080";
  const apiKey = process.env.EVOLUTION_API_KEY || "";
  const instanceName = process.env.WHATSAPP_INSTANCE_NAME || "chameleon";

  const url = `${apiBase}/message/sendText/${instanceName}`;
  const payload = { number: to, text };

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", apikey: apiKey },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      console.error(`[chameleon-whatsapp] Failed to send: ${resp.status}`);
    }
  } catch (err) {
    console.error("[chameleon-whatsapp] Send error:", err);
  }
}

// ── Bootstrap ────────────────────────────────────────────────────────

async function start(): Promise<void> {
  app.listen(PORT, () => {
    console.log(`[chameleon-whatsapp] Listening on port ${PORT}`);
    console.log(`[chameleon-whatsapp] Mode: ${OC_ENABLED ? "hybrid" : "bridge-only"}`);
  });

  if (OC_ENABLED) {
    ocConfig = loadOpenCodeConfig();
    console.log(`[chameleon-whatsapp] Connecting to OpenCode at ${ocConfig.apiUrl}...`);

    try {
      const healthy = await checkHealth(ocConfig);
      if (healthy) {
        ocReady = true;
        console.log("[chameleon-whatsapp] OpenCode connected.");
        const abortController = new AbortController();
        startEventSubscription(ocConfig, abortController.signal, handleOpenCodeEvent).catch((err) => {
          console.error("[chameleon-whatsapp] Event subscription failed:", err);
          ocReady = false;
        });
      } else {
        console.warn("[chameleon-whatsapp] OpenCode not reachable. Bridge-only mode.");
      }
    } catch (err) {
      console.warn("[chameleon-whatsapp] OpenCode SDK not available. Bridge-only mode.", err);
    }
  } else {
    console.log("[chameleon-whatsapp] OpenCode disabled via OC_ENABLED=false. Bridge-only mode.");
  }
}

start();
