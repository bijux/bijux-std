"use strict";
const fs = require("node:fs");
const path = require("node:path");
const { test, expect } = require("@playwright/test");
const measure = require("./contrast-targets/measurement");
const focusBoundary = require("./contrast-targets/focus-boundary");

test.beforeEach(async ({ browser }, info) => {
  info.annotations.push({ type: "browser-version", description: browser.version() });
});
const root = path.resolve(__dirname, "../../../..");
const styles = ["06-components.css", "07-utilities.css"];

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

async function focusStates(page, control, name, browserName, info, { scheme, forced = false }) {
  await expect(control).toHaveCount(1);
  await expect(control).toBeVisible();
  await focusBoundary.tabTo(page, control, browserName);
  const observations = [];
  const qualify = async state => {
    const observed = await focusBoundary.observe(page, control);
    const attachment = `boundary-${name.replaceAll(" ", "-")}-${state}`;
    // Retain actual paint and clipping surfaces before any assertion rejects them.
    await info.attach(`${attachment}.json`, {
      body: Buffer.from(JSON.stringify({ name, state, browserName, forced,
        url: page.url(), viewport: page.viewportSize(), ...observed }, null, 2)),
      contentType: "application/json" });
    await info.attach(`${attachment}.png`, { body: await page.screenshot(), contentType: "image/png" });
    expect(observed.focused).toBe(true);
    expect(observed.focusVisible).toBe(true);
    expect(observed.outlineStyle).toBe("solid");
    expect(observed.width).toBeGreaterThanOrEqual(2);
    expect(observed.boundary.contained, `${name}: entire ring inside actual clipping surfaces`).toBe(true);
    // WebKit media simulation does not establish native OS palette paint.
    if (!forced || browserName !== "webkit") expect(observed.paint.minimum).toBeGreaterThanOrEqual(3);
    observations.push({ name, state, ...observed });
  };
  await qualify(forced ? "forced" : scheme);
  if (!forced) {
    const opposite = scheme === "light" ? "dark" : "light";
    const toggle = page.locator("[data-bijux-theme-toggle]");
    if (await toggle.count()) await expect(toggle).toHaveAttribute("data-bijux-theme-mode", "auto");
    else await expect(page.locator("input[name='__palette'][data-md-color-media='(prefers-color-scheme)']")).toBeChecked();
    await page.emulateMedia({ colorScheme: opposite });
    await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", opposite === "dark" ? "slate" : "default");
    await qualify(`auto-${opposite}`);
    await page.emulateMedia({ colorScheme: scheme });
    await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", scheme === "dark" ? "slate" : "default");
    await qualify(`auto-return-${scheme}`);
    if (await control.getAttribute("data-bijux-theme-toggle") !== null) {
      for (const mode of ["light", "dark", "auto"]) {
        await page.keyboard.press("Space");
        await expect(control).toHaveAttribute("data-bijux-theme-mode", mode);
        await expect(control).toBeFocused();
        await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme",
          (mode === "auto" ? scheme : mode) === "dark" ? "slate" : "default");
        await qualify(`selected-${mode}`);
      }
    }
  }
  return observations;
}

async function boundaryControls(page, browserName, info, options) {
  const observations = [];
  const menu = page.locator('[data-bijux-header-control="drawer-toggle"]');
  const compact = await menu.isVisible();
  const search = page.locator('[data-bijux-header-control="search-toggle"]');
  const theme = page.locator("[data-bijux-theme-toggle]");
  // Source-owned enhanced headers expose exactly one Search and Theme utility.
  await expect(search).toHaveCount(1);
  await expect(theme).toHaveCount(1);
  for (const [name, control] of [["search utility", search], ["theme utility", theme]]) {
    await expect(control).toHaveAccessibleName(/\S/);
    observations.push(...await focusStates(page, control, name, browserName, info, options));
  }
  const repository = page.locator("header .md-source");
  if (await repository.isVisible()) observations.push(...await focusStates(page, repository, "repository", browserName, info, options));
  if (compact) {
    await focusBoundary.tabTo(page, menu, browserName);
    await page.keyboard.press("Space");
    await expect(page.locator("#__drawer")).toBeChecked();
    const close = page.getByRole("button", { name: "Close navigation", exact: true });
    observations.push(...await focusStates(page, close, "navigation close", browserName, info, options));
  }
  observations.push(...await focusStates(page, page.locator(".bijux-tree summary").first(), "navigation disclosure", browserName, info, options));
  if (compact) {
    await page.keyboard.press("Escape");
    await expect(page.locator("#__drawer")).not.toBeChecked();
    await expect(menu).toBeFocused();
  }
  return observations;
}

