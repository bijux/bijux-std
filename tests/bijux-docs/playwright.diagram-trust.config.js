const { defineConfig } = require("@playwright/test");
const { configureProjects, unsharded } = require("./reporting/projects");
const inherited = unsharded(require("./playwright.config"));
const projects = ["chromium", "firefox", "webkit"].map(browserName => ({
  name: `${browserName}-diagram-trust`,
  metadata: { required_case_count: 3 },
  use: { browserName, viewport: { width: 1440, height: 900 } },
}));
module.exports = configureProjects(defineConfig({
  ...inherited, testMatch: "**/diagram-trust.spec.js", projects,
  reporter: inherited.reporter.map(entry => Array.isArray(entry) && String(entry[0]).endsWith("strict-reporter.js")
    ? [entry[0], { ...entry[1], scope: "diagram_trust_boundaries", requiredProjects: projects.map(project => project.name) }]
    : entry),
}));
