const { test: base, expect } = require("@playwright/test");
const test = base.extend({
  runtimeEvidence: [async ({ browser, page }, use, info) => {
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    info.annotations.push({ type: "browser-version", description: browser.version() });
    await use();
    expect(errors, "Unexpected uncaught runtime errors").toEqual([]);
  }, { auto: true }],
});
const control = (page, kind) => page.locator(`[data-bijux-header-control='${kind}-toggle']`);
const navigation = (page) => page.locator("#bijux-navigation");
async function ready(page, route = "/") {
  await page.goto(route);
  await expect(page.locator("main")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", /phone|normal|desktop|wide/);
}
async function phone(page, route = "/") {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page, route);
}
async function openDrawer(page) {
  await control(page, "drawer").click();
  await expect(page.locator("#__drawer")).toBeChecked();
  await expect(navigation(page).locator("a:visible").first()).toBeInViewport();
}
module.exports = { test, expect, control, navigation, ready, phone, openDrawer };
