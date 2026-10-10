import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import type { UMEConfig } from "../types.ts";

const AGENT_ROOT = path.join(os.homedir(), ".pi", "agent");
export const CONFIG_DIR = AGENT_ROOT;
const CONFIG_PATH = path.join(AGENT_ROOT, "ume-config.json");

const DEFAULT_CONFIG: UMEConfig = {
  apiKey: "",
  userId: "",
  autoCapture: true,
  defaultScope: "project",
  contextInjection: true,
  searchThreshold: 0.3,
};

export function loadConfig(): UMEConfig {
  let fileConfig: Partial<UMEConfig> = {};

  if (fs.existsSync(CONFIG_PATH)) {
    try {
      const raw = fs.readFileSync(CONFIG_PATH, "utf-8");
      fileConfig = JSON.parse(raw);
    } catch {
      // Corrupted config — use defaults
    }
  }

  const config: UMEConfig = {
    ...DEFAULT_CONFIG,
    ...fileConfig,
  };

  if (process.env.UME_API_KEY) {
    config.apiKey = process.env.UME_API_KEY;
  }
  if (process.env.UME_USER_ID) {
    config.userId = process.env.UME_USER_ID;
  }

  return config;
}
