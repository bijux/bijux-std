const fs = require("node:fs");
const path = require("node:path");
const registry = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../../../../shared/bijux-docs/config/hub-links.json"), "utf8"));
const { test, expect } = require("./helpers/document");
const { desktopRegistry, touchJourney, scrollingControlJourney } = require("./registry-overflow/journeys");
function destinations(info) {
  const expected = registry.map(entry => {
    const route = entry.key === "bijux" ? "/" : `/${entry.key}/`;
    const label = entry.label + " scientific platform";
    expect(label.length).toBeGreaterThanOrEqual(entry.label.length * 1.5);
    return { label, url: new URL(route, info.project.use.baseURL).href, title: entry.key === "bijux" ? "Bijux" : entry.key,
      heading: entry.key === "bijux" ? /^Bijux reference(?:¶)?$/ : /^Product overview(?:¶)?$/ };
  }).concat([
    { label: "Reference extension", url: new URL("/fixtures/empty/", info.project.use.baseURL).href,
      currentURL: new URL("/bijux-core/", info.project.use.baseURL).href, title: "bijux-core", heading: /^Product overview(?:¶)?$/ },
    { label: "Research extension", url: new URL("/reading/", info.project.use.baseURL).href,
      currentURL: new URL("/", info.project.use.baseURL).href, title: "Reading reference - Bijux", heading: /^Rich reading reference(?:¶)?$/ },
  ]);
  return expected;
}

test("desktop overflow exposes all eleven registry destinations through named pointer controls", async ({ page }, info) => {
  await desktopRegistry(page, info, destinations(info), 1220, "pointer");
});
test("desktop registry current and last links retain native Tab Enter and scrolling Space endpoints", async ({ page }, info) => {
  await desktopRegistry(page, info, destinations(info), 1440, "keyboard");
  await scrollingControlJourney(page, info);
});
test("desktop registry current and last links retain trusted touch and focused phone handoff", async ({ page, browser }, info) => {
  await touchJourney(browser, info, touchPage => desktopRegistry(touchPage, info, destinations(info), 1440, "touch"));
  await scrollingControlJourney(page, info);
});
