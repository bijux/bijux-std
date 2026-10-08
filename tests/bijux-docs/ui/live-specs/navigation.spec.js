const { test, expect } = require("@playwright/test");
test.beforeEach(async ({ browser }, info) => {
  info.annotations.push({ type: "browser-version", description: browser.version() });
});
test("published compact header preserves page and hidden navigation", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await page.goto("/");
  await expect(page.locator("main")).toBeVisible();
  expect(await page.locator("header").first().evaluate((node) => node.getBoundingClientRect().height)).toBeLessThanOrEqual(112);
  expect(await page.locator("[data-bijux-detail-strip][hidden]").evaluateAll((nodes) => nodes.filter((node) => node.getClientRects().length).length)).toBe(0);
});
test("published phone drawer exposes site destinations and dismisses", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const trigger = page.locator("[data-bijux-header-control='drawer-toggle']");
  await expect(page.locator("#__drawer")).not.toBeChecked();
  await trigger.focus();
  await page.keyboard.press("Space");
  await expect(page.locator("#__drawer")).toBeChecked();
  await expect(page.locator(".md-sidebar--primary .bijux-mobile-hub__link")).toHaveCount(9);
  await expect(page.locator(".md-sidebar--primary .bijux-mobile-hub__link").first()).toBeInViewport();
  await page.keyboard.press("Escape");
  await expect(page.locator("#__drawer")).not.toBeChecked();
  await expect(trigger).toBeFocused();
});
test("published reader journey has no uncaught shell errors", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.locator("h1")).toBeVisible();
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.locator("main")).toBeVisible();
  }
  expect(errors).toEqual([]);
});
