"use strict";
const { configureProjects, unsharded } = require("./reporting/projects");
const path = require("node:path");
const { defineConfig } = require("@playwright/test");
const inherited = unsharded(require("./playwright.config"));
const root = path.resolve(__dirname, "../..");
const generatedRoot = path.resolve(process.env.BIJUX_GENERATED_ROOT || path.join(root, "artifacts/bijux-docs/contrast-generated"));
const artifactRoot = path.resolve(process.env.BIJUX_UI_ARTIFACT_ROOT || path.join(root, "artifacts/bijux-docs/contrast-playwright"));
const projects = inherited.projects.map(project => ({ ...project,
  testMatch: project.name.endsWith("-phone") ? ["**/contrast-targets.spec.js", "**/contrast-native-focus.spec.js"] : "**/contrast-targets.spec.js",
  metadata: { required_case_count: project.name.endsWith("-phone") ? 5 : 4 } }));
module.exports = configureProjects(defineConfig({ ...inherited, testMatch: "**/contrast*.spec.js", projects,
  fullyParallel: false, workers: 1,
  use: { ...inherited.use, baseURL: "http://127.0.0.1:62599", trace: "on" },
  webServer: { ...inherited.webServer,
    command: `python3 -m http.server 62599 --bind 127.0.0.1 --directory "${path.join(generatedRoot, "site")}"`,
    url: "http://127.0.0.1:62599/" },
  outputDir: path.join(artifactRoot, "test-results"),
  reporter: inherited.reporter.map(entry => {
    if (!Array.isArray(entry)) return entry;
    if (String(entry[0]).endsWith("strict-reporter.js")) return [entry[0], { ...entry[1], generatedRoot,
      output: path.join(artifactRoot, "qualification.json"), scope: "shared_contrast_targets", requiredProjects: projects.map(project => project.name) }];
    if (entry[0] === "html") return [entry[0], { ...entry[1], outputFolder: path.join(artifactRoot, "html-report") }];
    if (entry[0] === "junit") return [entry[0], { ...entry[1], outputFile: path.join(artifactRoot, "junit.xml") }];
    return entry;
  }),
}));
