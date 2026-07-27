// WhatsApp interactive menu system for Chameleon bot.
// Uses Evolution API interactive messages (buttons, lists).
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
      title: "reply" as const,
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

interface MenuItem {
  command: string;
  label: string;
}

export function formatTextMenu(
  title: string,
  items: MenuItem[],
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

export const MAIN_MENU: MenuItem[] = [
  { command: "/scan <query>", label: "🔍 Search jobs across 17 platforms" },
  { command: "/analyses", label: "📊 List saved job analyses" },
  { command: "/cvs", label: "📄 List tailored CVs" },
  { command: "/render <path>", label: "🖨️ Render YAML to PDF" },
  { command: "/chameleon <url>", label: "🎯 Full tailor workflow" },
  { command: "/cover-letter <url>", label: "✉️ Generate cover letter" },
  { command: "/question <text>", label: "❓ Answer screening question" },
  { command: "/score <id>", label: "⭐ Score a tailored CV" },
  { command: "/new", label: "🆕 New OpenCode session" },
  { command: "/abort", label: "⏹️ Abort current task" },
  { command: "/mode", label: "🔄 Toggle bridge-first / OC-first routing" },
  { command: "/ghost <path>", label: "👻 Inject ATS ghost text into PDF" },
  { command: "/review <yaml> <jd>", label: "🔍 Double AI review of CV" },
  { command: "/subscribe", label: "🔔 Subscribe to RSS job alerts" },
  { command: "/unsubscribe", label: "🔕 Unsubscribe from job alerts" },
  { command: "/status", label: "📡 Connection status" },
  { command: "/menu", label: "📋 Show this menu" },
  { command: "/help", label: "ℹ️ Help & commands" },
];

export function mainMenuAsButtons(): Button[] {
  return [
    { id: "scan", text: "🔍 Scan Jobs" },
    { id: "analyses", text: "📊 Analyses" },
    { id: "chameleon", text: "🎯 Tailor CV" },
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
      title: "ATS & Alerts",
      rows: [
        { id: "ghost", title: "👻 Ghost PDF", description: "Inject ATS ghost text" },
        { id: "review", title: "🔍 Review CV", description: "Double AI review" },
        { id: "subscribe", title: "🔔 Subscribe", description: "RSS job alerts" },
        { id: "unsubscribe", title: "🔕 Unsubscribe", description: "Stop alerts" },
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
