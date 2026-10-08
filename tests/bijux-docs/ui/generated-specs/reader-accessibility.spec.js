const { test, expect, control, navigation, ready, phone, openDrawer } = require("./helpers/document");

async function hitTarget(link) {
  await expect(link).toBeInViewport();
  await expect.poll(() => link.evaluate(node => {
    const box = node.getBoundingClientRect();
    const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
    return box.x >= 0 && box.y >= 0 && box.right <= innerWidth + 1 && box.bottom <= innerHeight + 1 && (hit === node || node.contains(hit));
  }), { message: "The intended destination has an ordinary unoccluded hit target" }).toBe(true);
}

async function reading(page, link) {
  const destination = await link.evaluate(node => node.href);
  await link.click();
  await expect(page).toHaveURL(destination);
  await expect(page.locator("main h1")).toBeFocused();
  await expect(page.locator("main h1")).toContainText("Rich reading reference");
  await expect(page).toHaveTitle(/Reading reference/);
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", false);
  await expect(page.locator("#__drawer")).not.toBeChecked();
}

async function visibleFragment(page, heading) {
  await page.evaluate(() => document.fonts.ready);
  await expect(heading).toBeInViewport();
  await expect.poll(() => heading.evaluate(node => {
    const box = node.getBoundingClientRect();
    const headers = [...document.querySelectorAll("header, .md-tabs")].filter(element => {
      const style = getComputedStyle(element), rect = element.getBoundingClientRect();
      return ["fixed", "sticky"].includes(style.position) && style.visibility === "visible" && rect.width > 0 && rect.height > 0 && rect.y <= 1;
    });
    const bottom = Math.max(0, ...headers.map(element => element.getBoundingClientRect().bottom));
    return box.top >= bottom - 1 && box.bottom <= innerHeight;
  })).toBe(true);
  expect(await page.evaluate(() => {
    const node = document.activeElement;
    return node.isConnected && !node.closest("[inert]") && (node === document.body || node.getClientRects().length > 0);
  }), "History retains connected focus outside hidden and inert surfaces").toBe(true);
}

test("short landscape keeps the masthead bounded and the final registry destination reachable", async ({ page }) => {
  await page.setViewportSize({ width: 568, height: 320 });
  await ready(page, "/fixtures/long-registry/");
  expect(await page.locator("header").first().evaluate(node => node.getBoundingClientRect().height)).toBeLessThanOrEqual(64);
  await openDrawer(page);
  const last = navigation(page).getByRole("link", { name: "Research extension", exact: true });
  const key = test.info().project.use.browserName === "webkit" ? "Alt+Tab" : "Tab";
  const section = navigation(page).locator("summary").filter({ hasText: /^\s*Platform\s*$/ });
  for (let index = 0; index < 32 && !await section.evaluate(node => node === document.activeElement); index++) await page.keyboard.press(key);
  await expect(section).toBeFocused();
  await page.keyboard.press("Space");
  await expect.poll(() => section.evaluate(node => node.parentElement.open)).toBe(true);
  await page.keyboard.press(key);
  const overview = section.locator("..").getByRole("link", { name: "Overview", exact: true }).first();
  await expect(overview).toBeFocused();
  await hitTarget(overview);
  await page.keyboard.press(test.info().project.use.browserName === "webkit" ? "Alt+Shift+Tab" : "Shift+Tab");
  await expect(section).toBeFocused();
  await page.keyboard.press("Space");
  await expect.poll(() => section.evaluate(node => node.parentElement.open)).toBe(false);
  for (let index = 0; index < 160 && !await last.evaluate(node => node === document.activeElement); index++) await page.keyboard.press(key);
  await expect(last).toBeFocused();
  await hitTarget(last);
  await last.click();
  await expect(page).toHaveURL(/\/reading\/$/);
  await expect(page.locator("main h1")).toContainText("Rich reading reference");
});

test("the actual RTL owned drawer mirrors its panel and reaches ordinary reading", async ({ page }) => {
  await phone(page, "/fixtures/rtl/");
  await expect(page.locator("body")).toHaveAttribute("dir", "rtl");
  expect(await page.locator("body").evaluate(node => getComputedStyle(node).direction)).toBe("rtl");
  await openDrawer(page);
  await expect.poll(async () => {
    const box = await page.locator(".md-sidebar--primary").boundingBox();
    return box.x >= -1 && Math.abs(box.x + box.width - page.viewportSize().width) <= 1;
  }).toBe(true);
  await reading(page, navigation(page).getByRole("link", { name: "Reading reference", exact: true }));
});

test("owned modal resize restores usable desktop content and connected visible focus", async ({ page }) => {
  await phone(page);
  await openDrawer(page);
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", true);
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.locator("#__drawer")).not.toBeChecked();
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", false);
  await expect(page.locator(".md-sidebar--primary")).not.toHaveAttribute("aria-modal", "true");
  await expect(navigation(page).locator(".bijux-tree")).toBeVisible();
  expect(await page.evaluate(() => {
    const node = document.activeElement;
    return node.isConnected && !node.closest("[inert]") && (node === document.body || node.getClientRects().length > 0);
  })).toBe(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await control(page, "drawer").click();
  await expect(page.locator("#__drawer")).toBeChecked();
  await page.keyboard.press("Escape");
  await expect(control(page, "drawer")).toBeFocused();
});

test("intentional drawer reading navigation updates title focus and noninert main context", async ({ page }) => {
  await phone(page);
  await openDrawer(page);
  await reading(page, navigation(page).getByRole("link", { name: "Reading reference", exact: true }));
});

test("a direct product fragment and reader Back keep the heading below the sticky masthead", async ({ page }) => {
  await phone(page, "/bijux-core/platform/details/leaf/#detailed-heading");
  const original = page.url(), heading = page.locator("#detailed-heading");
  const document = await page.evaluateHandle(() => window.document);
  await visibleFragment(page, heading);
  await openDrawer(page);
  await reading(page, navigation(page).getByRole("link", { name: "Reading reference", exact: true }));
  expect(await document.evaluate(node => node === window.document)).toBe(true);
  await page.goBack();
  await expect(page).toHaveURL(original);
  await visibleFragment(page, heading);
  expect(await document.evaluate(node => node === window.document)).toBe(true);
  await document.dispose();
});
