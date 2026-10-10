import type { SearchMemoryOptions } from "ume";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import type MemoryClient from "ume";
import type { UMEConfig, ScopeContext, Scope } from "./types.ts";
import { DEFAULT_CUSTOM_CATEGORIES } from "./types.ts";
import { resolveSearchFilters, resolveAddParams } from "./memory/scoping.ts";
import { formatMemoryList, formatMemoryCompact, groupByCategory } from "./memory/formatting.ts";
import { captureCommandEvent } from "./telemetry.ts";
import { PLATFORM_SOURCE } from "./attribution.ts";

// Wire identity is set once on the shared client in entry.ts, which covers
// every path including recall, capture, tools and deletion. It stays in the
// body of the two calls below as well: body `source` is what the backend reads
// when the header is absent.

const SEARCH_TOP_K = 10;

export function registerCommands(
  pi: ExtensionAPI,
  ume: MemoryClient,
  config: UMEConfig,
  getScopeCtx: () => ScopeContext,
  telemetryCtx?: { apiKey?: string },
): void {
  const sendFeedback = (customType: string, content: string): void => {
    pi.sendMessage({ customType, content, display: true });
  };

  const pluralize = (n: number, one: string, many: string): string =>
    `${n} ${n === 1 ? one : many}`;

  const searchMemories = async (query: string, scope: Scope) => {
    const filters = resolveSearchFilters(scope, getScopeCtx());
    const result = await ume.search(query, {
      filters,
      threshold: config.searchThreshold,
      topK: SEARCH_TOP_K,
      rerank: true,
      source: PLATFORM_SOURCE,
      // Widened by exactly this one property. `source` reaches the wire via the
      // SDK's camelToSnakeKeys spread, but it is absent from SearchMemoryOptions
      // in the published ume types. A blanket `as never` would also disable
      // checking of filters, threshold, topK and rerank above.
    } as SearchMemoryOptions & { source: string });
    return result.results ?? [];
  };

  pi.registerCommand("ume-remember", {
    description: "Store a memory verbatim (no inference)",
    handler: async (args, ctx) => {
      const text = args?.trim();
      if (!text) {
        ctx.ui.notify("Usage: /ume-remember <text>", "warning");
        return;
      }

      const addParams = resolveAddParams(config.defaultScope, getScopeCtx());
      const result = await ume.add(
        [{ role: "user", content: text }],
        { ...addParams, customCategories: DEFAULT_CUSTOM_CATEGORIES, infer: false, source: PLATFORM_SOURCE },
      );
      captureCommandEvent("ume-remember", {}, telemetryCtx);

      const storedItems = (Array.isArray(result) ? result : [])
        .map((m) => (m as { memory?: string }).memory)
        .filter((m): m is string => Boolean(m));
      const items = storedItems.length > 0 ? storedItems : [text];
      sendFeedback(
        "ume-remember",
        [`**Stored to ${config.defaultScope} memory**`, ...items.map((m) => `- ${m}`)].join("\n"),
      );
    },
  });

  pi.registerCommand("ume-forget", {
    description: "Delete memories matching a natural language query",
    handler: async (args, ctx) => {
      const query = args?.trim();
      if (!query) {
        ctx.ui.notify("Usage: /ume-forget <query>", "warning");
        return;
      }

      const memories = await searchMemories(query, config.defaultScope);

      if (memories.length === 0) {
        captureCommandEvent("ume-forget", { result_count: 0 }, telemetryCtx);
        sendFeedback("ume-forget", `**No matches for "${query}"** — nothing to forget.`);
        return;
      }

      const forgotten = (mem: Parameters<typeof formatMemoryCompact>[0]) => {
        captureCommandEvent("ume-forget", { deleted_count: 1 }, telemetryCtx);
        sendFeedback(
          "ume-forget",
          [`**Forgotten from ${config.defaultScope} memory**`, `- ${formatMemoryCompact(mem)}`].join("\n"),
        );
      };

      if (memories.length === 1) {
        const target = memories[0];
        const confirmed = await ctx.ui.confirm("Delete this memory?", formatMemoryCompact(target));
        if (!confirmed) {
          sendFeedback("ume-forget", "**Cancelled** — no memories deleted.");
          return;
        }
        await ume.delete(target.id);
        forgotten(target);
        return;
      }

      const labels = memories.map((m) => formatMemoryCompact(m));
      const selected = await ctx.ui.select(
        `Found ${pluralize(memories.length, "match", "matches")} for "${query}" — which should I delete?`,
        labels,
      );
      if (!selected) {
        sendFeedback("ume-forget", "**Cancelled** — no memories deleted.");
        return;
      }
      const idx = labels.indexOf(selected);
      if (idx < 0) return;
      const target = memories[idx];
      await ume.delete(target.id);
      forgotten(target);
    },
  });

  pi.registerCommand("ume-search", {
    description: "Semantic search across memories",
    handler: async (args, ctx) => {
      const query = args?.trim();
      if (!query) {
        ctx.ui.notify("Usage: /ume-search <query>", "warning");
        return;
      }

      const memories = await searchMemories(query, config.defaultScope);
      captureCommandEvent("ume-search", { result_count: memories.length }, telemetryCtx);

      if (memories.length === 0) {
        sendFeedback("ume-search", `**No matches for "${query}"** · ${config.defaultScope} scope`);
        return;
      }

      sendFeedback(
        "ume-search",
        [
          `**${pluralize(memories.length, "match", "matches")} for "${query}"** · ${config.defaultScope} scope`,
          "",
          formatMemoryList(memories),
        ].join("\n"),
      );
    },
  });

  pi.registerCommand("ume-tour", {
    description: "Browse all memories grouped by category",
    handler: async (args, ctx) => {
      const raw = args?.trim().toLowerCase();
      const validScopes: Scope[] = ["project", "session", "global"];
      if (raw && !validScopes.includes(raw as Scope)) {
        ctx.ui.notify(`Invalid scope "${raw}". Must be one of: ${validScopes.join(", ")}`, "warning");
        return;
      }
      const scope: Scope = (raw as Scope) || config.defaultScope;
      const filters = resolveSearchFilters(scope, getScopeCtx());
      const result = await ume.getAll({ filters });
      const memories = result.results ?? [];

      if (memories.length === 0) {
        captureCommandEvent("ume-tour", { memory_count: 0, scope }, telemetryCtx);
        sendFeedback("ume-tour", `**No memories in ${scope} scope yet** — store one with \`/ume-remember\`.`);
        return;
      }

      const groups = groupByCategory(memories);
      const lines: string[] = [
        `**Memory tour** · ${pluralize(memories.length, "memory", "memories")} · ${scope} scope`,
        "",
      ];

      for (const [category, items] of groups) {
        lines.push(`### ${category} (${items.length})`);
        for (const m of items) {
          lines.push(`- ${formatMemoryCompact(m)}`);
        }
        lines.push("");
      }

      captureCommandEvent("ume-tour", { memory_count: memories.length, scope }, telemetryCtx);
      sendFeedback("ume-tour", lines.join("\n"));
    },
  });

  pi.registerCommand("ume-scope", {
    description: "Change default memory scope for this session (project, session, global)",
    handler: async (args, ctx) => {
      const scope = args?.trim().toLowerCase();
      const valid: Scope[] = ["project", "session", "global"];

      if (!scope) {
        sendFeedback(
          "ume-scope",
          [
            `**Current scope: ${config.defaultScope}**`,
            `New memories save to the **${config.defaultScope}** pool. Switch with \`/ume-scope <${valid.join(" | ")}>\`.`,
          ].join("\n"),
        );
        return;
      }

      if (!valid.includes(scope as Scope)) {
        ctx.ui.notify(`Invalid scope "${scope}". Must be one of: ${valid.join(", ")}`, "warning");
        return;
      }

      config.defaultScope = scope as Scope;
      captureCommandEvent("ume-scope", { scope }, telemetryCtx);
      sendFeedback(
        "ume-scope",
        [
          `**Scope changed to ${scope}**`,
          `New memories now save to the **${scope}** pool for this session.`,
        ].join("\n"),
      );
    },
  });

  pi.registerCommand("ume-status", {
    description: "Show connection health, identity, project, and memory count",
    handler: async (_args, _ctx) => {
      const scopeCtx = getScopeCtx();
      const filters = resolveSearchFilters("project", scopeCtx);

      let count = 0;
      let connected = false;
      try {
        const result = await ume.getAll({ filters });
        count = result.count ?? (result.results ?? []).length;
        connected = true;
      } catch {
        connected = false;
      }

      const lines = [
        "**UME status**",
        "",
        `- Connection: ${connected ? "connected" : "disconnected"}`,
        `- User: ${scopeCtx.userId}`,
        `- Project: ${scopeCtx.appId}`,
        `- Session: ${scopeCtx.runId}`,
        `- Default scope: ${config.defaultScope}`,
        `- Search relevance threshold: ${config.searchThreshold}`,
        `- Project memories: ${count}`,
        `- Auto-capture: ${config.autoCapture ? "on" : "off"}`,
      ];

      captureCommandEvent("ume-status", { connected, memory_count: count }, telemetryCtx);
      sendFeedback("ume-status", lines.join("\n"));
    },
  });
}
