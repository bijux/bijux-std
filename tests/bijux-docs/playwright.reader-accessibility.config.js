const { configureProjects, unsharded } = require("./reporting/projects");
const { defineConfig } = require("@playwright/test");
const path = require("node:path");
const inherited = unsharded(require("./playwright.config"));
const root = path.resolve(process.env.BIJUX_UI_ARTIFACT_ROOT || path.join(__dirname, "../../artifacts/bijux-docs/reader-accessibility"));
const generated = path.resolve(process.env.BIJUX_GENERATED_ROOT || path.join(__dirname, "../../artifacts/bijux-docs/generated"));
const origin = process.env.BIJUX_UI_BASE_URL || "http://127.0.0.1:4173";
const port = new URL(origin).port || "80";
const projects = inherited.projects.filter(project => project.name.endsWith("-phone")).map(project => ({
  ...project, name: `${project.use.browserName}-reader-accessibility`, metadata: { required_case_count: 5 },
}));
module.exports = configureProjects(defineConfig({
  ...inherited,
  testMatch: "**/reader-accessibility.spec.js",
  projects,
  fullyParallel: false,
  workers: 1,
  use: { ...inherited.use, baseURL: origin, trace: "on" },
  outputDir: path.join(root, "test-results"),
  webServer: {
    ...inherited.webServer,
    command: `python3 -m http.server ${port} --bind 127.0.0.1 --directory "${path.join(generated, "site")}"`,
    url: origin,
  },
  reporter: inherited.reporter.map(entry => {
    if (!Array.isArray(entry)) return entry;
    if (String(entry[0]).endsWith("strict-reporter.js")) return [entry[0], {
      ...entry[1], output: path.join(root, "qualification.json"), scope: "reader_accessibility",
      requiredProjects: projects.map(project => project.name),
    }];
    if (entry[0] === "html") return [entry[0], { ...entry[1], outputFolder: path.join(root, "html-report") }];
    if (entry[0] === "junit") return [entry[0], { ...entry[1], outputFile: path.join(root, "junit.xml") }];
    return entry;
  }),
}));
