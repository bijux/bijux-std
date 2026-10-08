const { test, expect } = require("@playwright/test");
const control = page => page.locator("[data-bijux-header-control='drawer-toggle']");
const navigation = page => page.locator("#bijux-navigation");
test.beforeEach(async ({ browser, page }, info) => {
  info.annotations.push({ type: "browser-version", description: browser.version() });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  info._runtimeErrors = errors;
});
test.afterEach(async ({}, info) => { expect(info._runtimeErrors).toEqual([]); });
async function open(page) {
  await control(page).click();
  await expect(page.locator("#__drawer")).toBeChecked();
  await expect(navigation(page).locator("a:visible").first()).toBeInViewport();
}
test("modal drawer contains every Tab stop and restores background on backdrop dismissal", async ({ page }) => {
  await page.goto("/");
  await open(page);
  await expect(page.locator(".md-sidebar--primary")).toHaveAttribute("role", "dialog");
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", true);
  for (const key of ["Shift+Tab", ...Array(20).fill("Tab"), ...Array(4).fill("Shift+Tab")]) {
    await page.keyboard.press(key);
    await expect(navigation(page).locator(":focus")).toHaveCount(1);
  }
  const size = page.viewportSize();
  await page.locator(".md-overlay").click({ position: { x: size.width - 4, y: size.height / 2 } });
  await expect(page.locator("#__drawer")).not.toBeChecked();
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", false);
  await expect(control(page)).toBeFocused();
});
test("narrow masthead retains primary controls with enlarged text and prescribed spacing", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.goto("/fixtures/long-registry/");
  const size = await page.evaluate(() => parseFloat(getComputedStyle(document.documentElement).fontSize));
  await page.addStyleTag({ content: `html { font-size: ${size * 2}px !important; } * { line-height: 1.5 !important; letter-spacing: .12em !important; word-spacing: .16em !important; } p { margin-block-end: 2em !important; }` });
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  for (const kind of ["drawer", "search"]) {
    const box = await page.locator(`[data-bijux-header-control='${kind}-toggle']`).boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(320);
    expect(box.width).toBeGreaterThanOrEqual(44);
  }
  await open(page);
  await page.keyboard.press("Escape");
  await expect(control(page)).toBeFocused();
});
test("repeated instant journeys keep an explicit drawer opening through late Material resets", async ({ page }) => {
  await page.goto("/platform/");
  for (let journey = 0; journey < 10; journey += 1) {
    await page.locator("main").getByRole("link", { name: "Getting started", exact: true }).click();
    await expect(page).toHaveURL(/\/platform\/start\/$/);
    await expect(page.locator("h1")).toContainText("Platform getting started");
    await open(page);
    // The admitted Material location reset is delayed 125ms. Keep the explicit
    // opening observable beyond that bound before qualifying its ownership.
    await page.waitForTimeout(160);
    await expect(page.locator("#__drawer")).toBeChecked();
    await page.keyboard.press("Tab");
    await expect(navigation(page).locator(":focus")).toHaveCount(1);
    await page.keyboard.press("Escape");
    await expect(page.locator("#__drawer")).not.toBeChecked();
    await expect(control(page)).toBeFocused();
    await page.goBack();
    await expect(page).toHaveURL(/\/platform\/$/);
  }
});
