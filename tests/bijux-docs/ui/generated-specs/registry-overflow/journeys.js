const { expect } = require("../helpers/document");
const { tabTo, focus: measureFocus } = require("../contrast-targets/measurement");
const control = (page, kind) => page.locator(`[data-bijux-header-control='${kind}-toggle']`);
async function ready(page, route = "/") {
  await page.goto(route);
  await expect(page.locator("main")).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", /phone|normal|desktop|wide/);
}
function assertRegistryTarget(target) {
  expect(target.height).toBeGreaterThanOrEqual(44);
  expect(target.width).toBeGreaterThanOrEqual(44);
  expect(target.owned).toBe(true);
  expect(target.fit).toBe(true);
  expect(target.labelFit).toBe(true);
}
async function touchJourney(browser, info, journey) {
  const context = await browser.newContext({ hasTouch: true, viewport: { width: 390, height: 844 }, baseURL: info.project.use.baseURL });
  const errors = [];
  try {
    const page = await context.newPage();
    page.on("pageerror", error => errors.push(error.message));
    const reportedTouchPoints = await page.evaluate(() => navigator.maxTouchPoints);
    await info.attach("touch-context.json", { body: Buffer.from(JSON.stringify({ hasTouch: true, reportedTouchPoints, physicalDeviceQualified: false })), contentType: "application/json" });
    await journey(page);
    expect(errors, "Touch context has no uncaught runtime errors").toEqual([]);
  } finally {
    await context.close();
  }
}
async function desktopRegistry(page, info, entries, width, input) {
  const current = entries.find(entry => entry.url === new URL("/bijux-core/", info.project.use.baseURL).href);
  const destinations = input === "pointer" && width === 1220 ? entries : [current, entries.at(-1)];
  for (const entry of destinations) {
    await page.setViewportSize({ width, height: 900 });
    await ready(page, "/fixtures/long-registry/");
    const strip = page.locator("header .bijux-hub-strip");
    const next = strip.getByRole("button", { name: "Scroll Bijux sites forward", exact: true });
    const previous = strip.getByRole("button", { name: "Scroll Bijux sites backward", exact: true });
    await expect(next).toBeVisible();
    await expect(previous).toBeVisible();
    const link = strip.getByRole("link", { name: entry.label, exact: true });
    await expect(link).toHaveCount(1);
    expect(await link.evaluate(node => node.href)).toBe(entry.url);
    if (input === "keyboard") {
      await tabTo(page, link, info.project.use.browserName, 160);
      await expect(link).toBeFocused();
    } else {
      const fits = () => link.evaluate(node => {
        const bounds = node.closest("ul").getBoundingClientRect(), rect = node.getBoundingClientRect();
        return rect.left >= bounds.left - 1 && rect.right <= bounds.right + 1;
      });
      for (let action = 0; action < 12 && !await fits(); action++) {
        const behind = await link.evaluate(node => node.getBoundingClientRect().left < node.closest("ul").getBoundingClientRect().left);
        const button = behind ? previous : next;
        await expect(button).toHaveAttribute("aria-disabled", "false");
        if (input === "touch") await button.tap();
        else await button.click();
        expect(await page.evaluate(() => document.activeElement.isConnected)).toBe(true);
      }
      expect(await fits(), "Named scrolling actions reveal the complete destination before link activation").toBe(true);
    }
    const target = await link.evaluate(node => {
      const rect = node.getBoundingClientRect(), bounds = node.closest("ul").getBoundingClientRect();
      const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
      return { width:rect.width,height:rect.height,owned:hit === node || node.contains(hit),
        fit:rect.left >= bounds.left - 1 && rect.right <= bounds.right + 1,
        labelFit:node.scrollWidth <= node.clientWidth && node.scrollHeight <= node.clientHeight };
    });
    assertRegistryTarget(target);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    if (input === "keyboard") await page.keyboard.press("Enter");
    else if (input === "touch") await link.tap();
    else await link.click();
    await expect(page).toHaveURL(entry.url);
    await expect(page.locator("main h1")).toHaveText(entry.heading);
    await expect(page).toHaveTitle(entry.title);
    const active = page.locator("header .bijux-hub-strip a[aria-current='location']");
    await expect(active).toHaveCount(1);
    expect(await active.evaluate(node => node.href)).toBe(entry.currentURL || entry.url);
    expect(await page.evaluate(() => document.activeElement.isConnected)).toBe(true);
  }
}

async function scrollingControlJourney(page, info) {
    await page.setViewportSize({ width: 1440, height: 900 });
    await ready(page, "/fixtures/long-registry/");
    const forward = page.getByRole("button", { name: "Scroll Bijux sites forward", exact: true });
    await tabTo(page, forward, info.project.use.browserName, 160);
    await expect(forward).toBeFocused();
    const measured = await measureFocus(page, forward);
    expect(measured.focusVisible).toBe(true);
    expect(measured.ratio).toBeGreaterThanOrEqual(3);
    const strip = page.locator("header #bijux-registry-links");
    await expect(forward).toHaveAttribute("aria-disabled", "true");
    const endpoint = await strip.evaluate(node => node.scrollLeft);
    await page.keyboard.press("Space");
    await expect(forward).toBeFocused();
    expect(await strip.evaluate(node => node.scrollLeft)).toBe(endpoint);
    await strip.hover();
    await page.mouse.wheel(-800, 0);
    await expect(forward).toHaveAttribute("aria-disabled", "false");
    const before = await strip.evaluate(node => node.scrollLeft);
    await page.keyboard.press("Space");
    await expect(forward).toBeFocused();
    await expect.poll(() => strip.evaluate(node => node.scrollLeft)).not.toBe(before);
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(control(page, "drawer")).toBeFocused();
    await expect(forward).toBeHidden();
}
module.exports = { desktopRegistry, touchJourney, scrollingControlJourney };
