"use strict";
const fs = require("node:fs");
const path = require("node:path");
const { test, expect } = require("@playwright/test");
const measure = require("./contrast-targets/measurement");
const root = path.resolve(__dirname, "../../../..");
const styles = ["06-components.css"];

async function receipt(info, data) {
  await info.attach("rendered-contrast.json", { body: Buffer.from(JSON.stringify(data, null, 2)), contentType: "application/json" });
}
function assertText(observation) {
  expect(observation.minimum, `${observation.text}: rendered contrast`).toBeGreaterThanOrEqual(observation.threshold);
}
async function openDrawer(page) {
  const menu = page.locator('[data-bijux-header-control="drawer-toggle"]');
  if (await menu.isVisible()) {
    await menu.click();
    await expect(page.locator("#bijux-navigation")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(menu).toBeFocused();
  }
}

for (const [scheme, expectedScheme] of [["light", "default"], ["dark", "slate"]]) {
  test(`readable ${expectedScheme} shell and reading controls`, async ({ page, browserName }, info) => {
    const errors = [];
    page.on("pageerror", error => errors.push(String(error)));
    await page.emulateMedia({ colorScheme: scheme, forcedColors: "none" });
    await page.goto("/");
    await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", expectedScheme);
    await expect(page.locator("body")).toHaveAttribute("data-bijux-drawer-ready", "true");
    const observations = [];
    const menu = page.locator('[data-bijux-header-control="drawer-toggle"]');
    const compact = await page.evaluate(() => matchMedia("(max-width: 76.2344em)").matches);
    if (compact) await expect(menu).toBeVisible();
    else await expect(menu).toBeHidden();
    if (compact) {
      await measure.tabTo(page, menu, browserName);
      const focused = await measure.focus(page, menu);
      expect(focused.focusVisible).toBe(true);
      expect(focused.outlineWidth).toBeGreaterThanOrEqual(2);
      expect(focused.ratio).toBeGreaterThanOrEqual(3);
      expect(focused.rectangle.width).toBeGreaterThanOrEqual(44);
      expect(focused.rectangle.height).toBeGreaterThanOrEqual(44);
      expect(focused.centerOwned).toBe(true);
      await info.attach("keyboard-header-focus.png", { body: await page.screenshot(), contentType: "image/png" });
      observations.push({ name: "enhanced menu focus and target", ...focused });
      await page.keyboard.press("Space");
      const close = page.getByRole("button", { name: "Close navigation" });
      await expect(close).toBeVisible();
      await expect.poll(async () => (await measure.state(close)).centerOwned).toBe(true);
      const closeState = await measure.state(close);
      expect(closeState.rectangle.width).toBeGreaterThanOrEqual(44);
      expect(closeState.rectangle.height).toBeGreaterThanOrEqual(44);
      expect(closeState.centerOwned).toBe(true);
      observations.push({ name: "drawer close target", ...closeState });
      await page.keyboard.press("Escape");
      await expect(menu).toBeFocused();
    }
    const primaryControls = page.locator("[data-bijux-header-control], [data-bijux-theme-toggle]");
    for (const control of await primaryControls.all()) {
      if (!await control.isVisible()) continue;
      await expect.poll(async () => (await measure.state(control)).centerOwned).toBe(true);
      const target = await measure.state(control);
      expect(target.rectangle.width).toBeGreaterThanOrEqual(44);
      expect(target.rectangle.height).toBeGreaterThanOrEqual(44);
      expect(target.centerOwned).toBe(true);
      observations.push({ name: await control.getAttribute("aria-label"), kind: "primary44", ...target });
    }
    const palette = page.locator("[data-bijux-theme-toggle]");
    await expect(palette).toBeVisible();
    for (const hover of [false, true]) {
      if (hover) await palette.hover();
      const icon = await measure.textOrIcon(page, palette.locator("svg"), { icon: true });
      expect(icon.minimum).toBeGreaterThanOrEqual(3);
      observations.push({ name: hover ? "palette hover icon" : "palette icon", ...icon });
    }
    for (const selector of [".bijux-hub-tab", ".bijux-site-tabs .bijux-tabs__link"]) {
      const links = page.locator(selector);
      if (!await links.count() || !await links.first().isVisible()) continue;
      for (const hover of [false, true]) {
        if (hover) await links.first().hover();
        const text = await measure.textOrIcon(page, links.first());
        assertText(text);
        observations.push({ name: `${selector} ${hover ? "hover" : "normal"}`, ...text });
      }
    }
    await page.goto("/reading/");
    await expect(page.locator("h1")).toHaveText(/^Rich reading reference(?:¶)?$/);
    const disclosure = page.locator("article details > summary").filter({ hasText: /^Reader disclosure$/ });
    await disclosure.click();
    await expect(page.locator("article details[open] > summary").filter({ hasText: /^Reader disclosure$/ })).toBeVisible();
    for (const selector of ["h1", ".md-typeset p", ".md-typeset table th", ".md-footer__direction"]) {
      const node = page.locator(selector).first();
      await expect(node).toBeVisible();
      await node.scrollIntoViewIfNeeded();
      const text = await measure.textOrIcon(page, node);
      assertText(text);
      observations.push({ name: selector, ...text });
    }
    await info.attach("visible-reader-footer.png", { body: await page.screenshot(), contentType: "image/png" });
    const previous = page.getByRole("link", { name: "Previous: Leaf destination", exact: true });
    await expect(previous.locator(".md-footer__direction")).toBeVisible();
    await previous.click();
    await expect(page).toHaveURL(/\/repository\/details\/leaf\/(?:#.*)?$/);
    await expect(page.getByRole("heading", { level: 1, name: /^Repository leaf destination/ })).toBeVisible();
    await page.goBack();
    await expect(page).toHaveURL(/\/reading\/(?:#.*)?$/);
    await expect(page.getByRole("heading", { level: 1, name: /^Rich reading reference/ })).toBeVisible();
    observations.push({ name: "ordinary Previous reader destination and browser Back", outcome: "passed" });
    await receipt(info, { scheme: expectedScheme, observations, errors, browserName });
    expect(errors).toEqual([]);
  });
}

test("forced color focus preserves meaningful control and native target", async ({ page, browserName }, info) => {
  await page.emulateMedia({ colorScheme: "dark", forcedColors: "active" });
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-bijux-drawer-ready", "true");
  const menu = page.locator('[data-bijux-header-control="drawer-toggle"]');
  const control = await menu.isVisible() ? menu : page.locator("[data-bijux-theme-toggle]");
  if (await menu.isVisible()) {
    await measure.tabTo(page, control, browserName);
  } else {
    await expect(control).toBeVisible();
    // Mixed ordinary input qualifies ring paint without claiming forward search traversal.
    await control.click();
    await page.keyboard.press(browserName === "webkit" ? "Alt+Tab" : "Tab");
    await page.keyboard.press(browserName === "webkit" ? "Alt+Shift+Tab" : "Shift+Tab");
    await expect(control).toBeFocused();
  }
  const focused = await measure.focus(page, control);
  expect(focused.focusVisible).toBe(true);
  expect(focused.outlineWidth).toBeGreaterThanOrEqual(2);
  expect(focused.centerOwned).toBe(true);
  const forced = await page.evaluate(() => ({ active: matchMedia("(forced-colors: active)").matches,
    adjust: getComputedStyle(document.activeElement).forcedColorAdjust }));
  expect(forced.active).toBe(true);
  // WebKit emulates the media query without the OS palette remapping Chromium/Firefox apply.
  if (browserName !== "webkit") expect(focused.ratio).toBeGreaterThanOrEqual(3);
  await info.attach("forced-color-keyboard-focus.png", { body: await page.screenshot(), contentType: "image/png" });
  await receipt(info, { browserName, forced, focused,
    classification: browserName === "webkit" ? "source response only; native OS forced paint unqualified" : "browser emulated forced paint; physical OS/assistive validation remains open" });
});

test("historical shared CSS exposes the repaired contrast regression", async ({ page }, info) => {
  for (const name of styles) {
    const original = fs.readFileSync(path.join(root, "tests/bijux-docs/ui/generated-specs/contrast-targets/historical", name), "utf8");
    await page.route(`**/assets/styles/${name}`, route => route.fulfill({ contentType: "text/css", body: original }));
  }
  await page.emulateMedia({ colorScheme: "light", forcedColors: "none" });
  await page.goto("/");
  await page.goto("/reading/");
  const direction = page.locator(".md-footer__direction").first();
  const visible = await direction.isVisible();
  let observed = { visible, defect: "reader direction hidden by inherited Material phone styling" };
  if (visible) {
    await direction.scrollIntoViewIfNeeded();
    observed = { visible, ...(await measure.textOrIcon(page, direction)) };
    expect(observed.minimum).toBeLessThan(observed.threshold);
  }
  await receipt(info, { classification: "exact historical authored CSS counterfactual; hidden or deficient reader direction is detected", observed });
});
