/**
 * Cursor SDK agent runner — called by agent_nodes.py via subprocess.
 *
 * Usage:
 *   node cursor_agent_runner.js --api-key <key> --model <model> --cwd <path> --prompt <prompt>
 *
 * Streams each assistant text chunk as a JSON line: {"type":"text","text":"..."}
 * Final line: {"type":"done","status":"finished"|"error","result":"..."}
 */

const path = require("path");
// Try local node_modules first, then /tmp (where npm install ran)
let Agent;
try {
  ({ Agent } = require(path.join(__dirname, "node_modules/@cursor/sdk")));
} catch {
  ({ Agent } = require("/tmp/node_modules/@cursor/sdk"));
}

async function main() {
  const args = process.argv.slice(2);
  const get = (flag) => {
    const i = args.indexOf(flag);
    return i !== -1 ? args[i + 1] : null;
  };

  const apiKey = get("--api-key") || process.env.CURSOR_API_KEY;
  const model = get("--model") || "auto";
  const cwd = get("--cwd") || process.cwd();
  const promptArg = get("--prompt");

  if (!apiKey) {
    process.stdout.write(
      JSON.stringify({ type: "error", text: "CURSOR_API_KEY not set. Get yours at cursor.com/dashboard/integrations" }) + "\n"
    );
    process.exit(1);
  }

  if (!promptArg) {
    process.stdout.write(JSON.stringify({ type: "error", text: "No --prompt provided" }) + "\n");
    process.exit(1);
  }

  try {
    const run = await Agent.prompt(promptArg, {
      apiKey,
      model: { id: model },
      local: { cwd },
    });

    // Emit the result text
    const resultText = run.result || "";
    if (resultText) {
      process.stdout.write(JSON.stringify({ type: "text", text: resultText }) + "\n");
    }

    process.stdout.write(
      JSON.stringify({ type: "done", status: run.status, result: resultText }) + "\n"
    );
  } catch (err) {
    process.stdout.write(
      JSON.stringify({ type: "error", text: err.message || String(err) }) + "\n"
    );
    process.exit(1);
  }
}

main();
