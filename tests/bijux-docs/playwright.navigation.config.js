const { configureProjects, unsharded } = require("./reporting/projects");
const { defineConfig } = require("@playwright/test");
const inherited = unsharded(require("./playwright.config"));
module.exports = configureProjects(defineConfig(inherited, {
  reporter: inherited.reporter.map(entry => Array.isArray(entry) && String(entry[0]).endsWith("strict-reporter.js") ? [entry[0], { ...entry[1], scope: "responsive_navigation" }] : entry),
  testMatch: "**/shell.spec.js",
  grepInvert: /rich content renders|all declared consumer roots/,
  projects: inherited.projects.map(project => ({ ...project, metadata: { required_case_count: 14 } })),
}));
