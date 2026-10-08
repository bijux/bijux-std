const { test, expect } = require("@playwright/test");
test.beforeEach(async ({ browser }, testInfo) => {
  testInfo.annotations.push({ type: "browser-version", description: browser.version() });
});
const control = (page, kind) => page.locator(`[data-bijux-header-control='${kind}-toggle']`);
const drawer = (page) => page.locator(".md-sidebar--primary");
const exposedLinks = (page) => drawer(page).locator("a:visible");
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
  await expect(exposedLinks(page).first()).toBeInViewport();
}
test("inactive navigation strips remain absent at every responsive boundary", async ({ page }) => {
  for (const width of [320, 767, 768, 820, 1024, 1219, 1220, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await ready(page);
    const hidden = page.locator("[data-bijux-detail-strip][hidden], [data-bijux-course-strip][hidden]");
    expect(await hidden.count()).toBeGreaterThan(0);
    const painted = await hidden.evaluateAll((nodes) => nodes.filter((node) => node.getClientRects().length && getComputedStyle(node).visibility !== "hidden").length);
    expect(painted, `Hidden navigation painted at ${width}px`).toBe(0);
    const height = await page.locator("header").first().evaluate((node) => node.getBoundingClientRect().height);
    expect(height, `Masthead height at ${width}px`).toBeLessThanOrEqual(width < 768 ? 72 : width < 1220 ? 112 : 160);
  }
});
test("phone brand and visually hidden helper text preserve useful space", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await ready(page);
  const helper = control(page, "drawer").locator(".md-visually-hidden");
  if (await helper.count()) {
    const box = await helper.boundingBox();
    expect(box?.width || 0).toBeLessThanOrEqual(1);
    expect(box?.height || 0).toBeLessThanOrEqual(1);
  }
  const title = page.locator("[data-bijux-header-topic='site'] .md-ellipsis");
  expect(await title.evaluate((node) => node.clientWidth)).toBeGreaterThanOrEqual(40);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
});
test("tablet drawer exposes real destinations through ordinary pointer input", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 900 });
  await ready(page);
  await openDrawer(page);
  expect(await exposedLinks(page).count()).toBeGreaterThan(1);
});
test("drawer opens on Space from a known closed state", async ({ page }) => {
  await phone(page);
  await expect(page.locator("#__drawer")).not.toBeChecked();
  await control(page, "drawer").focus();
  await page.keyboard.press("Space");
  await expect(page.locator("#__drawer")).toBeChecked();
  await expect(exposedLinks(page).first()).toBeInViewport();
});
test("drawer opens on Enter from a known closed state", async ({ page }) => {
  await phone(page);
  await control(page, "drawer").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("#__drawer")).toBeChecked();
  await expect(exposedLinks(page).first()).toBeInViewport();
});
test("Escape dismisses drawer and restores its trigger", async ({ page }) => {
  await phone(page);
  await openDrawer(page);
  await page.keyboard.press("Escape");
  await expect(page.locator("#__drawer")).not.toBeChecked();
  await expect(control(page, "drawer")).toBeFocused();
});
test("parent overview remains a real navigation destination", async ({ page }) => {
  await phone(page);
  await openDrawer(page);
  await drawer(page).locator("summary").filter({ hasText: /^Platform$/ }).click();
  const destination = drawer(page).locator("a[href='platform/'], a[href$='/platform/']").filter({ hasText: /^\s*Overview\s*$/ }).first();
  await destination.click();
  await expect(page).toHaveURL(/\/platform\/$/);
  await expect(page.locator("h1")).toHaveText(/^Platform overview(?:¶)?$/);
});
test("all nine shared site destinations are reachable from phone drawer", async ({ page }) => {
  await phone(page);
  await openDrawer(page);
  const sites = drawer(page).locator(".bijux-mobile-hub__link:visible");
  await expect(sites).toHaveCount(9);
  await sites.filter({ hasText: /^Core$/ }).click();
  await expect(page).toHaveURL(/\/bijux-core\/$/);
  await expect(page.locator("h1")).toHaveText(/^Product overview(?:¶)?$/);
});
test("deep documents have truthful current page state", async ({ page }) => {
  await ready(page, "/bijux-core/platform/details/leaf/");
  const incorrect = await page.locator("a[aria-current='page']").evaluateAll((links) => links.filter((link) => {
    const rect = link.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && new URL(link.href).pathname.replace(/\/+$/, "") !== location.pathname.replace(/\/+$/, "");
  }).map((link) => ({ name: link.textContent.trim(), href: link.href })));
  expect(incorrect).toEqual([]);
});
test("resize and history preserve shell without uncaught errors", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await ready(page, "/platform/");
  for (const width of [1440, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(page.locator("main")).toBeVisible();
  }
  await page.locator("main a[href]").filter({ hasText: "Getting started" }).first().click();
  await expect(page).toHaveURL(/\/platform\/start\/$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/platform\/$/);
  expect(errors).toEqual([]);
});
test("search initialization yields a real known-answer result", async ({ page }) => {
  await phone(page, "/bijux-core/");
  await control(page, "search").click();
  await page.locator("[data-md-component='search-query']").pressSequentially("resilient navigation");
  await expect(page.locator(".md-search-result__link").first()).toBeVisible();
  await page.locator(".md-search-result__link").first().click();
  await expect(page).toHaveURL(/\/bijux-core\//);
  await expect(page.locator("main")).toContainText("resilient navigation");
});
test("rich content renders actual Material enhancements", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await ready(page, "/reading/");
  await expect(page.locator(".mermaid svg")).toBeVisible();
  await page.getByText("Reader disclosure", { exact: true }).click();
  await expect(page.getByText("Important nested reading content remains available.")).toBeVisible();
  await expect(page.locator("table")).toContainText("Measurement");
  expect(errors).toEqual([]);
});
test("empty and expanded-registry fixtures retain useful navigation", async ({ page }) => {
  for (const route of ["/fixtures/empty/", "/fixtures/long-registry/"]) {
    await phone(page, route);
    await openDrawer(page);
    expect(await exposedLinks(page).count()).toBeGreaterThan(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  }
});
test("no-script generated document retains ordinary destination links", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:4173/");
  await control(page, "drawer").click();
  await expect(page.locator("#__drawer")).toBeChecked();
  await expect(exposedLinks(page).first()).toBeInViewport();
  expect(await exposedLinks(page).count()).toBeGreaterThan(1);
  await context.close();
});

