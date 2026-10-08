const fs = require("node:fs"), path = require("node:path");
const { test, expect } = require("@playwright/test");
const { nativeAnswer } = require("./search");
const { settle } = require("../contrast-targets/measurement");
const generated = path.resolve(process.env.BIJUX_GENERATED_ROOT || path.join(__dirname, "../../../../../artifacts/bijux-docs/generated"));
const manifest = JSON.parse(fs.readFileSync(path.join(generated, "manifest.json")));
const variants = { owned: "/bijux-core/", native: "/fixtures/native-header/", rtl: "/fixtures/rtl/" };
const query = page => page.locator("[data-md-component='search-query']");

async function geometry(page, frames = 1) {
  const records = await page.evaluate(frames => {
    const snapshot = () => {
      const overlay = document.querySelector(".md-search__overlay");
      const style = getComputedStyle(overlay);
      return { width: innerWidth, height: innerHeight, documentWidth: document.documentElement.scrollWidth,
        checked: document.getElementById("__search").checked,
        overlay: overlay.getBoundingClientRect().toJSON(),
        overlayStyle: { position: style.position, transform: style.transform, visibility: style.visibility, pointerEvents: style.pointerEvents },
      };
    };
    // A disabled-script page must not depend on Promise or animation callbacks.
    if (frames === 1) return [snapshot()];
    return new Promise(resolve => {
      const records = [];
      const sample = () => {
        records.push(snapshot());
        if (records.length === frames) resolve(records);
        else requestAnimationFrame(sample);
      };
      sample();
    });
  }, frames);
  for (const record of records) {
    expect(record.documentWidth, "Search must not enlarge document width, including its opening frames").toBeLessThanOrEqual(record.width + 1);
    if (record.checked) {
      expect(record.overlayStyle.position).toBe("fixed");
      expect(record.overlayStyle.transform).toBe("none");
      expect(record.overlay.left).toBeGreaterThanOrEqual(-1);
      expect(record.overlay.right).toBeLessThanOrEqual(record.width + 1);
      expect(record.overlay.width).toBeGreaterThanOrEqual(record.width - 1);
      expect(record.overlay.top).toBeGreaterThanOrEqual(-1);
      expect(record.overlay.bottom).toBeLessThanOrEqual(record.height + 1);
      expect(record.overlay.height).toBeGreaterThanOrEqual(record.height - 1);
    }
  }
  return records;
}

async function hitTarget(target) {
  await expect(target).toBeVisible();
  await target.scrollIntoViewIfNeeded();
  await settle(target);
  expect(await target.evaluate(node => {
    const box = node.getBoundingClientRect();
    const hit = document.elementFromPoint((box.left + box.right) / 2, (box.top + box.bottom) / 2);
    return !!hit && (node === hit || node.contains(hit));
  }), "Viewport backdrop must not cover its native controls or restored reader targets").toBe(true);
}

async function clickVisiblePoint(page, target) {
  await expect(target).toBeVisible();
  // Native input remains available when script-disabled animation callbacks do
  // not provide Playwright's stability oracle. Require the real pointer target.
  let point;
  await expect.poll(async () => target.evaluate(node => {
    const box = node.getBoundingClientRect();
    const x = (box.left + box.right) / 2, y = (box.top + box.bottom) / 2;
    const hit = document.elementFromPoint(x, y);
    return { x, y, hittable: x >= 0 && x < innerWidth && y >= 0 && y < innerHeight && !!hit && (node === hit || node.contains(hit)) };
  }).then(value => { point = value; return value.hittable; })).toBe(true);
  await page.mouse.click(point.x, point.y);
}

async function openSearch(page) {
  const opener = page.locator("[data-bijux-header-control='search-toggle']");
  if (await opener.isVisible()) { await hitTarget(opener); await opener.click(); }
  else { await hitTarget(query(page)); await query(page).click(); }
  await expect(page.locator("#__search")).toBeChecked();
  await expect(query(page)).toBeFocused();
  await hitTarget(query(page));
}

async function closeSearch(page) {
  const close = page.getByRole("button", { name: "Close search", exact: true });
  await hitTarget(close);
  await close.click();
  await expect(page.locator("#__search")).not.toBeChecked();
  await expect(page.locator(".md-content")).not.toHaveAttribute("inert");
}

