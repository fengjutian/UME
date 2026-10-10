import { describe, expect, it } from "vitest";
import { applySurfaceHeaders, PLATFORM_APPLICATION, PLATFORM_SOURCE } from "./attribution.ts";

function client(headers: Record<string, string> = {}) {
  return { headers: { Authorization: "Token k", ...headers } } as never;
}

describe("applySurfaceHeaders", () => {
  it("stamps the shared client so every path is attributed, not just commands", () => {
    const ume = client();
    applySurfaceHeaders(ume);
    const headers = (ume as unknown as { headers: Record<string, string> }).headers;

    expect(headers["X-UME-Source"]).toBe(PLATFORM_SOURCE);
    expect(headers["X-Application"]).toBe(PLATFORM_APPLICATION);
    expect(headers["X-UME-Client"]).toMatch(/^ume-pi-agent\//);
    expect(headers.Authorization).toBe("Token k");
  });

  it("defers to a surface an outer wrapper already declared", () => {
    const ume = client({ "X-UME-Source": "OPENCLAW", "X-Application": "vscode" });
    applySurfaceHeaders(ume);
    const headers = (ume as unknown as { headers: Record<string, string> }).headers;

    expect(headers["X-UME-Source"]).toBe("OPENCLAW");
    expect(headers["X-Application"]).toBe("vscode");
  });

  it("appends to the client stack rather than replacing it", () => {
    const ume = client({ "X-UME-Client": "openclaw/2.1.0" });
    applySurfaceHeaders(ume);
    const headers = (ume as unknown as { headers: Record<string, string> }).headers;

    expect(headers["X-UME-Client"]).toMatch(/^openclaw\/2\.1\.0, ume-pi-agent\//);
  });

  it("treats a blank header as absent", () => {
    const ume = client({ "X-UME-Source": "   " });
    applySurfaceHeaders(ume);
    const headers = (ume as unknown as { headers: Record<string, string> }).headers;

    expect(headers["X-UME-Source"]).toBe(PLATFORM_SOURCE);
  });

  it("bounds the stack so a long chain cannot grow the header without limit", () => {
    const ume = client({ "X-UME-Client": "a/1, b/1, c/1, d/1, e/1" });
    applySurfaceHeaders(ume);
    const headers = (ume as unknown as { headers: Record<string, string> }).headers;

    expect(headers["X-UME-Client"].split(",").length).toBeLessThanOrEqual(4);
    expect(headers["X-UME-Client"].length).toBeLessThanOrEqual(200);
  });
});

describe("client stack bounding", () => {
  it("keeps our own entry when the caller already filled the stack", () => {
    // The defect: pushing then trimming to four dropped exactly the entry this
    // function exists to add, so we vanished from our own stack.
    const ume = client({ "X-UME-Client": "a/1, b/2, c/3, d/4" });
    applySurfaceHeaders(ume);
    const stack = (ume as unknown as { headers: Record<string, string> }).headers["X-UME-Client"];

    expect(stack).toMatch(/ume-pi-agent\//);
    expect(stack.split(",").length).toBeLessThanOrEqual(4);
  });

  it("drops whole entries at the character cap, never a fragment", () => {
    const long = `${"n".repeat(90)}/1.0, ${"m".repeat(90)}/1.0, ${"o".repeat(90)}/1.0`;
    const ume = client({ "X-UME-Client": long });
    applySurfaceHeaders(ume);
    const stack = (ume as unknown as { headers: Record<string, string> }).headers["X-UME-Client"];

    expect(stack.length).toBeLessThanOrEqual(200);
    expect(stack.endsWith("/0.0.0") || /ume-pi-agent\/[\w.\-]+$/.test(stack)).toBe(true);
    // Every surviving entry is whole: name/version, no severed tail.
    for (const entry of stack.split(",")) {
      expect(entry.trim()).toMatch(/^[^/]+\/[^/]+$/);
    }
  });
});
