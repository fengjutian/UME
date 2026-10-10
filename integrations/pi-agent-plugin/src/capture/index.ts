import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type MemoryClient from "ume";
import type { UMEConfig, ScopeContext } from "../types.ts";
import { DEFAULT_CUSTOM_CATEGORIES } from "../types.ts";
import { resolveAddParams } from "../memory/scoping.ts";
import { captureEvent } from "../telemetry.ts";
import { createMemoryLifecycle } from "../../../agent-plugin-core/typescript/src/lifecycle.ts";

export { extractConversation } from "../../../agent-plugin-core/typescript/src/lifecycle.ts";

export function setupAutoCapture(
  pi: ExtensionAPI,
  ume: MemoryClient,
  config: UMEConfig,
  getScopeCtx: () => ScopeContext,
  telemetryCtx?: { apiKey?: string },
  lifecycle: ReturnType<typeof createMemoryLifecycle> = createMemoryLifecycle(),
): void {
  if (!config.autoCapture) return;

  pi.on("agent_end", async (event) => {
    const messages = event.messages ?? [];
    const conversation = lifecycle.prepareConversation(messages);
    if (conversation.length === 0) return;

    const scopeCtx = getScopeCtx();
    const addParams = resolveAddParams("project", scopeCtx);

    try {
      await ume.add(conversation, {
        ...addParams,
        customCategories: DEFAULT_CUSTOM_CATEGORIES,
      });
      captureEvent("pi.capture.auto", { success: true, message_count: conversation.length }, telemetryCtx);
    } catch (err: unknown) {
      captureEvent("pi.capture.auto", {
        success: false,
        error_type: err instanceof Error ? err.name : "unknown",
      }, telemetryCtx);
      console.error("[ume] auto-capture failed:", err);
    }
  });
}
