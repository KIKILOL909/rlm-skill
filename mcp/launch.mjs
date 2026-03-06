// Auto-install dependencies and start the MCP server.
// Claude Code plugin cache doesn't run npm install, so we handle it here.
import { execSync } from "child_process";
import { existsSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

var dir = dirname(fileURLToPath(import.meta.url));

if (!existsSync(join(dir, "node_modules"))) {
  try {
    execSync("npm install --no-fund --no-audit --production", {
      cwd: dir,
      stdio: ["pipe", "pipe", "pipe"],
      timeout: 60000,
    });
  } catch (e) {
    process.stderr.write("RLM MCP: failed to install dependencies: " + e.message + "\n");
    process.exit(1);
  }
}

await import("./server.mjs");
