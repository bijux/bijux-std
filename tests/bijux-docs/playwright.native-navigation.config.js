const { configureProjects, unsharded } = require("./reporting/projects");
const { defineConfig } = require("@playwright/test");
const path = require("path");
const inherited = unsharded(require("./playwright.config"));
const artifactRoot = path.resolve(process.env.BIJUX_UI_ARTIFACT_ROOT || path.join(__dirname, "../../artifacts/bijux-docs/native-navigation-playwright"));
const projects = inherited.projects.filter(project => project.name.endsWith("-phone")).map(project => ({ ...project, name: `${project.use.browserName}-native-navigation`, metadata: { required_case_count: 12 } }));
module.exports = configureProjects(defineConfig({
  ...inherited,
  testMatch: "**/native-navigation.spec.js",
  projects, fullyParallel: false, workers: 1,
  use: { ...inherited.use, trace: "on" },
  outputDir: path.join(artifactRoot, "test-results"),
  reporter: inherited.reporter.map(entry => {
    if (!Array.isArray(entry)) return entry;
    if (String(entry[0]).endsWith("strict-reporter.js")) return [entry[0], { ...entry[1], output: path.join(artifactRoot, "qualification.json"), scope: "native_navigation_fallback", requiredProjects: projects.map(project => project.name) }];
    if (entry[0] === "html") return [entry[0], { ...entry[1], outputFolder: path.join(artifactRoot, "html-report") }];
    if (entry[0] === "junit") return [entry[0], { ...entry[1], outputFile: path.join(artifactRoot, "junit.xml") }];
    return entry;
  }),
}));
