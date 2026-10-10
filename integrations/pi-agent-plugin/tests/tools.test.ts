import { describe, it, expect, vi } from "vitest";
import { buildToolExecute } from "../src/memory/tools.ts";
import type { ScopeContext } from "../src/types.ts";

const mockUME = {
  search: vi.fn(),
  add: vi.fn(),
  getAll: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
  deleteAll: vi.fn(),
};

const scopeCtx: ScopeContext = {
  userId: "testuser",
  appId: "testproject",
  runId: "session123",
};

describe("buildToolExecute", () => {
  const execute = buildToolExecute(mockUME as any, scopeCtx, "project");

  it("search calls ume.search with correct filters", async () => {
    mockUME.search.mockResolvedValue({ results: [] });
    await execute({ action: "search", query: "dark mode" });
    expect(mockUME.search).toHaveBeenCalledWith("dark mode", {
      filters: { user_id: "testuser", app_id: "testproject" },
    });
  });

  it("add calls ume.add with customCategories and entity params", async () => {
    mockUME.add.mockResolvedValue([{ id: "new-id", memory: "test" }]);
    await execute({ action: "add", content: "User likes tabs" });
    const call = mockUME.add.mock.calls[0];
    expect(call[0]).toEqual([{ role: "user", content: "User likes tabs" }]);
    expect(call[1].userId).toBe("testuser");
    expect(call[1].appId).toBe("testproject");
    expect(call[1].customCategories).toBeDefined();
    expect(call[1].customCategories.length).toBe(10);
  });

  it("search uses global scope only after the user selects it", async () => {
    mockUME.search.mockResolvedValue({ results: [] });
    await expect(execute({ action: "search", query: "preferences", scope: "global" })).rejects.toThrow(/Select global/);
    const globalExecute = buildToolExecute(mockUME as any, scopeCtx, "global");
    await globalExecute({ action: "search", query: "preferences", scope: "global" });
    expect(mockUME.search).toHaveBeenCalledWith("preferences", {
      filters: { user_id: "testuser" },
    });
  });

  it("delete calls ume.delete with full memory_id", async () => {
    mockUME.delete.mockResolvedValue({ message: "deleted" });
    await execute({ action: "delete", memory_id: "abc12345-6789-0abc-def0-123456789abc" });
    expect(mockUME.delete).toHaveBeenCalledWith("abc12345-6789-0abc-def0-123456789abc");
  });

  it("delete passes memory_id directly to ume.delete", async () => {
    const fullId = "956e3d68-b420-4e07-a4e3-3019e7cebe6f";
    mockUME.delete.mockResolvedValue({ message: "deleted" });
    await execute({ action: "delete", memory_id: fullId });
    expect(mockUME.delete).toHaveBeenCalledWith(fullId);
  });

  it("write actions accept the citation ID returned by search", async () => {
    mockUME.update.mockResolvedValue({ status: "updated" });
    mockUME.delete.mockResolvedValue({ message: "deleted" });
    await execute({
      action: "update",
      memory_id: "[ume:956e3d68-b420-4e07-a4e3-3019e7cebe6f]",
      content: "updated memory",
    });
    await execute({ action: "delete", memory_id: "ume:956e3d68-b420-4e07-a4e3-3019e7cebe6f" });
    expect(mockUME.update).toHaveBeenLastCalledWith("956e3d68-b420-4e07-a4e3-3019e7cebe6f", {
      text: "updated memory",
    });
    expect(mockUME.delete).toHaveBeenLastCalledWith("956e3d68-b420-4e07-a4e3-3019e7cebe6f");
  });
});
