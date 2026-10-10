import { describe, it, expect, vi, beforeEach } from "vitest";
import { registerCommands } from "./commands.ts";
import type { UMEConfig, ScopeContext } from "./types.ts";

vi.mock("./telemetry.ts", () => ({
  captureCommandEvent: vi.fn(),
}));

function makeUME() {
  return {
    search: vi.fn(),
    delete: vi.fn(),
    add: vi.fn(),
    get: vi.fn(),
    getAll: vi.fn(),
    update: vi.fn(),
  } as any;
}

function makePi() {
  const commands = new Map<string, { handler: (args: string, ctx: any) => Promise<void> }>();
  return {
    registerCommand: vi.fn((name: string, opts: any) => {
      commands.set(name, opts);
    }),
    sendMessage: vi.fn(),
    _commands: commands,
    _invoke: (name: string, args: string, ctx: any) => commands.get(name)!.handler(args, ctx),
  };
}

function makeCtx(confirmResult = true) {
  return {
    hasUI: true,
    ui: {
      notify: vi.fn(),
      confirm: vi.fn(async () => confirmResult),
      select: vi.fn(),
      input: vi.fn(),
    },
  };
}

const defaultConfig: UMEConfig = {
  apiKey: "test-key",
  userId: "test-user",
  autoCapture: false,
  defaultScope: "project",
  contextInjection: false,
  searchThreshold: 0.3,
};

const scopeCtx: ScopeContext = { userId: "test-user", appId: "test-app", runId: "test-run" };

