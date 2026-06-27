/**
 * Cursor SDK agent runner — streaming version.
 * Uses Agent.create() + run.messages() so each text chunk is emitted
 * immediately as it arrives, giving real-time progress in FleetView.
 *
 * Usage:
 *   node cursor_agent_runner.js --api-key <key> --model <model> --cwd <path> --prompt <prompt>
 *
 * Each output line is a JSON event:
 *   {"type":"text","text":"..."}    — streaming chunk
 *   {"type":"done","status":"finished","result":"..."}
 *   {"type":"error","text":"..."}
 */

const path = require("path");

// Load @cursor/sdk — try local node_modules first, then /tmp
let Agent;
try {
  ({ Agent } = require(path.join(__dirname, "node_modules/@cursor/sdk")));
} catch {
  try {
    ({ Agent } = require("/tmp/node_modules/@cursor/sdk"));
  } catch (e) {
    process.stdout.write(JSON.stringify({ type: "error", text: "Cannot load @cursor/sdk: " + e.message }) + "\n");
    process.exit(1);
  }
}

function emit(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

async function main() {
  const args = process.argv.slice(2);
  const get = (flag) => { const i = args.indexOf(flag); return i !== -1 ? args[i + 1] : null; };

  const apiKey    = get("--api-key") || process.env.CURSOR_API_KEY;
  const modelArg  = get("--model") || "auto";
  const cwd       = get("--cwd") || process.cwd();
  const prompt    = get("--prompt");
  const agentId   = get("--agent-id") || "agent";
  const agentName = get("--agent-name") || agentId;

  if (!apiKey) {
    emit({ type: "error", text: "CURSOR_API_KEY not set — get yours at cursor.com/dashboard/integrations" });
    process.exit(1);
  }
  if (!prompt) {
    emit({ type: "error", text: "No --prompt provided" });
    process.exit(1);
  }

  // Announce which agent + model is starting
  emit({ type: "agent_start", agent_id: agentId, agent_name: agentName, model: modelArg });

  try {
    let result = "";
    let status = "finished";
    let resolvedModel = modelArg;

    const agent = await Agent.create({
      apiKey,
      model: { id: modelArg },
      local: { cwd },
    });

    const run = await agent.send(prompt);

    // Stream each message chunk as it arrives
    for await (const message of run.stream()) {
      // Try to capture the actual model name from the message metadata
      if (message.model && message.model !== resolvedModel) {
        resolvedModel = message.model;
        emit({ type: "model_resolved", model: resolvedModel });
      }
      if (message.type === "assistant") {
        for (const block of (message.message?.content || [])) {
          if (block.type === "text" && block.text) {
            result += block.text;
            emit({ type: "text", text: block.text });
          }
        }
      }
    }

    const final = await run.wait();
    status = final?.status || "finished";
    if (final?.model) resolvedModel = final.model;

    // If streaming gave us nothing but wait() has a result, use that
    if (!result && final?.result) {
      result = final.result;
      emit({ type: "text", text: result });
    }

    // Dispose the agent
    if (typeof agent[Symbol.asyncDispose] === "function") {
      await agent[Symbol.asyncDispose]();
    } else if (typeof agent.close === "function") {
      agent.close();
    }

    // Capture usage + model from final result
    const usage = final?.usage || {};
    const resolvedFinalModel = final?.model?.id || resolvedModel;
    const durationMs = final?.durationMs || 0;

    emit({
      type: "done",
      status,
      result,
      model: resolvedFinalModel,
      usage: {
        input_tokens:       usage.inputTokens       || 0,
        output_tokens:      usage.outputTokens      || 0,
        cache_read_tokens:  usage.cacheReadTokens   || 0,
        cache_write_tokens: usage.cacheWriteTokens  || 0,
        total_tokens:       usage.totalTokens       || 0,
      },
      duration_ms: durationMs,
    });

  } catch (err) {
    emit({ type: "error", text: err.message || String(err) });
    process.exit(1);
  }
}

main();