async function drawerPath(page) {
  const opener = page.locator("[data-bijux-header-control='drawer-toggle']:visible,header label.md-header__button[for='__drawer']:visible").first();
  if (!await opener.count()) return { mode: "persistent sidebar", links: await page.locator(".md-sidebar--primary a:visible").count() };
  await hitTarget(opener);
  await opener.click();
  await expect(page.locator("#__drawer")).toBeChecked();
  const first = page.locator(".md-sidebar--primary a.md-nav__link:visible").first();
  await hitTarget(first);
  const href = await first.getAttribute("href");
  const owned = await page.locator("body").getAttribute("data-bijux-drawer-ready") === "true";
  if (owned) {
    const close = page.getByRole("button", { name: "Close navigation", exact: true });
    await hitTarget(close);
    await close.click();
  } else {
    const backdrop = page.locator(".md-overlay[for='__drawer']");
    const point = await backdrop.evaluate(node => {
      const x = innerWidth - 5, y = innerHeight - 5;
      return { x, y, hittable: document.elementFromPoint(x, y) === node };
    });
    expect(point.hittable).toBe(true);
    await page.mouse.click(point.x, point.y);
  }
  await expect(page.locator("#__drawer")).not.toBeChecked();
  return { mode: owned ? "owned drawer" : "native drawer backdrop", reachableFirstRoute: href,
    standaloneNativeCloseControlQualified: owned ? null : false };
}

async function wheelReader(page) {
  // Pointer preparation can settle Material's sidebar sizing. Measure the
  // document at the input point, rather than retaining its earlier overflow.
  await page.locator(".md-content h1").hover();
  const before = await page.evaluate(() => ({ position: scrollY, maximum: document.scrollingElement.scrollHeight - document.scrollingElement.clientHeight }));
  if (before.maximum > before.position) {
    await page.mouse.wheel(0, 600);
    await expect.poll(() => page.evaluate(() => scrollY)).toBeGreaterThan(before.position);
  }
  return { before, after: await page.evaluate(() => scrollY) };
}

async function readerPath(page, baseURL, route) {
  await page.goto(new URL(`${route}reader-code/`, baseURL).href);
  await expect(page.locator("article .highlight td.code pre > code")).toHaveText(manifest.reader_fixture.code, { useInnerText: false });
  const target = page.getByRole("region", { name: /^Scrollable code example / });
  const result = { width: await page.evaluate(() => innerWidth), horizontalRegion: await target.count() };
  if (result.horizontalRegion) {
    await target.click();
    await expect(target).toBeFocused();
    await page.keyboard.press("End");
    await expect.poll(() => target.evaluate(node => Math.abs(node.scrollLeft) >= node.scrollWidth - node.clientWidth - 1)).toBe(true);
    result.scroll = await target.evaluate(node => ({ left: node.scrollLeft, maximum: node.scrollWidth - node.clientWidth }));
  }
  const codeScroll = await wheelReader(page);
  result.pageScrollAvailable = codeScroll.before.maximum;
  result.pageScroll = codeScroll.after;
  result.geometry = await geometry(page);
  // A short code page may fit entirely after layout settles. The authored long
  // reading page must still prove ordinary vertical scrolling independently.
  await page.goto(new URL(`${route}reading/`, baseURL).href);
  await expect(page.locator(".md-content h1")).toContainText("Rich reading reference");
  const longReader = await wheelReader(page);
  expect(longReader.before.maximum, "The long reading fixture must provide real document scrolling").toBeGreaterThan(longReader.before.position);
  expect(longReader.after, "Ordinary wheel input must scroll the long reading document").toBeGreaterThan(longReader.before.position);
  result.longReader = { ...longReader, url: page.url(), geometry: await geometry(page) };
  return result;
}

