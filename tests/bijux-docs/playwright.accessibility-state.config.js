const { defineConfig } = require("@playwright/test");
const { configureProjects, unsharded } = require("./reporting/projects");
const inherited = unsharded(require("./playwright.config"));
const projects = ["chromium", "firefox", "webkit"].map(browserName => ({
  name: `${browserName}-accessibility-state`,
  metadata: { required_case_count: 3 },
  use: { browserName, viewport: { width: 1440, height: 900 } },
}));
module.exports = configureProjects(defineConfig({
  ...inherited, testMatch: "**/accessibility-state.spec.js", projects,
  timeout: 90_000,
  reporter: inherited.reporter.map(entry => Array.isArray(entry) && String(entry[0]).endsWith("strict-reporter.js")
    ? [entry[0], { ...entry[1], scope: "accessibility_states", requiredProjects: projects.map(project => project.name) }]
    : entry),
}));
