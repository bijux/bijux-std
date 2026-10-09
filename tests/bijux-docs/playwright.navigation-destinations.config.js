const { configureProjects, unsharded } = require("./reporting/projects");
const { defineConfig } = require("@playwright/test");
const inherited = unsharded(require("./playwright.config"));
const projects = inherited.projects.filter(project => project.name.endsWith("-phone")).map(project => ({
  ...project, metadata: { required_case_count: 3 },
}));
module.exports = configureProjects(defineConfig({
  ...inherited, testMatch: "**/authored-navigation-destinations.spec.js", projects,
  workers: 1,
  fullyParallel: false,
  use: { ...inherited.use, trace: "on" },
  reporter: inherited.reporter.map(entry =>
    Array.isArray(entry) && String(entry[0]).endsWith("strict-reporter.js")
      ? [entry[0], { ...entry[1], scope: "authored_navigation_destinations", requiredProjects: projects.map(project => project.name) }]
      : entry,
  ),
}));
