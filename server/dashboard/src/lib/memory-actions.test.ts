import { describe, expect, it } from "vitest";
import { allowedActions, memoryStatusNote } from "@/lib/memory-actions";

/**
 * These mirror the server's guards in `ume_app/services/memories.py`. They are
 * not the authority — every call is re-checked server-side and a mismatch
 * surfaces as a 409 — but a page that offers an impossible action is a bug
 * worth failing a build over.
 */
const memory = (status: string, engine_state = "ready") => ({
  status,
  engine_state,
  engine_error: null,
});

describe("allowedActions", () => {
  it("allows edit and archive on an active record", () => {
    expect(allowedActions(memory("active"))).toMatchObject({
      edit: true,
      archive: true,
      restoreVersion: false,
      retryEngine: false,
    });
  });

  it("allows restore but not archive on an archived record", () => {
    // The server: archive requires status == active, restore requires archived.
    expect(allowedActions(memory("archived"))).toMatchObject({
      edit: true,
      archive: false,
      restoreVersion: true,
    });
  });

  it("denies archive and restore on a deleted record", () => {
    expect(allowedActions(memory("deleted"))).toMatchObject({
      edit: false,
      archive: false,
      restoreVersion: false,
    });
  });

  it("still allows forget on a deleted record, which the server rejects", () => {
    // Deliberately left true: `forget` is the one action whose guard is
    // `status != deleted`, so a deleted row is the single case it must refuse.
    expect(allowedActions(memory("deleted")).forget).toBe(false);
  });

  it("offers retry only for a failed engine write", () => {
    // The server: retrying a `ready` record would create a second engine memory.
    expect(allowedActions(memory("active", "failed")).retryEngine).toBe(true);
    expect(allowedActions(memory("active", "ready")).retryEngine).toBe(false);
    expect(allowedActions(memory("active", "pending")).retryEngine).toBe(false);
    expect(allowedActions(memory("active", "deleting")).retryEngine).toBe(
      false,
    );
  });

  it("denies every action it does not recognise rather than guessing", () => {
    // A status the server adds later must not light up buttons here.
    expect(allowedActions(memory("quarantined"))).toEqual({
      edit: false,
      archive: false,
      restoreVersion: false,
      forget: true,
      retryEngine: false,
    });
  });
});

describe("memoryStatusNote", () => {
  it("surfaces the engine error text on a failed write", () => {
    const note = memoryStatusNote({
      status: "active",
      engine_state: "failed",
      engine_error: "upstream 401",
    });
    expect(note?.label).toBe("Engine write failed");
    expect(note?.detail).toBe("upstream 401");
  });

  it("still says something useful when the failure carries no message", () => {
    const note = memoryStatusNote({
      status: "active",
      engine_state: "failed",
      engine_error: null,
    });
    expect(note?.detail).toBeTruthy();
  });

  it("returns null for a healthy active record", () => {
    expect(memoryStatusNote(memory("active"))).toBeNull();
  });

  it("marks a tombstone as deleted", () => {
    const note = memoryStatusNote(memory("deleted"));
    expect(note?.label).toBe("Deleted");
  });

  it("notes that an archived record is retained, not erased", () => {
    const note = memoryStatusNote(memory("archived"));
    expect(note?.label).toBe("Archived");
    expect(note?.detail).toMatch(/retained/i);
  });
});
