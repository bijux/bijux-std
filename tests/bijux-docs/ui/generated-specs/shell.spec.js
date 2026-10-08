const fs = require("node:fs");
const path = require("node:path");
const registry = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../../../../shared/bijux-docs/config/hub-links.json"), "utf8"));
const { test, expect } = require("./helpers/document");
const { tabTo } = require("./contrast-targets/measurement");
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
async function registryDestination(page, link, expected) {
  await expect(link).toHaveCount(1);
  await expect(link).toHaveAccessibleName(expected.label);
  expect(await link.evaluate(node => node.href)).toBe(expected.url);
  await link.hover();
  const target = await link.evaluate(node => {
    const rect = node.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
    return { width: rect.width, height: rect.height, owned: hit === node || node.contains(hit),
      fit: rect.left >= 0 && rect.right <= innerWidth + 1 && rect.top >= 0 && rect.bottom <= innerHeight + 1,
      labelFit: node.scrollWidth <= node.clientWidth && node.scrollHeight <= node.clientHeight };
  });
  expect(target.height).toBeGreaterThanOrEqual(44);
  expect(target.width).toBeGreaterThanOrEqual(44);
  expect(target.owned).toBe(true);
  expect(target.fit).toBe(true);
  expect(target.labelFit).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  const previousDocument = await page.evaluateHandle(() => document);
  const documentRequests = [];
  let retainedDocument;
  const observeDocument = request => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documentRequests.push(request.url());
  };
  page.on("request", observeDocument);
  try {
    await link.click();
    await expect(page).toHaveURL(expected.url);
    await expect(page.locator("main h1")).toHaveText(expected.heading);
    try {
      retainedDocument = await previousDocument.evaluate(original => original === document);
    } catch (error) {
      // Only a destroyed former context and a genuine completed document load
      // establish native navigation; an attempted or aborted request does not.
      if (!documentRequests.length || !/Execution context was destroyed|JSHandles can be evaluated only in the context|Execution context is not available|Cannot find context/.test(error.message)) throw error;
      await page.waitForLoadState("domcontentloaded");
      retainedDocument = false;
    }
  } finally {
    page.off("request", observeDocument);
    await previousDocument.dispose();
  }
  await expect(page.locator("main h1")).toHaveText(expected.heading);
  // Cross-site registry links may use a native document navigation. Retained
  // document reading journeys own H1 focus; native navigation owns page context.
  if (retainedDocument) await expect(page.locator("main h1")).toBeFocused();
  await expect(page).toHaveTitle(expected.title);
  expect(await page.evaluate(() => document.activeElement.isConnected)).toBe(true);
  await expect(page.locator("#__drawer")).not.toBeChecked();
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", false);
  await openDrawer(page);
  const current = drawer(page).locator(".bijux-mobile-hub__link[aria-current='location']");
  await expect(current).toHaveCount(1);
  expect(await current.evaluate(node => node.href)).toBe(expected.currentURL || expected.url);
  const incorrect = await drawer(page).locator("a[aria-current='page']").evaluateAll(nodes =>
    nodes.filter(node => node.getClientRects().length && new URL(node.href).pathname !== location.pathname)
      .map(node => ({ name: node.textContent.trim(), href: node.href })));
  expect(incorrect).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(control(page, "drawer")).toBeFocused();
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
    if (width >= 1220) {
      await expect(page.locator("header .bijux-hub-strip")).toBeVisible();
      await expect(page.locator(".md-sidebar--primary .bijux-site-registry")).toBeHidden();
    } else {
      await openDrawer(page);
      const tabs = page.locator("header .bijux-site-tabs");
      await expect(tabs).toHaveJSProperty("inert", true);
      await page.keyboard.press("Escape");
      await expect(tabs).toHaveJSProperty("inert", false);
      await expect(control(page, "drawer")).toBeFocused();
    }
  }
});
test("phone brand and visually hidden helper text preserve useful space", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  const logoResponse = page.waitForResponse(response => new URL(response.url()).pathname.endsWith("/assets/bijux_logo.png"));
  await ready(page);
  const imageResponse = await logoResponse;
  expect(imageResponse.ok()).toBe(true);
  expect((await imageResponse.body()).length).toBeLessThanOrEqual(32 * 1024);
  const helper = control(page, "drawer").locator(".md-visually-hidden");
  if (await helper.count()) {
    const box = await helper.boundingBox();
    expect(box?.width || 0).toBeLessThanOrEqual(1);
    expect(box?.height || 0).toBeLessThanOrEqual(1);
  }
  const title = page.locator("[data-bijux-header-topic='site'] .md-ellipsis");
  expect(await title.evaluate((node) => node.clientWidth)).toBeGreaterThanOrEqual(40);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await openDrawer(page);
  const brand = drawer(page).locator(".bijux-nav__title > a.md-logo");
  await expect(brand).toHaveAccessibleName(/\S/);
  const logo = brand.locator("img");
  await expect(logo).toHaveAttribute("alt", "");
  await expect(logo).toHaveAttribute("width", "48");
  await expect(logo).toHaveAttribute("height", "48");
  await expect.poll(() => logo.evaluate(image => image.complete && image.naturalWidth === 128 && image.naturalHeight === 128)).toBe(true);
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
test("all nine shared site destinations are reachable from phone drawer", async ({ page }, info) => {
  expect(registry).toHaveLength(9);
  for (const destination of registry) {
    await phone(page);
    await openDrawer(page);
    await expect(drawer(page).locator(".bijux-mobile-hub__link:visible")).toHaveCount(9);
    const route = destination.key === "bijux" ? "/" : `/${destination.key}/`;
    await registryDestination(page, drawer(page).locator(".bijux-site-registry").getByRole("link", { name: destination.label, exact: true }), {
      label: destination.label,
      url: new URL(route, info.project.use.baseURL).href,
      heading: destination.key === "bijux" ? /^Bijux reference(?:¶)?$/ : /^Product overview(?:¶)?$/,
      title: destination.key === "bijux" ? "Bijux" : destination.key,
    });
  }
});
test("deep documents have truthful current page state", async ({ page }) => {
  await ready(page, "/bijux-core/platform/details/leaf/");
  const incorrect = await page.locator("a[aria-current='page']").evaluateAll((links) => links.filter((link) => {
    const rect = link.getBoundingClientRect();
    return rect.width > 0 && rect.height > 0 && new URL(link.href).pathname.replace(/\/+$/, "") !== location.pathname.replace(/\/+$/, "");
  }).map((link) => ({ name: link.textContent.trim(), href: link.href })));
  expect(incorrect).toEqual([]);
  if (page.viewportSize().width >= 1220) {
    await expect(drawer(page).locator("a[aria-current='page']")).toBeVisible();
    const alternatives = page.locator("header .bijux-site-tabs a, header .bijux-detail-tabs a, header .bijux-course-tabs a, header .bijux-detail-select");
    expect(await alternatives.evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).length)).toBe(0);
    expect(await alternatives.evaluateAll(nodes => nodes.every(node => {
      node.focus();
      return document.activeElement !== node;
    }))).toBe(true);
    const reading = drawer(page).locator("a").filter({ hasText: /^\s*Reading reference\s*$/ });
    await tabTo(page, reading, test.info().project.use.browserName, 160);
    await expect(reading).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/bijux-core\/reading\/$/);
    await page.goBack();
    await expect(page).toHaveURL(/\/bijux-core\/platform\/details\/leaf\/$/);
    await expect(drawer(page).locator("a[aria-current='page']")).toBeVisible();
  }
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
test("empty and expanded-registry fixtures retain useful navigation", async ({ page }, info) => {
  for (const route of ["/fixtures/empty/", "/fixtures/long-registry/"]) {
    await phone(page, route);
    await openDrawer(page);
    expect(await exposedLinks(page).count()).toBeGreaterThan(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  }
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
  for (const entry of expected) {
    await phone(page, "/fixtures/long-registry/");
    await openDrawer(page);
    await expect(drawer(page).locator(".bijux-mobile-hub__link:visible")).toHaveCount(11);
    await registryDestination(page, drawer(page).locator(".bijux-site-registry").getByRole("link", { name: entry.label, exact: true }), entry);
  }
});
test("no-script generated document retains ordinary destination links", async ({ browser }, info) => {
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 390, height: 844 } });
  try {
    const page = await context.newPage();
    await page.goto(new URL("/", info.project.use.baseURL).href);
    const toggle = page.getByRole("checkbox", { name: "Navigation", exact: true });
    await expect(toggle).toBeVisible();
    await toggle.click();
    await expect(toggle).toBeChecked();
    await expect(exposedLinks(page).first()).toBeInViewport();
    expect(await exposedLinks(page).count()).toBeGreaterThan(1);
    const geometry = await drawer(page).evaluate(node => {
      const bounds = node.getBoundingClientRect();
      return { position: getComputedStyle(node).position, left: bounds.left, right: bounds.right,
        width: innerWidth, documentWidth: document.documentElement.scrollWidth };
    });
    expect(geometry.position).toBe("static");
    expect(geometry.left).toBeGreaterThanOrEqual(-1);
    expect(geometry.right).toBeLessThanOrEqual(geometry.width + 1);
    expect(geometry.documentWidth).toBeLessThanOrEqual(geometry.width + 1);
    for (const width of [768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(new URL("/", info.project.use.baseURL).href);
      const localRows = page.locator("header .bijux-site-tabs, header .bijux-detail-tabs, header .bijux-course-tabs");
      if (width === 768) {
        const toggle = page.getByRole("checkbox", { name: "Navigation", exact: true });
        expect(await localRows.evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).length)).toBe(1);
        await toggle.click();
        expect(await localRows.evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).length)).toBe(0);
        await toggle.click();
        expect(await localRows.evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).length)).toBe(1);
        await toggle.click();
      }
      await expect(drawer(page)).toBeVisible();
      expect(await localRows.evaluateAll(nodes => nodes.filter(node => node.getClientRects().length).length)).toBe(0);
      const reading = drawer(page).locator("a").filter({ hasText: /^\s*Reading reference\s*$/ });
      await reading.click();
      await expect(page).toHaveURL(/\/reading\/$/);
      await expect(page.locator("h1")).toBeVisible();
    }
  } finally {
    await context.close();
  }
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
