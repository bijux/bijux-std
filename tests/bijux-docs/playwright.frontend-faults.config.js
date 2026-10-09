const { defineConfig } = require("@playwright/test");
const { configureProjects, unsharded } = require("./reporting/projects");
const inherited = unsharded(require("./playwright.config"));
const projects = inherited.projects.filter(project => project.name.endsWith("-phone"))
  .map(project => ({...project, metadata:{required_case_count:4}}));
module.exports = configureProjects(defineConfig({...inherited, workers:1,
  testMatch:"**/frontend-faults.spec.js", projects,
  reporter:inherited.reporter.map(entry => Array.isArray(entry) && String(entry[0]).endsWith("strict-reporter.js")
    ? [entry[0], {...entry[1],scope:"frontend_fault_gate", requiredProjects:projects.map(project=>project.name)}] : entry),
}));
