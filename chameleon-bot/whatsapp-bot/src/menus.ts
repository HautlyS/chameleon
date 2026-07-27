// WhatsApp interactive menu system for Chameleon bot.
// Uses Evolution API interactive messages (buttons, lists, polls).
// Falls back to formatted text when interactive messages fail.

export interface Button {
  id: string;
  text: string;
}

export interface ListRow {
  id: string;
  title: string;
  description?: string;
}

export interface ListSection {
  title: string;
  rows: ListRow[];
}

export interface MenuConfig {
  apiBase: string;
  apiKey: string;
  instanceName: string;
}

// ── Evolution API endpoints ──────────────────────────────────────────

const ENDPOINTS = {
  buttons: (inst: string) => `/message/sendButtons/${inst}`,
  list: (inst: string) => `/message/sendList/${inst}`,
};

// ── Interactive Buttons ──────────────────────────────────────────────

export async function sendButtonMenu(
  sender: string,
  title: string,
  body: string,
  buttons: Button[],
  config: MenuConfig,
): Promise<boolean> {
  const url = `${config.apiBase}${ENDPOINTS.buttons(config.instanceName)}`;
  const payload = {
    number: sender,
    title,
    description: body,
    footer: "Chameleon Bot",
    buttons: buttons.map((b) => ({
      title: "reply",
      displayText: b.text,
      id: b.id,
    })),
  };

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", apikey: config.apiKey },
      body: JSON.stringify(payload),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

// ── Interactive List ─────────────────────────────────────────────────

export async function sendListMenu(
  sender: string,
  title: string,
  body: string,
  buttonText: string,
  sections: ListSection[],
  config: MenuConfig,
): Promise<boolean> {
  const url = `${config.apiBase}${ENDPOINTS.list(config.instanceName)}`;
  const payload = {
    number: sender,
    title,
    description: body,
    buttonText,
    footerText: "Chameleon Bot",
    values: sections.map((s) => ({
      title: s.title,
      rows: s.rows.map((r) => ({
        title: r.title,
        description: r.description || "",
        rowId: r.id,
      })),
    })),
  };

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", apikey: config.apiKey },
      body: JSON.stringify(payload),
    });
    return resp.ok;
  } catch {
    return false;
  }
}

// ── Text-based fallback menu ─────────────────────────────────────────
// Used when interactive messages fail (e.g., Evolution API v2.3.7 bug)

export function formatTextMenu(
  title: string,
  items: Array<{ command: string; label: string; description: string }>,
  extras?: string[],
): string {
  const lines = [
    `── ${title} ──`,
    "",
    ...items.map((item) => `${item.command} — ${item.label}`),
    "",
    ...(extras || []),
    "",
    "Type a command above to get started.",
  ];
  return lines.join("\n");
}

// ── Pre-built menus ──────────────────────────────────────────────────

export const MAIN_MENU: Array<{ command: string; label: string; description: string }> = [
  { command: "/scan <query>", label: "🔍 Search jobs across 17 platforms", description: "" },
  { command: "/analyses", label: "📊 List saved job analyses", description: "" },
  { command: "/cvs", label: "📄 List tailored CVs", description: "" },
  { command: "/render <path>", label: "🖨️ Render YAML to PDF", description: "" },
  { command: "/chameleon <url>", label: "🎯 Full tailor workflow", description: "" },
  { command: "/cover-letter <url>", label: "✉️ Generate cover letter", description: "" },
  { command: "/question <text>", label: "❓ Answer screening question", description: "" },
  { command: "/score <id>", label: "⭐ Score a tailored CV", description: "" },
  { command: "/ghost <pdf>", label: "👻 Inject ATS ghost text", description: "" },
  { command: "/review <yaml>", label: "🔬 Double AI review on CV", description: "" },
  { command: "/subscribe", label: "🔔 Subscribe to RSS alerts", description: "" },
  { command: "/unsubscribe", label: "🔕 Unsubscribe from RSS alerts", description: "" },
  { command: "/new", label: "🆕 New OpenCode session", description: "" },
  { command: "/abort", label: "⏹️ Abort current task", description: "" },
  { command: "/status", label: "📡 Connection status", description: "" },
  { command: "/menu", label: "📋 Show this menu", description: "" },
  { command: "/help", label: "ℹ️ Help & commands", description: "" },
];

export function mainMenuAsButtons(): Button[] {
  return [
    { id: "scan", text: "🔍 Scan Jobs" },
    { id: "analyses", text: "📊 Analyses" },
    { id: "cvs", text: "📄 CVs" },
    { id: "chameleon", text: "🎯 Tailor CV" },
    { id: "cover-letter", text: "✉️ Cover Letter" },
    { id: "status", text: "📡 Status" },
  ];
}

export function mainMenuAsListSections(): ListSection[] {
  return [
    {
      title: "Job Search",
      rows: [
        { id: "scan", title: "🔍 Scan Jobs", description: "Search across 17 platforms" },
        { id: "analyses", title: "📊 Analyses", description: "Saved job analyses" },
      ],
    },
    {
      title: "CV Management",
      rows: [
        { id: "cvs", title: "📄 Tailored CVs", description: "List your tailored CVs" },
        { id: "render", title: "🖨️ Render CV", description: "Render YAML to PDF" },
      ],
    },
    {
      title: "AI Workflows",
      rows: [
        { id: "chameleon", title: "🎯 Full Tailor", description: "JD → tailored CV" },
        { id: "cover-letter", title: "✉️ Cover Letter", description: "Generate a cover letter" },
        { id: "question", title: "❓ Question", description: "Answer screening Qs" },
        { id: "score", title: "⭐ Score CV", description: "Score against analysis" },
      ],
    },
    {
      title: "System",
      rows: [
        { id: "status", title: "📡 Status", description: "Connection health" },
        { id: "new-session", title: "🆕 New Session", description: "Reset OpenCode session" },
        { id: "abort", title: "⏹️ Abort", description: "Stop current task" },
      ],
    },
  ];
}

// ── Button response matchers ─────────────────────────────────────────

export function getButtonId(text: string): string | null {
  const lower = text.toLowerCase().trim();
  const map: Record<string, string> = {
    "🔍 scan jobs": "scan",
    "📊 analyses": "analyses",
    "📄 cvs": "cvs",
    "📄 tailored cvs": "cvs",
    "🖨️ render cv": "render",
    "🎯 tailor cv": "chameleon",
    "✉️ cover letter": "cover-letter",
    "❓ question": "question",
    "⭐ score cv": "score",
    "📡 status": "status",
    "🆕 new session": "new-session",
    "⏹️ abort": "abort",
  };
  return map[lower] || null;
}