async function compatibilityControls(page, browserName, info, options) {
  await page.goto("/fixtures/native-header/");
  // Native Material owns its sidebar; readiness belongs to the upgraded native control.
  const nativeMenu = page.locator("header button[data-bijux-control-target='__drawer']");
  await expect(nativeMenu).toHaveCount(1);
  await expect(nativeMenu).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator("#__drawer")).not.toBeChecked();
  const census = await page.locator("header").evaluate(header => [...header.querySelectorAll("button,input,label[for^='__palette_'],select")].map(node => {
    const rect = node.getBoundingClientRect(), style = getComputedStyle(node);
    return { tag:node.tagName, type:node.getAttribute("type"), role:node.getAttribute("role"),
      name:node.getAttribute("aria-label") || node.getAttribute("title"), target:node.getAttribute("for"),
      tabIndex:node.tabIndex, hidden:node.hidden, visible:rect.width > 0 && rect.height > 0 && style.visibility !== "hidden",
      rectangle:{ x:rect.x,y:rect.y,width:rect.width,height:rect.height } };
  }));
  await info.attach("native-material-control-census.json", { body:Buffer.from(JSON.stringify(census,null,2)),contentType:"application/json" });
  const observations = [];
  for (const kind of ["drawer", "search"]) {
    const utility = page.locator(`[data-bijux-header-control='${kind}-toggle']`);
    await expect(utility).toHaveCount(1);
    await expect(utility).toHaveAccessibleName(/\S/);
    observations.push(...await focusStates(page, utility, `compatible ${kind} utility`, browserName, info, options));
  }
  // Configured native Material palette must retain an ordinary reachable selector.
  const selector = page.locator("header [for^='__palette_']:visible");
  await expect(selector).toHaveCount(1);
  observations.push(...await focusStates(page, selector, "compatible theme selector", browserName, info, options));
  const activations = [];
  for (const input of ["Space", "Enter", "click"]) {
    const current = page.locator("header [for^='__palette_']:visible");
    const target = await current.getAttribute("for");
    await expect(current).toHaveAttribute("type", "button");
    await expect(current).toHaveAttribute("aria-controls", target);
    if (input === "click") await current.click();
    else await page.keyboard.press(input);
    await expect(page.locator(`input[id="${target}"]`)).toBeChecked();
    const successor = page.locator("header [for^='__palette_']:visible");
    await expect(successor).toHaveCount(1);
    await expect(successor).toBeFocused();
    const observed = await focusBoundary.observe(page, successor);
    await info.attach(`compatible-theme-${input}.json`, { body:Buffer.from(JSON.stringify({
      input, target, browserName, ...observed },null,2)),contentType:"application/json" });
    if (input !== "click") {
      expect(observed.focusVisible).toBe(true);
      expect(observed.outlineStyle).toBe("solid");
      expect(observed.width).toBeGreaterThanOrEqual(2);
      expect(observed.boundary.contained).toBe(true);
      if (!options.forced || browserName !== "webkit") expect(observed.paint.minimum).toBeGreaterThanOrEqual(3);
    }
    activations.push({ input, target, ...observed });
  }
  return { census, observations, activations };
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
    observations.push(...await boundaryControls(page, browserName, info, { scheme }));
    for (const hover of [false, true]) {
      if (hover) await palette.hover();
      const icon = await measure.textOrIcon(page, palette.locator("svg"), { icon: true });
      expect(icon.minimum).toBeGreaterThanOrEqual(3);
      observations.push({ name: hover ? "palette hover icon" : "palette icon", ...icon });
    }
    for (const selector of [".bijux-hub-tab", ".bijux-site-tabs .bijux-tabs__link"]) {
      const links = page.locator(selector);
      if (!await links.count() || !await links.first().isVisible()) continue;
      // Keyboard traversal can leave a horizontally scrollable strip at another link.
      // Return through ordinary focus, then advance so the normal sample is unfocused.
      await focusBoundary.tabTo(page, links.first(), browserName);
      await page.keyboard.press(browserName === "webkit" ? "Alt+Tab" : "Tab");
      await expect(links.first()).not.toBeFocused();
      await page.mouse.move(page.viewportSize().width / 2, page.viewportSize().height / 2);
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
    const originalViewport = page.viewportSize();
    for (const width of [320, 767]) {
      await page.setViewportSize({ width, height: originalViewport.height });
      for (const selected of ["Python", "Rust"]) {
        await page.locator(".tabbed-labels a").getByText(selected, { exact: true }).click();
        await expect(page.locator(".tabbed-set input:checked")).toHaveAttribute(
          "id", selected === "Python" ? "__tabbed_1_1" : "__tabbed_1_2");
        const inactive = page.locator(".tabbed-labels a").getByText(
          selected === "Python" ? "Rust" : "Python", { exact: true });
        const text = await measure.textOrIcon(page, inactive);
        assertText(text);
        observations.push({ name: `inactive tab at ${width} CSS px`, selected, ...text });
      }
    }
    await page.setViewportSize(originalViewport);
    await page.locator(".tabbed-labels a").getByText("Python", { exact: true }).click();
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
    const workerURL = "**/assets/javascripts/workers/search*.js";
    await page.route(workerURL, route => route.fulfill({
      status: 404, contentType: "text/plain", body: "Controlled unavailable search worker" }));
    await page.goto("/bijux-core/");
    await page.locator('[data-bijux-header-control="search-toggle"]').click();
    await page.locator("[data-md-component='search-query']").fill("resilient navigation");
    const recovery = page.locator(".bijux-search-recovery [role='status']");
    await expect(recovery).toContainText("Search is unavailable", { timeout: 12_000 });
    const feedback = await measure.textOrIcon(page, recovery);
    assertText(feedback);
    observations.push({ name: "search worker recovery text", ...feedback });
    await page.unroute(workerURL);
    await page.getByRole("button", { name: "Retry search", exact: true }).click();
    await expect(page.locator(".md-search-result__link:visible").first()).toBeVisible({ timeout: 12_000 });
    const compatibility = info.project.name.endsWith("-phone")
      ? await compatibilityControls(page, browserName, info, { scheme }) : null;
    await receipt(info, { scheme: expectedScheme, observations, compatibility, errors, browserName });
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
  const boundaries = await boundaryControls(page, browserName, info, { forced: true });
  const compatibility = info.project.name.endsWith("-phone")
    ? await compatibilityControls(page, browserName, info, { forced: true }) : null;
  await receipt(info, { browserName, forced, focused, boundaries, compatibility,
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
  await page.goto("/");
  await expect(page.locator("body")).toHaveAttribute("data-bijux-drawer-ready", "true");
  const menu = page.locator('[data-bijux-header-control="drawer-toggle"]');
  let control = page.locator("header .md-source");
  if (await menu.isVisible()) {
    await focusBoundary.tabTo(page, menu, info.project.use.browserName);
    await page.keyboard.press("Space");
    await expect(page.locator("#__drawer")).toBeChecked();
    control = page.locator(".bijux-tree summary").first();
  }
  await focusBoundary.tabTo(page, control, info.project.use.browserName);
  const clippedFocus = await focusBoundary.observe(page, control);
  expect(clippedFocus.focused).toBe(true);
  expect(clippedFocus.focusVisible).toBe(true);
  expect(clippedFocus.boundary.contained).toBe(false);
  expect(clippedFocus.boundary.clippedBy.length).toBeGreaterThan(0);
  await info.attach("historical-clipped-focus.png", { body: await page.screenshot(), contentType: "image/png" });
  await receipt(info, { classification: "exact historical authored CSS detects deficient reader direction and clipped focus", observed, clippedFocus });
});
