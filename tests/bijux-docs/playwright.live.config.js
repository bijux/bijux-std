const path = require("path");
const { defineConfig } = require("@playwright/test");
const base = require("./playwright.config");
if (process.env.BIJUX_LIVE_E2E !== "1") throw new Error("Read-only live qualification requires BIJUX_LIVE_E2E=1; no skipped green live suite");
const root = path.resolve(__dirname, "../../artifacts/bijux-docs/live");
module.exports = defineConfig({
  ...base,
  testMatch: "**/*.spec.js",
  projects: base.projects.map(project => ({ ...project, metadata: { required_case_count: 3 } })),
  testDir: path.join(__dirname, "ui/live-specs"),
  outputDir: path.join(root, "test-results"),
  webServer: undefined,
  use: { ...base.use, baseURL: process.env.BIJUX_LIVE_HUB_URL || "https://bijux.io/" },
  reporter: [
    ["list"],
    [path.join(__dirname, "generated/strict-reporter.js"), { output: path.join(root, "qualification.json"), liveBaseUrl: process.env.BIJUX_LIVE_HUB_URL || "https://bijux.io/" }],
    ["html", { open: "never", outputFolder: path.join(root, "html-report") }],
  ],
});
