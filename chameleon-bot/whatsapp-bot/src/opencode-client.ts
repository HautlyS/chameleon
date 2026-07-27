// Lazy-loaded OpenCode client.
// No top-level SDK import: the import() call happens at runtime so the bot
// starts without @opencode-ai/sdk installed (bridge-only mode).

export interface OpenCodeConfig {
  apiUrl: string;
  username?: string;
  password?: string;
  modelProvider: string;
  modelId: string;
  projectDir: string;
}

export function loadOpenCodeConfig(): OpenCodeConfig {
  return {
    apiUrl: process.env.OPENCODE_API_URL || "http://localhost:4096",
    username: process.env.OPENCODE_SERVER_USERNAME,
    password: process.env.OPENCODE_SERVER_PASSWORD,
    modelProvider: process.env.OPENCODE_MODEL_PROVIDER || "anthropic",
    modelId: process.env.OPENCODE_MODEL_ID || "claude-sonnet-4-20250514",
    projectDir: process.env.CHAMELEON_PROJECT_ROOT || process.cwd(),
  };
}

// ── Minimal SDK type shapes (we only use a fraction of the API) ──────

interface SdkClient {
  global: {
    health(): Promise<{ healthy: boolean }>;
    event(opts: { signal: AbortSignal }): Promise<{ stream: AsyncIterable<unknown> }>;
  };
  session: {
    create(opts: { directory: string }): Promise<{ info: { id: string; directory?: string } }>;
    promptAsync(opts: {
      sessionID: string;
      directory: string;
      parts: Array<{ type: string; text: string }>;
      model: string;
    }): Promise<unknown>;
    abort(opts: { sessionID: string; directory: string }): Promise<unknown>;
  };
}

type SdkModule = { createOpencodeClient(opts: { baseUrl: string; headers?: Record<string, string> }): SdkClient };

// ── Lazy SDK loader + cached client ──────────────────────────────────

let sdkPromise: Promise<SdkModule> | null = null;
let cachedClient: SdkClient | null = null;

async function getClient(config: OpenCodeConfig): Promise<SdkClient> {
  if (cachedClient) return cachedClient;

  if (!sdkPromise) {
    sdkPromise = import("@opencode-ai/sdk/v2").catch((err: unknown) => {
      sdkPromise = null; // allow retry if package installed later
      throw err;
    }) as Promise<SdkModule>;
  }
  const mod = await sdkPromise;
  cachedClient = mod.createOpencodeClient({
    baseUrl: config.apiUrl,
    headers: config.password
      ? { Authorization: `Basic ${Buffer.from(`${config.username || "opencode"}:${config.password}`).toString("base64")}` }
      : undefined,
  });
  return cachedClient;
}

export function resetClient(): void {
  cachedClient = null;
  sdkPromise = null;
}

// ── Session State (module-level, single-user) ────────────────────────

export interface SessionState {
  id: string;
  directory: string;
}

let currentState: SessionState | null = null;
let busy = false;
let eventController: AbortController | null = null;
let eventLoopRunning = false;

export function getSession(): SessionState | null {
  return currentState;
}

export function isBusy(): boolean {
  return busy;
}

export function markBusy(): void {
  busy = true;
}

export function markIdle(): void {
  busy = false;
}

export function clearSession(): void {
  currentState = null;
  busy = false;
}

// ── Session & Prompt API ─────────────────────────────────────────────

export async function ensureSession(config: OpenCodeConfig): Promise<SessionState> {
  if (currentState) return currentState;

  const client = await getClient(config);
  const result = await client.session.create({ directory: config.projectDir });
  currentState = { id: result.info.id, directory: result.info.directory || config.projectDir };
  return currentState;
}

export async function sendPrompt(config: OpenCodeConfig, text: string): Promise<void> {
  const session = await ensureSession(config);
  const client = await getClient(config);

  await client.session.promptAsync({
    sessionID: session.id,
    directory: session.directory,
    parts: [{ type: "text", text }],
    model: `${config.modelProvider}/${config.modelId}`,
  });
}

export async function abortSession(config: OpenCodeConfig): Promise<void> {
  if (!currentState) return;
  try {
    const client = await getClient(config);
    await client.session.abort({ sessionID: currentState.id, directory: currentState.directory });
  } catch {
    // ignore abort errors
  }
}

export async function checkHealth(config: OpenCodeConfig, timeoutMs = 5000): Promise<boolean> {
  try {
    const client = await getClient(config);
    const result = await Promise.race([
      client.global.health(),
      new Promise<"timeout">((r) => setTimeout(() => r("timeout"), timeoutMs)),
    ]);
    if (result === "timeout") return false;
    return result.healthy;
  } catch {
    return false;
  }
}

// ── SSE Event Subscription with auto-reconnect ───────────────────────

export async function startEventSubscription(
  config: OpenCodeConfig,
  signal: AbortSignal,
  onEvent: (event: Record<string, unknown>) => void,
): Promise<void> {
  if (eventLoopRunning) return;
  eventLoopRunning = true;

  let retryDelay = 1000;

  while (!signal.aborted) {
    try {
      const client = await getClient(config);
      const controller = new AbortController();
      eventController = controller;

      const subscription = await client.global.event({ signal: controller.signal });

      for await (const event of subscription.stream) {
        if (signal.aborted || controller.signal.aborted) break;

        const raw = event as Record<string, unknown>;
        const directory = raw.directory as string | undefined;
        if (directory && directory !== config.projectDir) continue;

        const payload = (raw.payload ?? raw) as Record<string, unknown>;
        onEvent(payload);
      }

      retryDelay = 1000;
    } catch (err: unknown) {
      if (signal.aborted) break;
      if (err instanceof Error && (err.name === "AbortError" || err.message.includes("AbortError"))) break;

      console.error(`[opencode] Event subscription error, retry in ${retryDelay}ms:`, err);

      await new Promise((r) => setTimeout(r, retryDelay));
      retryDelay = Math.min(retryDelay * 2, 15000);
    }
  }

  eventLoopRunning = false;
  eventController = null;
}

export function stopEventSubscription(): void {
  if (eventController) {
    eventController.abort();
    eventController = null;
  }
}
