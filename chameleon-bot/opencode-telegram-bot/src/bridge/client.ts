import { execSync, type ExecSyncOptions } from "child_process";
import { existsSync, mkdirSync, writeFileSync, unlinkSync } from "fs";
import { fileURLToPath } from "url";
import { resolve, dirname } from "path";
import { logger } from "../utils/logger.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

interface BridgeResult {
  success: boolean;
  error?: string;
  data?: unknown;
}

class BridgeClient {
  private pythonBin: string;
  private bridgeDir: string;
  private tempDir: string;

  constructor() {
    const envRoot = process.env.CHAMELEON_PROJECT_ROOT;
    const projectRoot = envRoot
      ? resolve(envRoot)
      : resolve(__dirname, "..", "..", "..", "..");
    this.bridgeDir = resolve(projectRoot, "chameleon-bot");
    this.tempDir = resolve(projectRoot, ".chameleon");

    const pythonFromEnv = process.env.CHAMELEON_PYTHON;
    if (pythonFromEnv) {
      this.pythonBin = resolve(pythonFromEnv);
    } else {
      const candidates = ["python3", "python", "python.exe", "python3.exe"];
      const found = candidates.find((name) => {
        try { execSync(`${name} --version`, { stdio: "ignore" }); return true; }
        catch { return false; }
      });
      this.pythonBin = found || "python3";
    }
  }

  private tempFile(prefix: string, content: string): string {
    if (!existsSync(this.tempDir)) {
      mkdirSync(this.tempDir, { recursive: true });
    }
    const tmpPath = resolve(this.tempDir, `${prefix}_${Date.now()}.txt`);
    writeFileSync(tmpPath, content, "utf-8");
    return tmpPath;
  }

  private run(args: string[], timeoutMs = 60000): BridgeResult {
    if (!existsSync(this.bridgeDir)) {
      return { success: false, error: `Bridge not found: ${this.bridgeDir}` };
    }
    const cmd = [this.pythonBin, "-m", "bridge", ...args].join(" ");
    const opts: ExecSyncOptions = {
      cwd: this.bridgeDir,
      encoding: "utf-8",
      maxBuffer: 10 * 1024 * 1024,
      timeout: timeoutMs,
    };
    try {
      const out = String(execSync(cmd, opts)).trim();
      try { return { success: true, data: JSON.parse(out) }; }
      catch { return { success: true, data: out }; }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      logger.error(`[Bridge] exec failed: ${msg}`);
      return { success: false, error: msg };
    }
  }

  scanJobs(query = "", platforms = "", limit = 15): BridgeResult {
    const args = ["scan", "--json"];
    if (query) args.push("--query", query);
    if (platforms) args.push("--platforms", platforms);
    if (limit) args.push("--limit", String(limit));
    return this.run(args, 60000);
  }

  listAnalyses(): BridgeResult {
    return this.run(["analyses", "--json"], 30000);
  }

  listTailoredCvs(): BridgeResult {
    return this.run(["tailored", "--json"], 30000);
  }

  renderCv(yamlPath: string): BridgeResult {
    return this.run(["render", "--yaml", yamlPath], 60000);
  }

  ghostPdf(pdfPath: string, jdFile?: string, extraTerms?: string): BridgeResult {
    const args = ["ghost", "--yaml", pdfPath, "--json"];
    if (jdFile) args.push("--jd", jdFile);
    if (extraTerms) args.push("--extra", extraTerms);
    return this.run(args, 60000);
  }

  reviewCv(yamlPath: string, jdFile: string, single = false): BridgeResult {
    const args = ["review", "--yaml", yamlPath, "--jd", jdFile, "--json"];
    if (single) args.push("--single");
    return this.run(args, 180000);
  }

  tailorCv(jdText: string, company?: string, title?: string): BridgeResult {
    const tmpPath = this.tempFile("jd", jdText);
    try {
      const args = ["tailor", "--yaml", tmpPath, "--json"];
      if (company) args.push("--company", company);
      if (title) args.push("--title", title);
      return this.run(args, 180000);
    } finally {
      try { unlinkSync(tmpPath); } catch { /* ignore */ }
    }
  }

  coverLetter(jdText: string, cvPath?: string): BridgeResult {
    const tmpPath = this.tempFile("cl_jd", jdText);
    try {
      const args = ["cover-letter", "--yaml", tmpPath, "--json"];
      if (cvPath) args.push("--cv", cvPath);
      return this.run(args, 120000);
    } finally {
      try { unlinkSync(tmpPath); } catch { /* ignore */ }
    }
  }

  answerQuestion(questionText: string, jdText?: string, cvPath?: string): BridgeResult {
    const qPath = this.tempFile("q", questionText);
    try {
      const args = ["question", "--yaml", qPath, "--json"];
      if (jdText) {
        const jdPath = this.tempFile("q_jd", jdText);
        args.push("--jd", jdPath);
      }
      if (cvPath) args.push("--cv", cvPath);
      return this.run(args, 120000);
    } finally {
      try { unlinkSync(qPath); } catch { /* ignore */ }
    }
  }

  scoreJob(analysisIdOrPath: string): BridgeResult {
    return this.run(["score", "--analysis", analysisIdOrPath, "--json"], 120000);
  }

  subscribe(phoneOrChatId: string, channel: "whatsapp" | "telegram"): BridgeResult {
    const flag = channel === "telegram" ? "--telegram" : "--subscribe";
    return this.run(["subscribe", flag, phoneOrChatId], 30000);
  }

  unsubscribe(phoneOrChatId: string, channel: "whatsapp" | "telegram"): BridgeResult {
    const flag = channel === "telegram" ? "--telegram" : "--unsubscribe";
    return this.run(["unsubscribe", flag, phoneOrChatId], 30000);
  }
}

export const bridge = new BridgeClient();
