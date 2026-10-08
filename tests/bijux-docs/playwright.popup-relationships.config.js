const { configureProjects, unsharded } = require("./reporting/projects");
const path = require("node:path");
const { defineConfig } = require("@playwright/test");
const inherited = unsharded(require("./playwright.config"));
const artifactRoot = path.resolve(
  process.env.BIJUX_UI_ARTIFACT_ROOT ||
    path.join(
      __dirname,
      "../../artifacts/bijux-docs/popup-relationships-playwright",
    ),
);
const generatedRoot = path.resolve(
  process.env.BIJUX_GENERATED_ROOT ||
    path.join(__dirname, "../../artifacts/bijux-docs/generated"),
);
const origin =
  process.env.BIJUX_POPUP_RELATIONSHIPS_ORIGIN || "http://127.0.0.1:4173";
const projects = ["chromium", "firefox", "webkit"].map((browserName) => ({
  name: `${browserName}-popup-relationships`,
  metadata: { required_case_count: 4 },
  use: { browserName },
}));
module.exports = configureProjects(defineConfig({
  ...inherited,
  testMatch: "**/popup-relationships.spec.js",
  projects,
  workers: 1,
  fullyParallel: false,
  use: { ...inherited.use, baseURL: origin, trace: "on" },
  outputDir: path.join(artifactRoot, "test-results"),
  webServer: {
    ...inherited.webServer,
    command: `python3 -m http.server ${new URL(origin).port} --bind 127.0.0.1 --directory "${path.join(generatedRoot, "site")}"`,
    url: `${origin}/`,
  },
  reporter: inherited.reporter.map((entry) => {
    if (!Array.isArray(entry)) return entry;
    if (String(entry[0]).endsWith("strict-reporter.js"))
      return [
        entry[0],
        {
          ...entry[1],
          generatedRoot,
          output: path.join(artifactRoot, "qualification.json"),
          scope: "popup_relationships",
          requiredProjects: projects.map((project) => project.name),
        },
      ];
    if (entry[0] === "html")
      return [
        entry[0],
        { ...entry[1], outputFolder: path.join(artifactRoot, "html-report") },
      ];
    if (entry[0] === "junit")
      return [
        entry[0],
        { ...entry[1], outputFile: path.join(artifactRoot, "junit.xml") },
      ];
    return entry;
  }),
}));
