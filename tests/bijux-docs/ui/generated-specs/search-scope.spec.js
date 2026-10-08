const fs = require("node:fs");
const path = require("node:path");
const { test, expect, ready } = require("./helpers/document");
const { nativeAnswer } = require("./helpers/search");
const generated = path.resolve(process.env.BIJUX_GENERATED_ROOT || path.join(__dirname, "../../../../artifacts/bijux-docs/generated"));
const manifest = JSON.parse(fs.readFileSync(path.join(generated, "manifest.json")));
const consumers = manifest.scenarios.filter(scenario => ["hub", "project"].includes(scenario.kind));
if (consumers.length !== 9 || new Set(consumers.map(scenario => scenario.route)).size !== 9) throw new Error("Search scope requires all nine declared consumer-root fixtures");
const query = page => page.locator("[data-md-component='search-query']");

async function openSearch(page) {
  const opener = page.locator("[data-bijux-header-control='search-toggle']");
  if (await opener.isVisible()) await opener.click();
  else await query(page).click();
  await expect(page.locator("#__search")).toBeChecked();
  await expect(query(page)).toBeFocused();
}

async function scopeState(page, siteName) {
  const scope = page.locator("#bijux-search-scope");
  await expect(scope).toHaveCount(1);
  await expect(scope).toHaveText(`Results from ${siteName} only.`);
  await expect(scope).toBeVisible();
  await expect(scope).toBeInViewport();
  await expect(query(page)).toHaveAttribute("aria-label", `Search ${siteName}`);
  await expect(query(page)).toHaveAttribute("placeholder", `Search ${siteName}`);
  await expect(query(page)).toHaveAttribute("aria-describedby", "bijux-search-scope");
  await expect.poll(() => scope.evaluate(node => {
    const rect = node.getBoundingClientRect();
    return rect.width > 0 && rect.left >= -1 && rect.right <= innerWidth + 1 && node.scrollWidth <= node.clientWidth;
  }), { message: "The local scope must fit after native search animation settles" }).toBe(true);
  return scope.evaluate(node => ({
    text: node.textContent.trim(),
    nonfocusable: node.tabIndex === -1,
    descriptionReachable: document.getElementById(document.querySelector("[data-md-component='search-query']").getAttribute("aria-describedby")) === node,
    scopeWidth: node.getBoundingClientRect().width,
    viewportWidth: innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    globalDocumentReflowQualified: false,
  }));
}

for (const consumer of consumers) {
  test(`${consumer.identity} names its native search through results and document history`, async ({ page, browser }, info) => {
    const siteName = consumer.identity === "bijux" ? "Bijux" : consumer.identity;
    const evidence = { consumer, siteName, sourceSHA: manifest.source_sha, sourceTreeDirty: manifest.source_tree_dirty,
      observedIndexRequests: [], states: {}, errors: [], missing: [],
      globalDocumentReflowQualified: false, actualConsumerPublicationQualified: false,
      physicalManualEditorialQualified: false };
    page.on("request", request => { if (request.url().includes("/search/search_index.")) evidence.observedIndexRequests.push(request.url()); });
    page.on("response", response => { if (new URL(response.url()).origin === new URL(info.project.use.baseURL).origin && response.status() >= 400) evidence.missing.push({ url: response.url(), status: response.status() }); });
    let documentIdentity;
    let noJSContext;
    try {
      await ready(page, consumer.route);
      documentIdentity = await page.evaluateHandle(() => document);
      await openSearch(page);
      await query(page).fill("");
      evidence.states.empty = await scopeState(page, siteName);
      await page.keyboard.insertText("resilient navigation");
      const answer = await nativeAnswer(page);
      evidence.states.results = await scopeState(page, siteName);
      const destination = await answer.getAttribute("href");
      for (let step = 0; step < 40 && !(await answer.evaluate(node => node === document.activeElement)); step++) await page.keyboard.press("ArrowDown");
      await expect(answer).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(page).toHaveURL(destination);
      await expect(page.locator(".md-content h1")).toContainText("leaf destination");
      expect(await page.evaluate(original => original === document, documentIdentity)).toBe(true);
      await openSearch(page);
      evidence.states.destination = await scopeState(page, siteName);
      await page.keyboard.press("Escape");
      await expect(page.locator("#__search")).not.toBeChecked();
      await page.goBack();
      await expect(page).toHaveURL(new URL(consumer.route, info.project.use.baseURL).href);
      expect(await page.evaluate(original => original === document, documentIdentity)).toBe(true);
      await openSearch(page);
      evidence.states.history = await scopeState(page, siteName);
      await query(page).fill("zzbijuxscopenomatch752");
      await expect.poll(() => page.evaluate(() => window.bijuxSearchWorker?.state.stage)).toBe("worker-ready");
      await expect(page.locator(".md-search-result__meta")).toHaveText("No matching documents");
      await expect(page.locator(".md-search-result__link")).toHaveCount(0);
      evidence.states.noResult = await scopeState(page, siteName);
      await query(page).fill("");
      await expect(page.locator(".md-search-result__link")).toHaveCount(0);
      evidence.states.cleared = await scopeState(page, siteName);
      expect(evidence.observedIndexRequests.length).toBeGreaterThan(0);
      for (const url of evidence.observedIndexRequests) expect(new URL(url).pathname).toBe(`${consumer.route}search/search_index.json`);
      for (const state of Object.values(evidence.states)) {
        expect(state.nonfocusable).toBe(true);
        expect(state.descriptionReachable).toBe(true);
      }
      noJSContext = await browser.newContext({ javaScriptEnabled: false, viewport: info.project.use.viewport });
      const noJSPage = await noJSContext.newPage();
      noJSPage.on("pageerror", error => evidence.errors.push(error.message));
      await noJSPage.goto(new URL(consumer.route, info.project.use.baseURL).href);
      await expect(noJSPage.locator("html")).toHaveClass(/no-js/);
      await expect(query(noJSPage)).toBeHidden();
      await expect(noJSPage.locator("[data-bijux-header-control='search-toggle']")).toBeHidden();
      await expect(noJSPage.locator("#bijux-search-scope")).toHaveCount(1);
      await expect(noJSPage.locator("#bijux-search-scope")).toHaveText(`Results from ${siteName} only.`);
      evidence.noJS = { namedScopePresent: true, queryHidden: true, searchOpenerHidden: true, addedSearchCapability: false };
      expect(evidence.errors).toEqual([]);
      expect(evidence.missing).toEqual([]);
      evidence.status = "passed";
    } catch (error) {
      evidence.status = "failed";
      evidence.failure = { message: error.message, stack: error.stack };
      throw error;
    } finally {
      if (documentIdentity) await documentIdentity.dispose();
      if (noJSContext) await noJSContext.close();
      await info.attach("search-scope-evidence", { body: Buffer.from(JSON.stringify(evidence, null, 2)), contentType: "application/json" });
    }
  });
}
