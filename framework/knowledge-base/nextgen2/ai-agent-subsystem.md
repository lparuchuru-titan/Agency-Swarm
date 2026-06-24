# AI Agent Subsystem (org-specific)
_A Claude-based chat agent embedded in the CPQ quoting UI. Source: code analysis._

## What it is
Reps edit a quote/cart in natural language (add products, qty, discounts, ramps, promos, header). **Provider = Anthropic Claude** via Named Credential `Anthropic_API` (`https://api.anthropic.com`, `callout:Anthropic_API/v1/messages`, header `anthropic-version: 2023-06-01`); OpenAI/Gemini exist only as fallback in `AIProviderService`.

## Apex layer
- **`AIAgentController`** — only LWC-facing controller. `@AuraEnabled processAgentMessage(...)` runs one turn: guardrails → (Smart Planner or legacy router) → Claude tool-use loop → returns `AgentResponse{message, actions[], tokensUsed, sessionId}`. **Tools emit action JSON, not DML.**
- `AIPlannerService` — "Smart Planner": one Claude call classifies intent + resolves product/promo Ids + emits structured steps.
- `AIProviderService` — LLM transport: `sendWithFallback` (CLAUDE→OPENAI→GEMINI), prompt-cache breakpoints, circuit breaker, token parsing.
- `AIPromptService` — **separate legacy** one-shot quote-JSON generator doing its own Gemini/GPT-4o-mini callouts; NOT the agent/planner pipeline.
- `AIAgentSessionService` — `AI_Agent_Session__c`/`AI_Agent_Message__c` lifecycle. (Older `AIConversationService` + `AI_Conversation__c`/`AI_Message__c` coexists — the Session model is the active path.)
- `AIGuardrailService`, `AIAnalyticsService`, `AIAgentMessageTrimQueueable`, `AIAgentSummaryQueueable`, `AIAnalyticsRetentionBatch`, `AIAgentRetentionScheduler`.

## Models (hardcoded — drift risk)
Default `claude-sonnet-4-20250514`; CART_UPDATER uses `claude-haiku-4-5-20251001` (a code comment notes Haiku 3.5 `claude-3-5-haiku-20241022` was retired/404). Tool-use loop caps: `MAX_TOOL_ITERATIONS=8`, `MAX_SPECIALIST_ITERATIONS=4`. Prompt caching via inline `cache_control` (gated by `AI_Caching_Config__c`).

## LWC layer
`lwc/nextGenAiAgent/` (chat panel) + `nextGenQuotingBaseAgent.js` (helper in the cart LWC). Talks to Apex only via `AIAgentController` (`processAgentMessage`, `getActiveSessionFull`, `endSession`; parent wires `isAIAgentEnabled`). **Cart edits are applied client-side**: LWC fires `CustomEvent('agentaction', {actions})` → parent `handleAgentActionFromEvent` switches on `actionType` and calls the real cart engine. Voice I/O is Chrome-only (`webkitSpeechRecognition` / `speechSynthesis`).

## Gating & guardrails
- Kill switch: `AIAgentController.isAIAgentEnabled()` reads `ORG_Setting__mdt` record `AI_Agent_Enabled` (fail-closed). `AI_Agent_Smart_Planner` toggles planner vs legacy.
- `AIGuardrailService`: input cap 2000 chars, ~60 req/hr, ~22 prompt-injection patterns, output redaction of `sk-ant-…` keys, per-tool param validation (discount −100..100, ≤12 ramp segments, term 1–120). No quantity cap (approvals handle it).
- Retention: `AI_Analytics__c` deleted after 60 days; sessions abandoned/trimmed per `AI_Chat_Retention_Config__mdt`.

## Gotchas
1. Two storage models coexist (Session vs Conversation) — Session is active.
2. `AIPromptService` is a different generation (Gemini/GPT) — not the Claude agent.
3. No server-side DML for cart edits — if actions aren't dispatched/handled, nothing persists; `saveQuote` held for explicit confirmation.
4. Analytics must `flushPending()` AFTER all callouts (enqueueJob creates pending DML that blocks further callouts).
5. Model IDs hardcoded; voice = Chrome only.

## Files
`classes/AIAgentController.cls`, `AIProviderService.cls`, `AIPlannerService.cls`, `AIPromptService.cls`, `AIAgentSessionService.cls`, `AIGuardrailService.cls`, `AIAnalyticsService.cls` (+ queueables/batch/scheduler); `lwc/nextGenAiAgent/`, `lwc/nextGenQuotingBase/nextGenQuotingBaseAgent.js`; `namedCredentials/Anthropic_API`, `objects/AI_Chat_Retention_Config__mdt`, `AI_Caching_Config__c`, `ORG_Setting__mdt`.