test("disclosure keyboard changes expansion without swallowing overview navigation", async ({ page }) => {
  await phone(page);
  await openDrawer(page);
  const summary = drawer(page).locator("summary").filter({ hasText: /^Platform$/ });
  const group = summary.locator("..");
  await summary.focus();
  await page.keyboard.press("Space");
  await expect(group).toHaveAttribute("open", "");
  await page.keyboard.press("Enter");
  await expect(group).not.toHaveAttribute("open", "");
  await expect(summary).toBeFocused();
});

test("all declared consumer roots serve admitted shell and search data", async ({ page }) => {
  const fs = require("fs"), path = require("path");
  const root = process.env.BIJUX_GENERATED_ROOT || path.resolve(__dirname, "../../../../artifacts/bijux-docs/generated");
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json")));
  const consumers = manifest.scenarios.filter((entry) => ["hub", "project"].includes(entry.kind));
  expect(consumers).toHaveLength(9);
  for (const entry of consumers) {
    await ready(page, entry.route);
    await expect(page.locator("[data-bijux-active-repository]")).toHaveAttribute("data-bijux-active-repository", entry.identity);
    const response = await page.request.get(`${entry.route}search/search_index.json`);
    expect(response.status()).toBe(200);
    expect((await response.json()).docs.length).toBeGreaterThan(0);
  }
});
