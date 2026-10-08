const { defineConfig } = require("@playwright/test");
const inherited = require("./playwright.config");
const projects = inherited.projects.filter(project => project.name.endsWith("-phone")).map(project => ({ ...project, metadata: { required_case_count: 2 } }));
module.exports = defineConfig({
  ...inherited,
  testMatch: "**/repository.spec.js",
  projects,
  reporter: inherited.reporter.map(entry => Array.isArray(entry) && String(entry[0]).endsWith("strict-reporter.js") ? [entry[0], { ...entry[1], scope: "optional_repository_facts", requiredProjects: projects.map(project => project.name) }] : entry),
});
