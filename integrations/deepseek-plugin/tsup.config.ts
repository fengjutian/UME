import { defineConfig } from "tsup";

export default defineConfig({
  entry: ["src/index.ts"],
  format: ["esm"],
  dts: true,
  sourcemap: true,
  clean: true,
  // The harness runtime and the UME SDK are provided by the host / installed
  // separately; keep them out of the bundle.
  external: [/^node:/, /^@deepseek-ai\//, "ume", /^ume\//],
});
