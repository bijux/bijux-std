const path = require("path");
const { defineConfig } = require("@playwright/test");

const repoRoot = path.resolve(__dirname, "..");

module.exports = defineConfig({
  testDir: path.join(__dirname, "ui", "specs"),
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: true,
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4173",
    headless: true,
  },
  webServer: {
    command: "python3 -m http.server 4173 --bind 127.0.0.1 -d .",
    cwd: repoRoot,
    port: 4173,
    reuseExistingServer: true,
    timeout: 30_000,
  },
  projects: [
    {
      name: "phone",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
      },
    },
    {
      name: "normal",
      use: {
        viewport: { width: 1024, height: 900 },
      },
    },
    {
      name: "wide",
      use: {
        viewport: { width: 1920, height: 1080 },
      },
    },
  ],
});
