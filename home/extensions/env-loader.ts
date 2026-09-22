/**
 * env-loader — loads ~/.pi/agent/.env into process.env at pi startup.
 *
 * Runs before any per-request env reads (model router, subagent router, etc.).
 * Never overrides variables already set in the environment.
 */

import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

const envPath = join(homedir(), ".pi", "agent", ".env");

if (existsSync(envPath)) {
  try {
    const lines = readFileSync(envPath, "utf-8").replace(/^\uFEFF/, "").split("\n");
    for (const raw of lines) {
      const line = raw.trim();
      if (!line || line.startsWith("#")) continue;
      const stripped = line.startsWith("export ") ? line.slice(7).trim() : line;
      const eq = stripped.indexOf("=");
      if (eq <= 0) continue;
      const key = stripped.slice(0, eq).trim();
      if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) continue;
      let value = stripped.slice(eq + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      if (process.env[key] === undefined) process.env[key] = value;
    }
  } catch {
    // unreadable .env — extensions fail open on missing keys
  }
}

export default function () {}
