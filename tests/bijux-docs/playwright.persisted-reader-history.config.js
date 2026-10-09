"use strict";
const { defineConfig } = require("@playwright/test");
const { configureProjects, unsharded } = require("./reporting/projects");
const inherited = unsharded(require("./playwright.config"));
const projects = [["narrow", 320], ["phone", 390], ["desktop", 1024]].map(([name, width]) => ({
  name: "chromium-reader-" + name, metadata: { required_case_count: 1 },
  use: { browserName: "chromium", viewport: { width, height: 900 },
    channel: "chromium", launchOptions: { ignoreDefaultArgs: ["--disable-back-forward-cache"] } },
}));
module.exports = configureProjects(defineConfig({
  ...inherited, testMatch: "**/persisted-reader-history.spec.js", projects, workers: 1,
  reporter: inherited.reporter.map(entry =>
    Array.isArray(entry) && String(entry[0]).endsWith("strict-reporter.js")
      ? [entry[0], { ...entry[1], scope: "persisted_native_diagram_reader_chromium", requiredProjects: projects.map(project => project.name) }]
      : entry,
  ),
}));
