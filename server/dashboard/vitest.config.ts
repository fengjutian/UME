import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

/**
 * Node environment on purpose: everything under test here is a pure function —
 * URL building, query construction, envelope unwrapping and error mapping.
 * Nothing needs a DOM, and adding one would let a test pass on a jsdom
 * behaviour that the browser does not have.
 *
 * The `@/` alias mirrors tsconfig.json's `paths` so the modules under test can
 * keep importing each other exactly as the app does.
 */
export default defineConfig({
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});