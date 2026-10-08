const { configureProjects, unsharded } = require("../../reporting/projects");
const { defineConfig } = require("@playwright/test");
const path = require("node:path");
module.exports = function searchReflowConfig(group) {
  const inherited = unsharded(require("../../playwright.config"));
  const artifactRoot = path.resolve(process.env.BIJUX_UI_ARTIFACT_ROOT || path.join(__dirname, `../../../../artifacts/bijux-docs/search-reflow-${group}-playwright`));
  const baseURL = process.env.BIJUX_SEARCH_REFLOW_BASE_URL || inherited.use.baseURL;
  const origin = new URL(baseURL);
  if (origin.protocol !== "http:" || origin.hostname !== "127.0.0.1" || !origin.port || origin.pathname !== "/" || origin.search || origin.hash) throw new Error("Search reflow fixture origin must be a loopback HTTP origin");
  const projects = inherited.projects.filter(project => project.name.endsWith("-compact")).map(project => ({ ...project, name: `${project.use.browserName}-search-reflow-${group}`, metadata: { required_case_count: 3 } }));
  return configureProjects(defineConfig({
    ...inherited,
    testMatch: `**/search-reflow-${group}.spec.js`,
    projects,
    fullyParallel: true,
    workers: 1,
    timeout: 60_000,
    use: { ...inherited.use, baseURL },
    webServer: { ...inherited.webServer,
      command: inherited.webServer.command.replace("http.server 4173", `http.server ${origin.port}`),
      url: `${origin.origin}/`,
    },
    outputDir: path.join(artifactRoot, "test-results"),
    reporter: inherited.reporter.map(entry => {
      if (!Array.isArray(entry)) return entry;
      if (String(entry[0]).endsWith("strict-reporter.js")) return [entry[0], { ...entry[1], output: path.join(artifactRoot, "qualification.json"), scope: `native_search_viewport_reflow_${group}`, requiredProjects: projects.map(project => project.name) }];
      if (entry[0] === "html") return [entry[0], { ...entry[1], outputFolder: path.join(artifactRoot, "html-report") }];
      if (entry[0] === "junit") return [entry[0], { ...entry[1], outputFile: path.join(artifactRoot, "junit.xml") }];
      return entry;
    }),
  }));

};
