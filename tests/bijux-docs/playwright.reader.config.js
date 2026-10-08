const { defineConfig } = require("@playwright/test"),
  path = require("node:path");
const inherited = require("./playwright.config");
const artifactRoot = path.resolve(
  process.env.BIJUX_UI_ARTIFACT_ROOT ||
    path.join(__dirname, "../../artifacts/bijux-docs/reader-playwright"),
);
const projects = inherited.projects
  .filter((project) => project.name.endsWith("-phone"))
  .map((project) => ({
    ...project,
    name: `${project.use.browserName}-reader`,
    metadata: { required_case_count: 12 },
  }));
module.exports = defineConfig({
  ...inherited,
  testMatch: "**/reader-reflow.spec.js",
  projects,
  fullyParallel: false,
  workers: 1,
  use: { ...inherited.use, trace: "on" },
  outputDir: path.join(artifactRoot, "test-results"),
  reporter: inherited.reporter.map((entry) => {
    if (!Array.isArray(entry)) return entry;
    if (String(entry[0]).endsWith("strict-reporter.js"))
      return [
        entry[0],
        {
          ...entry[1],
          output: path.join(artifactRoot, "qualification.json"),
          scope: "reader_reflow",
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
});
