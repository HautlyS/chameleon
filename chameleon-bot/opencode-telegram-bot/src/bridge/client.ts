import { execSync, type ExecSyncOptions } from "child_process";
import { existsSync } from "fs";
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

  constructor() {
    const envRoot = process.env.CHAMELEON_PROJECT_ROOT;
    const projectRoot = envRoot
      ? resolve(envRoot)
      : resolve(__dirname, "..", "..", "..", "..");
    this.bridgeDir = resolve(projectRoot, "chameleon-bot");

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
      const out = execSync(cmd, opts).trim();
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
}

export const bridge = new BridgeClient();

