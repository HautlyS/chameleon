import { execFileSync, execSync, type ExecFileSyncOptions } from "child_process";
import { existsSync, mkdirSync, writeFileSync, unlinkSync } from "fs";
import { resolve } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

export interface BridgeConfig {
  projectRoot: string;
  pythonBin: string;
}

export function getBridgeConfig(): BridgeConfig {
  const projectRoot = resolve(__dirname, process.env.CHAMELEON_PROJECT_ROOT || "../../..");
  const pythonFromEnv = process.env.CHAMELEON_PYTHON;
  let pythonBin: string;

  if (pythonFromEnv) {
    pythonBin = pythonFromEnv;
  } else {
    const candidates = ["python3", "python", "python.exe", "python3.exe"];
    const found = candidates.find((name) => {
      try {
        execSync(`${name} --version`, { stdio: "ignore" });
        return true;
      } catch {
        return false;
      }
    });
    pythonBin = found || "python3";
  }

  return { projectRoot, pythonBin };
}

function runBridge(args: string[], timeoutMs: number = 60000, config?: Partial<BridgeConfig>): string {
  const cfg = { ...getBridgeConfig(), ...config };
  const bridgeDir = resolve(cfg.projectRoot, "chameleon-bot");

  if (!existsSync(bridgeDir)) {
    return JSON.stringify({ error: `Bridge directory not found: ${bridgeDir}` });
  }

  const opts: ExecFileSyncOptions = {
    cwd: bridgeDir,
    encoding: "utf-8",
    maxBuffer: 10 * 1024 * 1024,
    timeout: timeoutMs,
  };

  try {
    return String(execFileSync(cfg.pythonBin, ["-m", "bridge", ...args], opts)).trim();
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return JSON.stringify({ error: `Bridge exec failed: ${msg}` });
  }
}

function tempFile(prefix: string, content: string): string {
  const tmpDir = resolve(getBridgeConfig().projectRoot, ".chameleon");
  if (!existsSync(tmpDir)) {
    mkdirSync(tmpDir, { recursive: true });
  }
  const tmpPath = resolve(tmpDir, `${prefix}_${Date.now()}.txt`);
  writeFileSync(tmpPath, content, "utf-8");
  return tmpPath;
}

export function scanJobs(
  query?: string,
  platforms?: string,
  limit?: number,
  config?: Partial<BridgeConfig>,
): string {
  const args = ["scan", "--json"];
  if (query) args.push("--query", query);
  if (platforms) args.push("--platforms", platforms);
  if (limit) args.push("--limit", String(limit));
  return runBridge(args, 60000, config);
}

export function listAnalyses(config?: Partial<BridgeConfig>): string {
  return runBridge(["analyses", "--json"], 30000, config);
}

export function listTailoredCvs(config?: Partial<BridgeConfig>): string {
  return runBridge(["tailored", "--json"], 30000, config);
}

export function renderCv(yamlPath: string, config?: Partial<BridgeConfig>): string {
  return runBridge(["render", "--yaml", yamlPath], 60000, config);
}

export function tailorCv(
  jdText: string,
  company?: string,
  title?: string,
  config?: Partial<BridgeConfig>,
): string {
  const tmpPath = tempFile("jd", jdText);
  try {
    const args = ["tailor", "--yaml", tmpPath, "--json"];
    if (company) args.push("--company", company);
    if (title) args.push("--title", title);
    return runBridge(args, 180000, config);
  } finally {
    try { unlinkSync(tmpPath); } catch {}
  }
}

export function coverLetter(
  jdText: string,
  cvPath?: string,
  config?: Partial<BridgeConfig>,
): string {
  const tmpPath = tempFile("cl_jd", jdText);
  try {
    const args = ["cover-letter", "--yaml", tmpPath, "--json"];
    if (cvPath) args.push("--cv", cvPath);
    return runBridge(args, 120000, config);
  } finally {
    try { unlinkSync(tmpPath); } catch {}
  }
}

export function answerQuestion(
  questionText: string,
  jdText?: string,
  cvPath?: string,
  config?: Partial<BridgeConfig>,
): string {
  const qPath = tempFile("q", questionText);
  let jdPath: string | undefined;
  try {
    const args = ["question", "--yaml", qPath, "--json"];
    if (jdText) {
      jdPath = tempFile("q_jd", jdText);
      args.push("--jd", jdPath);
    }
    if (cvPath) args.push("--cv", cvPath);
    return runBridge(args, 120000, config);
  } finally {
    try { unlinkSync(qPath); } catch {}
    if (jdPath) {
      try { unlinkSync(jdPath); } catch {}
    }
  }
}

export function scoreJob(analysisIdOrPath: string, config?: Partial<BridgeConfig>): string {
  return runBridge(["score", "--analysis", analysisIdOrPath, "--json"], 120000, config);
}

export function getAnalysis(analysisIdOrPath: string, config?: Partial<BridgeConfig>): string {
  return runBridge(["analysis", "--analysis", analysisIdOrPath, "--json"], 30000, config);
}

export function ghostPdf(
  pdfPath: string,
  jdText?: string,
  extraTerms?: string,
  config?: Partial<BridgeConfig>,
): string {
  let jdPath: string | undefined;
  const args = ["ghost", "--yaml", pdfPath, "--json"];
  if (jdText) {
    jdPath = tempFile("ghost_jd", jdText);
    args.push("--jd", jdPath);
  }
  if (extraTerms) args.push("--extra", extraTerms);
  try {
    return runBridge(args, 60000, config);
  } finally {
    if (jdPath) {
      try { unlinkSync(jdPath); } catch {}
    }
  }
}

export function reviewCv(
  yamlPath: string,
  jdText: string,
  single?: boolean,
  config?: Partial<BridgeConfig>,
): string {
  const jdPath = tempFile("review_jd", jdText);
  const args = ["review", "--yaml", yamlPath, "--jd", jdPath, "--json"];
  if (single) args.push("--single");
  try {
    return runBridge(args, 180000, config);
  } finally {
    try { unlinkSync(jdPath); } catch {}
  }
}

export function subscribeWhatsApp(phoneNumber: string, config?: Partial<BridgeConfig>): string {
  return runBridge(["subscribe", "--subscribe", phoneNumber], 30000, config);
}

export function unsubscribeWhatsApp(phoneNumber: string, config?: Partial<BridgeConfig>): string {
  return runBridge(["unsubscribe", "--unsubscribe", phoneNumber], 30000, config);
}
