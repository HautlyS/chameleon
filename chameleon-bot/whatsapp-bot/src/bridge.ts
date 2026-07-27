import { execSync, type ExecSyncOptions } from "child_process";
import { existsSync } from "fs";
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
    pythonBin = resolve(__dirname, pythonFromEnv);
  } else {
    // Cross-platform: try common names
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

function runBridge(args: string[], config?: Partial<BridgeConfig>): string {
  const cfg = { ...getBridgeConfig(), ...config };
  const bridgeDir = resolve(cfg.projectRoot, "chameleon-bot");

  if (!existsSync(bridgeDir)) {
    return JSON.stringify({ error: `Bridge directory not found: ${bridgeDir}` });
  }

  const cmd = [cfg.pythonBin, "-m", "bridge", ...args].join(" ");
  const opts: ExecSyncOptions = {
    cwd: bridgeDir,
    encoding: "utf-8",
    maxBuffer: 10 * 1024 * 1024,
    timeout: 60000,
  };

  try {
    return execSync(cmd, opts).trim();
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return JSON.stringify({ error: `Bridge exec failed: ${msg}` });
  }
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
  return runBridge(args, config);
}

export function listAnalyses(config?: Partial<BridgeConfig>): string {
  return runBridge(["analyses", "--json"], config);
}

export function listTailoredCvs(config?: Partial<BridgeConfig>): string {
  return runBridge(["tailored", "--json"], config);
}

export function renderCv(yamlPath: string, config?: Partial<BridgeConfig>): string {
  return runBridge(["render", "--yaml", yamlPath], config);
}