function defineSearchReflow(widths) {
for (const width of widths) {
  test(`${width}px preserves native search geometry and independent reader paths`, async ({ browser }, info) => {
    info.annotations.push({ type: "browser-version", description: browser.version() });
    const evidence = { width, engine: info.project.use.browserName, version: browser.version(), sourceSHA: manifest.source_sha,
      sourceTreeDirty: manifest.source_tree_dirty, variants: [], liveManualAAQualified: false };
    try {
      for (const [kind, route] of Object.entries(variants)) {
        const context = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: width < 768 });
        const page = await context.newPage();
        const record = { kind, route, errors: [], frames: {} };
        evidence.variants.push(record);
        page.on("pageerror", error => record.errors.push(error.message));
        let documentIdentity;
        try {
          await page.goto(new URL(route, info.project.use.baseURL).href);
          await expect(page.locator("main")).toBeVisible();
          documentIdentity = await page.evaluateHandle(() => document);
          record.frames.closed = await geometry(page);
          await openSearch(page);
          record.frames.opening = await geometry(page, 12);
          await query(page).fill("resilient navigation");
          const answer = await nativeAnswer(page);
          record.frames.results = await geometry(page);
          await hitTarget(answer);
          const scroll = page.locator(".md-search__scrollwrap");
          await scroll.hover();
          await page.mouse.wheel(0, 500);
          await expect.poll(() => scroll.evaluate(node => node.scrollTop)).toBeGreaterThan(0);
          record.resultsScroll = await scroll.evaluate(node => ({ top: node.scrollTop, maximum: node.scrollHeight - node.clientHeight }));
          await answer.scrollIntoViewIfNeeded();
          await query(page).click();
          for (let step = 0; step < 40 && !(await answer.evaluate(node => node === document.activeElement)); step++) await page.keyboard.press("ArrowDown");
          await expect(answer).toBeFocused();
          const destination = await answer.getAttribute("href");
          await page.keyboard.press("Enter");
          await expect(page).toHaveURL(destination);
          expect(await page.evaluate(original => original === document, documentIdentity)).toBe(true);
          await expect(page.locator(".md-content h1")).toContainText("leaf destination");
          record.frames.destination = await geometry(page);
          await page.goBack();
          await expect(page).toHaveURL(new URL(route, info.project.use.baseURL).href);
          expect(await page.evaluate(original => original === document, documentIdentity)).toBe(true);
          await openSearch(page);
          record.frames.history = await geometry(page, 12);
          if (width >= 960) {
            const backdrop = page.locator(".md-search__overlay");
            const point = await backdrop.evaluate(node => {
              const x = 5, y = innerHeight - 5;
              return { x, y, hittable: document.elementFromPoint(x, y) === node };
            });
            expect(point.hittable).toBe(true);
            await page.mouse.click(point.x, point.y);
            await expect(page.locator("#__search")).not.toBeChecked();
            record.desktopBackdropDismissed = true;
            await openSearch(page);
          }
          const resizedWidth = width < 960 ? 960 : 959;
          await page.setViewportSize({ width: resizedWidth, height: 900 });
          if (!await page.locator("#__search").isChecked()) await openSearch(page);
          record.frames.resized = await geometry(page, 12);
          await closeSearch(page);
          record.frames.closedResized = await geometry(page);
          await page.setViewportSize({ width, height: 900 });
          await openSearch(page);
          await page.keyboard.press("Escape");
          await expect(page.locator("#__search")).not.toBeChecked();
          record.frames.escape = await geometry(page);
          record.drawer = await drawerPath(page);
          record.reader = await readerPath(page, info.project.use.baseURL, route);
          const noJS = await browser.newContext({ viewport: { width, height: 900 }, javaScriptEnabled: false });
          try {
            const noJSPage = await noJS.newPage();
            await noJSPage.goto(new URL(route, info.project.use.baseURL).href);
            await expect(noJSPage.locator("html")).toHaveClass(/no-js/);
            await expect(query(noJSPage)).toBeHidden();
            const checkbox = noJSPage.locator("#__drawer");
            const nativeLabel = noJSPage.locator("header label.md-header__button[for='__drawer']:visible").first();
            if (await checkbox.isVisible()) await clickVisiblePoint(noJSPage, checkbox);
            else if (await nativeLabel.count()) await clickVisiblePoint(noJSPage, nativeLabel);
            const summary = noJSPage.locator(".md-sidebar--primary summary:visible").first();
            if (await summary.count() && !await summary.evaluate(node => node.parentElement.open)) {
              await clickVisiblePoint(noJSPage, summary);
              await expect.poll(() => summary.evaluate(node => node.parentElement.open)).toBe(true);
            }
            const link = noJSPage.locator(".md-sidebar--primary .md-nav__link:visible").filter({ hasText: /^\s*Getting started\s*$/ }).first();
            const destination = await link.evaluate(node => node.href);
            await clickVisiblePoint(noJSPage, link);
            await expect(noJSPage).toHaveURL(destination);
            await expect(noJSPage.locator(".md-content h1")).toContainText("getting started");
            record.noJS = { searchHidden: true, destination, nativeRouteActivated: true, geometry: await geometry(noJSPage) };
          } finally { await noJS.close(); }
          expect(record.errors).toEqual([]);
          record.status = "passed";
        } finally {
          if (documentIdentity) await documentIdentity.dispose();
          await context.close();
        }
      }
      evidence.status = "passed";
    } catch (error) {
      evidence.status = "failed";
      evidence.failure = { message: error.message, stack: error.stack };
      throw error;
    } finally {
      fs.writeFileSync(info.outputPath("search-reflow-evidence.json"), JSON.stringify(evidence, null, 2) + "\n");
      await info.attach("search-reflow-evidence", { body: Buffer.from(JSON.stringify(evidence, null, 2)), contentType: "application/json" });
    }
  });
}

}
module.exports = { defineSearchReflow };
