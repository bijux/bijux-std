const { defineConfig } = require("@playwright/test"),
  path = require("node:path");
const inherited = require("./playwright.config");
const artifactRoot = path.resolve(
  process.env.BIJUX_UI_ARTIFACT_ROOT ||
    path.join(__dirname, "../../artifacts/bijux-docs/link-policy-playwright"),
);
const generatedRoot = path.resolve(
  process.env.BIJUX_GENERATED_ROOT ||
    path.join(__dirname, "../../artifacts/bijux-docs/link-policy-generated"),
);
const origin = process.env.BIJUX_LINK_POLICY_ORIGIN || "http://127.0.0.1:4173";
const projects = inherited.projects.map((project) => ({
  ...project,
  name: project.name + "-links",
  metadata: { required_case_count: 9 },
}));
module.exports = defineConfig({
  ...inherited,
  testMatch: "**/external-links.spec.js",
  projects,
  fullyParallel: false,
  workers: 1,
  use: { ...inherited.use, baseURL: origin, trace: "on" },
  webServer: {
    ...inherited.webServer,
    command: `python3 -m http.server ${new URL(origin).port} --bind 127.0.0.1 --directory "${path.join(generatedRoot, "site")}"`,
    url: `${origin}/`,
  },
  outputDir: path.join(artifactRoot, "test-results"),
  reporter: inherited.reporter.map((entry) => {
    if (!Array.isArray(entry)) return entry;
    if (String(entry[0]).endsWith("strict-reporter.js"))
      return [
        entry[0],
        {
          ...entry[1],
          output: path.join(artifactRoot, "qualification.json"),
          generatedRoot,
          scope: "authored_link_policy",
          requiredProjects: projects.map((project) => project.name),
        },
      ];
    if (entry[0] === "html")
      return [
        entry[0],
        { ...entry[1], outputFolder: path.join(artifactRoot, "html-report") },
      ];
    if (entry[0] === "junit")
      return [
        entry[0],
        { ...entry[1], outputFile: path.join(artifactRoot, "junit.xml") },
      ];
    return entry;
  }),
});
