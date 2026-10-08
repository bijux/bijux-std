const path = require("path");
const { defineConfig } = require("@playwright/test");
const repoRoot = path.resolve(__dirname, "../..");
const artifactRoot = path.resolve(process.env.BIJUX_UI_ARTIFACT_ROOT || path.join(repoRoot, "artifacts/bijux-docs/playwright"));
const generatedRoot = path.resolve(process.env.BIJUX_GENERATED_ROOT || path.join(repoRoot, "artifacts/bijux-docs/generated"));
const profiles = {
  phone: { viewport: { width: 390, height: 844 }, hasTouch: true },
  compact: { viewport: { width: 768, height: 900 } },
  desktop: { viewport: { width: 1440, height: 900 } },
};
module.exports = defineConfig({
  testDir: path.join(__dirname, "ui/generated-specs"),
  testMatch: "**/shell.spec.js",
  outputDir: path.join(artifactRoot, "test-results"),
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  workers: 3,
  retries: 0,
  reporter: [
    ["list"],
    [path.join(__dirname, "generated/strict-reporter.js"), { output: path.join(artifactRoot, "qualification.json"), generatedRoot }],
    ["html", { open: "never", outputFolder: path.join(artifactRoot, "html-report") }],
    ["junit", { outputFile: path.join(artifactRoot, "junit.xml") }],
  ],
  use: { baseURL: "http://127.0.0.1:4173", headless: true, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: {
    command: `python3 -m http.server 4173 --bind 127.0.0.1 --directory "${path.join(generatedRoot, "site")}"`,
    cwd: repoRoot,
    url: "http://127.0.0.1:4173/",
    reuseExistingServer: false,
    timeout: 15_000,
    stdout: "ignore", stderr: "ignore",
  },
  projects: ["chromium", "firefox", "webkit"].flatMap((browserName) =>
    Object.entries(profiles).map(([profile, settings]) => ({ name: `${browserName}-${profile}`, metadata: { required_case_count: 16 }, use: { browserName, ...settings } }))
  ),
});