describe("registerCommands", () => {
  let pi: ReturnType<typeof makePi>;
  let ume: ReturnType<typeof makeUME>;

  beforeEach(() => {
    pi = makePi();
    ume = makeUME();
    defaultConfig.defaultScope = "project";
    registerCommands(pi as any, ume, defaultConfig, () => scopeCtx);
  });

  it("registers all expected commands", () => {
    const names = [...pi._commands.keys()];
    expect(names).toEqual([
      "ume-remember",
      "ume-forget",
      "ume-search",
      "ume-tour",
      "ume-scope",
      "ume-status",
    ]);
  });

  describe("/ume-forget", () => {
    it("shows warning when no query provided", async () => {
      const ctx = makeCtx();
      await pi._invoke("ume-forget", "", ctx);
      expect(ctx.ui.notify).toHaveBeenCalledWith("Usage: /ume-forget <query>", "warning");
      expect(ume.search).not.toHaveBeenCalled();
    });

    it("sends a visible message naming the query when no memories match", async () => {
      const ctx = makeCtx();
      ume.search.mockResolvedValue({ results: [] });
      await pi._invoke("ume-forget", "old preference", ctx);
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "ume-forget",
          content: expect.stringContaining('No matches for "old preference"'),
          display: true,
        }),
      );
    });

    it("asks for confirmation before deleting a single match", async () => {
      const ctx = makeCtx(true);
      ume.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "test mem" }] });
      ume.delete.mockResolvedValue({ message: "Deleted" });

      await pi._invoke("ume-forget", "test", ctx);

      expect(ctx.ui.confirm).toHaveBeenCalledWith(
        "Delete this memory?",
        expect.stringContaining("test mem"),
      );
      expect(ume.delete).toHaveBeenCalledWith("abc-123");
    });

    it("sends a visible confirmation showing what was forgotten", async () => {
      const ctx = makeCtx(true);
      ume.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "test mem" }] });
      ume.delete.mockResolvedValue({ message: "Deleted" });

      await pi._invoke("ume-forget", "test", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "ume-forget",
          content: expect.stringContaining("Forgotten"),
          display: true,
        }),
      );
    });

    it("does not delete when user cancels confirmation", async () => {
      const ctx = makeCtx(false);
      ume.search.mockResolvedValue({ results: [{ id: "abc-123", memory: "test mem" }] });

      await pi._invoke("ume-forget", "test", ctx);

      expect(ctx.ui.confirm).toHaveBeenCalled();
      expect(ume.delete).not.toHaveBeenCalled();
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("Cancelled"), display: true }),
      );
    });

    it("uses select UI for multiple matches and deletes chosen memory", async () => {
      const ctx = makeCtx();
      ume.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "mem one" },
          { id: "id-2", memory: "mem two" },
        ],
      });
      ume.delete.mockResolvedValue({ message: "Deleted" });
      ctx.ui.select = vi.fn(async (_title: string, options: string[]) => options[1]);

      await pi._invoke("ume-forget", "test", ctx);

      expect(ctx.ui.select).toHaveBeenCalledWith(
        expect.stringContaining("which should I delete"),
        expect.arrayContaining([
          expect.stringContaining("mem one"),
          expect.stringContaining("mem two"),
        ]),
      );
      expect(ume.delete).toHaveBeenCalledWith("id-2");
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "ume-forget",
          content: expect.stringContaining("Forgotten"),
          display: true,
        }),
      );
    });

    it("does not delete when user cancels select", async () => {
      const ctx = makeCtx();
      ctx.ui.select = vi.fn(async () => undefined);
      ume.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "mem one" },
          { id: "id-2", memory: "mem two" },
        ],
      });

      await pi._invoke("ume-forget", "test", ctx);

      expect(ume.delete).not.toHaveBeenCalled();
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("Cancelled"), display: true }),
      );
    });
  });

  describe("/ume-search", () => {
    it("performs server-side semantic search with a relevance threshold", async () => {
      const ctx = makeCtx();
      ume.search.mockResolvedValue({ results: [{ id: "id-1", memory: "result" }] });

      await pi._invoke("ume-search", "my preferences", ctx);

      expect(ume.search).toHaveBeenCalledWith(
        "my preferences",
        expect.objectContaining({ threshold: 0.3, topK: 10, rerank: true }),
      );
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ customType: "ume-search" }),
      );
    });

    it("uses semantic search even for hex-looking strings", async () => {
      const ctx = makeCtx();
      ume.search.mockResolvedValue({ results: [] });

      await pi._invoke("ume-search", "abcd1234", ctx);

      expect(ume.search).toHaveBeenCalledWith("abcd1234", expect.any(Object));
      expect(ume.getAll).not.toHaveBeenCalled();
      expect(ume.get).not.toHaveBeenCalled();
    });

    it("shows a no-matches message naming the query", async () => {
      const ctx = makeCtx();
      ume.search.mockResolvedValue({ results: [] });

      await pi._invoke("ume-search", "nonexistent", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("No matches") }),
      );
    });

    it("shows a result count header when there are matches", async () => {
      const ctx = makeCtx();
      ume.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "one" },
          { id: "id-2", memory: "two" },
        ],
      });

      await pi._invoke("ume-search", "stuff", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({ content: expect.stringContaining("2 matches") }),
      );
    });

    it("shows all results the API returns (relevance gating is server-side)", async () => {
      const ctx = makeCtx();
      ume.search.mockResolvedValue({
        results: [
          { id: "id-1", memory: "first match", score: 0.62 },
          { id: "id-2", memory: "second match", score: 0.31 },
        ],
      });

      await pi._invoke("ume-search", "stuff", ctx);

      const call = pi.sendMessage.mock.calls.find(([m]: any[]) => m.customType === "ume-search");
      expect(call?.[0].content).toContain("first match");
      expect(call?.[0].content).toContain("second match");
      expect(call?.[0].content).toContain("2 matches");
    });
  });

  describe("/ume-remember", () => {
    it("stores a memory verbatim", async () => {
      const ctx = makeCtx();
      ume.add.mockResolvedValue({ message: "Memory stored." });

      await pi._invoke("ume-remember", "I prefer dark mode", ctx);

      expect(ume.add).toHaveBeenCalledWith(
        [{ role: "user", content: "I prefer dark mode" }],
        expect.objectContaining({ infer: false }),
      );
    });

    it("shows the stored text in a visible confirmation (infer:false status response)", async () => {
      const ctx = makeCtx();
      ume.add.mockResolvedValue({ message: "Memories stored successfully" });

      await pi._invoke("ume-remember", "I prefer dark mode", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "ume-remember",
          content: expect.stringContaining("I prefer dark mode"),
          display: true,
        }),
      );
    });

    it("lists memory objects returned by the API when present", async () => {
      const ctx = makeCtx();
      ume.add.mockResolvedValue([{ id: "m1", memory: "Uses dark mode", event: "ADD" }]);

      await pi._invoke("ume-remember", "I prefer dark mode", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "ume-remember",
          content: expect.stringContaining("Uses dark mode"),
          display: true,
        }),
      );
    });

    it("shows warning when no text provided", async () => {
      const ctx = makeCtx();
      await pi._invoke("ume-remember", "  ", ctx);
      expect(ctx.ui.notify).toHaveBeenCalledWith("Usage: /ume-remember <text>", "warning");
    });
  });

  describe("/ume-scope", () => {
    it("sends a visible message showing the current scope when no arg is given", async () => {
      const ctx = makeCtx();
      await pi._invoke("ume-scope", "", ctx);
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "ume-scope",
          content: expect.stringContaining("Current scope:"),
          display: true,
        }),
      );
    });

    it("sends a visible confirmation after changing scope", async () => {
      const ctx = makeCtx();
      await pi._invoke("ume-scope", "global", ctx);
      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "ume-scope",
          content: expect.stringContaining("Scope changed to global"),
          display: true,
        }),
      );
    });

    it("warns on an invalid scope", async () => {
      const ctx = makeCtx();
      await pi._invoke("ume-scope", "bogus", ctx);
      expect(ctx.ui.notify).toHaveBeenCalledWith(
        expect.stringContaining('Invalid scope "bogus"'),
        "warning",
      );
    });
  });

  describe("/ume-tour", () => {
    it("shows an empty-state message when there are no memories", async () => {
      const ctx = makeCtx();
      ume.getAll.mockResolvedValue({ results: [] });

      await pi._invoke("ume-tour", "", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "ume-tour",
          content: expect.stringContaining("No memories"),
          display: true,
        }),
      );
    });

    it("groups memories by category with a count header", async () => {
      const ctx = makeCtx();
      ume.getAll.mockResolvedValue({
        results: [
          { id: "id-1", memory: "likes tea", categories: ["preferences"] },
          { id: "id-2", memory: "uses vim", categories: ["technical"] },
        ],
      });

      await pi._invoke("ume-tour", "", ctx);

      expect(pi.sendMessage).toHaveBeenCalledWith(
        expect.objectContaining({
          customType: "ume-tour",
          content: expect.stringContaining("Memory tour"),
          display: true,
        }),
      );
    });
  });

});
