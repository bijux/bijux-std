const { configureProjects, unsharded } = require("./reporting/projects");
const { defineConfig } = require("@playwright/test");
const path = require("node:path");
const inherited = unsharded(require("./playwright.config"));
const artifactRoot = path.resolve(
  process.env.BIJUX_UI_ARTIFACT_ROOT ||
    path.join(__dirname, "../../artifacts/bijux-docs/content-playwright"),
);
const projects = inherited.projects.map(project => ({
  ...project,
  metadata: { required_case_count: 1 },
}));
module.exports = configureProjects(defineConfig({
  ...inherited,
  testMatch: "**/shell.spec.js",
  grep: /rich content renders actual Material enhancements$/,
  projects,
  workers: 1,
  fullyParallel: false,
  use: { ...inherited.use, trace: "on" },
  outputDir: path.join(artifactRoot, "test-results"),
  reporter: inherited.reporter.map(entry => {
    if (!Array.isArray(entry)) return entry;
    if (String(entry[0]).endsWith("strict-reporter.js"))
      return [entry[0], { ...entry[1], output: path.join(artifactRoot, "qualification.json"), scope: "authored_content", requiredProjects: projects.map(project => project.name) }];
    if (entry[0] === "html")
      return [entry[0], { ...entry[1], outputFolder: path.join(artifactRoot, "html-report") }];
    if (entry[0] === "junit")
      return [entry[0], { ...entry[1], outputFile: path.join(artifactRoot, "junit.xml") }];
    return entry;
  }),
}));
