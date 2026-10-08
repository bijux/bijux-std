"use strict";
const { test, expect } = require("@playwright/test");
const measure = require("./contrast-targets/measurement");

test.beforeEach(async ({ browser }, info) => {
  info.annotations.push({ type: "browser-version", description: browser.version() });
});
test("native no-script Navigation retains white focus and 44px hit target", async ({ browser, browserName, baseURL }, info) => {
  const context = await browser.newContext({ javaScriptEnabled: false, baseURL, viewport: { width: 390, height: 844 } });
  try {
    const page = await context.newPage();
    await page.goto("/");
    const checkbox = page.getByRole("checkbox", { name: "Navigation", exact: true });
    await expect(checkbox).toBeVisible();
    await measure.tabTo(page, checkbox, browserName);
    const observations = [];
    for (const scheme of ["light", "dark"]) {
      await page.emulateMedia({ colorScheme: scheme, forcedColors: "none" });
      const focused = await measure.focus(page, checkbox);
      expect(focused.focusVisible).toBe(true);
      expect(focused.ratio).toBeGreaterThanOrEqual(3);
      expect(focused.rectangle.width).toBeGreaterThanOrEqual(44);
      expect(focused.rectangle.height).toBeGreaterThanOrEqual(44);
      expect(focused.centerOwned).toBe(true);
      await info.attach(`native-${scheme}-focus.png`, { body: await page.screenshot(), contentType: "image/png" });
      observations.push({ scheme, ...focused });
    }
    await page.keyboard.press("Space");
    await expect(checkbox).toBeChecked();
    await expect(page.locator("#bijux-navigation")).toBeVisible();
    await info.attach("native-focus.json", { body: Buffer.from(JSON.stringify(observations, null, 2)), contentType: "application/json" });
  } finally { await context.close(); }
});
