const assert = require("node:assert/strict");
const test = require("node:test");
const navigation = require("../playwright.navigation.config");
const drawer = require("../playwright.drawer.config");
const previousLive = process.env.BIJUX_LIVE_E2E;
process.env.BIJUX_LIVE_E2E = "1";
const live = require("../playwright.live.config");
if (previousLive === undefined) delete process.env.BIJUX_LIVE_E2E;
else process.env.BIJUX_LIVE_E2E = previousLive;
const expected = ["chromium", "firefox", "webkit"].flatMap(engine => ["phone", "compact", "desktop"].map(profile => `${engine}-${profile}`));
test("bounded navigation gate requires exactly 126 cases across all engine profiles", () => {
  assert.deepEqual(navigation.projects.map(project => project.name), expected);
  assert.equal(navigation.projects.reduce((count, project) => count + project.metadata.required_case_count, 0), 126);
  assert(navigation.projects.every(project => project.metadata.required_case_count === 14));
});
test("phone dialog gate cannot inherit desktop modal assertions through project merging", () => {
  assert.deepEqual(drawer.projects.map(project => project.name), ["chromium-phone", "firefox-phone", "webkit-phone"]);
  assert(drawer.projects.every(project => project.use.viewport.width === 390 && project.metadata.required_case_count === 3));
});
test("live gate retains its own case contract across all engine profiles", () => {
  assert.deepEqual(live.projects.map(project => project.name), expected);
  assert(live.projects.every(project => project.metadata.required_case_count === 3));
});
