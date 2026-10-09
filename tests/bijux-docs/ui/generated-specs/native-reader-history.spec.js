const { test, expect } = require("./helpers/document");
const { observeRoute } = require("./history/observations");

const article = page => page.locator(".md-content article");
const figures = page => article(page).locator(".bijux-diagram");
const reader = origin => origin + "/reader-diagrams/";
const checkpoint = origin => origin + "/reader-table/";

async function rendered(page) {
  await expect(figures(page)).toHaveCount(5);
  await expect(figures(page).locator(".bijux-diagram-preview > svg")).toHaveCount(5);
  await expect(figures(page).locator("details[open]")).toHaveCount(0);
}

async function openReader(page, origin) {
  await page.goto(reader(origin));
  await expect(page.locator("body")).toHaveAttribute("data-bijux-drawer-ready", "true");
  await rendered(page);
  return figures(page).locator(".bijux-diagram-source code").allTextContents();
}

async function attach(info, records) {
  await info.attach("native-diagram-reader-observations", {
    body: Buffer.from(JSON.stringify(records, null, 2)),
    contentType: "application/json",
  });
}

async function position(link) {
  return link.evaluate(node => ({
    url: location.href,
    y: scrollY,
    height: document.documentElement.scrollHeight,
    viewport: innerHeight,
    maxScroll: Math.max(0, document.documentElement.scrollHeight - innerHeight),
    readerState: history.state?.bijuxDiagramReaderPosition ?? null,
    nativeEvents: window.bijuxNativeReaderEvents ?? [],
    readerScrollCalls: window.bijuxNativeReaderScrollCalls ?? [],
    rect: node.getBoundingClientRect().toJSON(),
    navigation: performance.getEntriesByType("navigation").map(entry => ({
      type: entry.type, name: entry.name,
    })),
  }));
}

test("native same-window diagram Back and Forward retain the authored reader position", async ({ page }, info) => {
  const origin = info.project.use.baseURL;
  const records = [], clicks = [], documents = [];
  page.on("request", request => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documents.push(request.url());
  });
  await page.exposeFunction("bijuxObserveNativeDeparture", event => clicks.push(event));
  await page.addInitScript(() => {
    window.bijuxNativeReaderEvents = [];
    window.bijuxNativeReaderScrollCalls = [];
    const nativeScrollTo = window.scrollTo;
    window.scrollTo = function (...args) {
      const value = nativeScrollTo.apply(this, args);
      window.bijuxNativeReaderScrollCalls.push({ args, stack: new Error().stack, url: location.href,
        y: scrollY, height: document.documentElement.scrollHeight, viewport: innerHeight,
        maxScroll: Math.max(0, document.documentElement.scrollHeight - innerHeight) });
      return value;
    };
    for (const type of ["pageshow", "pagehide"]) window.addEventListener(type, event => {
      const link = document.querySelector("#reader-native-next");
      window.bijuxNativeReaderEvents.push({ type, persisted: event.persisted, trusted: event.isTrusted,
        url: location.href, timeOrigin: performance.timeOrigin, y: scrollY,
        height: document.documentElement.scrollHeight, viewport: innerHeight,
        maxScroll: Math.max(0, document.documentElement.scrollHeight - innerHeight),
        readerState: history.state?.bijuxDiagramReaderPosition ?? null,
        top: link?.getBoundingClientRect().top ?? null });
    });
    document.addEventListener("click", event => {
      const link = event.target.closest?.("#reader-native-next");
      if (link && event.isTrusted) window.bijuxObserveNativeDeparture({
        trusted: event.isTrusted, url: location.href, href: link.href, y: scrollY,
        rect: link.getBoundingClientRect().toJSON(),
      });
    }, true);
  });
  try {
    const authored = await openReader(page, origin);
    const timeOrigin = await page.evaluate(() => performance.timeOrigin);
    const link = page.locator("#reader-native-next");
    await expect(link).toHaveAttribute("target", "_self");
    const heading = await article(page).locator("h1").boundingBox();
    await page.mouse.move(heading.x + heading.width / 2, heading.y + heading.height / 2);
    await page.mouse.wheel(0, 650);
    await expect.poll(() => page.evaluate(() => scrollY)).toBeGreaterThan(0);
    await link.click();
    await expect(page).toHaveURL(checkpoint(origin));
    expect(await page.evaluate(() => performance.timeOrigin)).not.toBe(timeOrigin);
    expect(documents).toEqual([reader(origin), checkpoint(origin)]);
    const departure = clicks.at(-1);
    expect(departure?.trusted).toBe(true);
    expect(departure.url).toBe(reader(origin));
    records.push({ label: "trusted native departure", departure, documents });
    const firstBack = await page.goBack();
    records.push({ label: "first native Back response", response: firstBack ? { url: firstBack.url(), status: firstBack.status() } : null });
    await expect(page).toHaveURL(departure.url);
    await rendered(page);
    records.push({ label: "native Back geometry before assertion", ...await position(link) });
    await expect(link).toBeInViewport();
    records.push({ label: "native Back exact URL", ...await observeRoute(page, departure.url) });
    expect(await figures(page).locator(".bijux-diagram-source code").allTextContents()).toEqual(authored);
    await page.goForward();
    await expect(article(page).locator("h1")).toHaveText(/^Table boundary reference(?:¶)?$/);
    records.push({ label: "native Forward exact URL", ...await observeRoute(page, checkpoint(origin)) });

    // Opening authored diagram source changes layout independently of reader identity.
    await page.goBack();
    await rendered(page);
    await page.setViewportSize({ width: 320, height: 780 });
    await figures(page).locator(".bijux-diagram-source > summary").first().click();
    await expect(figures(page).locator("details[open]")).toHaveCount(1);
    const disclosedDiagrams = await figures(page).evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().height));
    await link.click();
    await expect(page).toHaveURL(checkpoint(origin));
    const compactDeparture = clicks.at(-1);
    expect(compactDeparture?.trusted).toBe(true);
    records.push({ label: "trusted compact native departure", compactDeparture, disclosedDiagrams });
    const compactBack = await page.goBack();
    records.push({ label: "compact native Back response", response: compactBack ? { url: compactBack.url(), status: compactBack.status() } : null });
    await rendered(page);
    const restoredDiagrams = await figures(page).evaluateAll(nodes => nodes.map(node => node.getBoundingClientRect().height));
    const compactReturned = await position(link);
    records.push({ label: "compact native Back geometry before assertion", compactDeparture, disclosedDiagrams, restoredDiagrams,
      desiredScroll: compactReturned.y + compactReturned.rect.top - compactDeparture.rect.top,
      absoluteOffset: Math.abs(compactReturned.rect.top - compactDeparture.rect.top),
      ...compactReturned });
    expect(restoredDiagrams).not.toEqual(disclosedDiagrams);
    await expect(link).toBeInViewport();
    await expect.poll(() => link.evaluate((node, top) => Math.abs(node.getBoundingClientRect().top - top), compactDeparture.rect.top),
      { message: "Native Back retains the clicked reader offset after actual diagram source layout changes" }).toBeLessThan(1);
    records.push({ label: "diagram source native Back context", compactDeparture, disclosedDiagrams, restoredDiagrams, ...await position(link) });
  } finally {
    await attach(info, records);
  }
});

test("ordinary instant diagram reader history retains its document realm and authored source", async ({ page }, info) => {
  const origin = info.project.use.baseURL;
  const records = [], documents = [];
  page.on("request", request => {
    if (request.isNavigationRequest() && request.frame() === page.mainFrame()) documents.push(request.url());
  });
  try {
    const authored = await openReader(page, origin);
    const realm = await page.evaluate(() => ({ timeOrigin: performance.timeOrigin }));
    const link = page.locator("#reader-instant-next");
    expect(await link.getAttribute("target")).toBeNull();
    await link.click();
    await expect(page).toHaveURL(checkpoint(origin));
    expect(await page.evaluate(() => performance.timeOrigin)).toBe(realm.timeOrigin);
    await page.goBack();
    await rendered(page);
    expect(await page.evaluate(() => performance.timeOrigin)).toBe(realm.timeOrigin);
    expect(documents).toEqual([reader(origin)]);
    expect(await figures(page).locator(".bijux-diagram-source code").allTextContents()).toEqual(authored);
    records.push({ label: "instant Back exact URL", realm, documents, ...await observeRoute(page, reader(origin)) });
    await page.goForward();
    expect(await page.evaluate(() => performance.timeOrigin)).toBe(realm.timeOrigin);
    records.push({ label: "instant Forward exact URL", ...await observeRoute(page, checkpoint(origin)) });
  } finally {
    await attach(info, records);
  }
});

test("trusted wheel during native diagram rebuilding owns the reader position", async ({ page }, info) => {
  const origin = info.project.use.baseURL;
  const records = [], calls = [];
  await page.exposeFunction("bijuxObserveReaderScroll", call => calls.push(call));
  await page.addInitScript(() => {
    const native = window.scrollTo;
    window.scrollTo = function (...args) {
      window.bijuxObserveReaderScroll({ url: location.href, args, stack: new Error().stack });
      return native.apply(this, args);
    };
  });
  try {
    await openReader(page, origin);
    await page.locator("#reader-native-next").click();
    await expect(page).toHaveURL(checkpoint(origin));
    await page.route("**/vendor/mermaid-11.17.2.min.js", async route => {
      await new Promise(resolve => setTimeout(resolve, 900));
      await route.continue();
    });
    await page.goBack({ waitUntil: "domcontentloaded" });
    await expect(page.locator("body")).toHaveAttribute("data-bijux-drawer-ready", "true");
    // Native Back settles its initial scroll in the browser's layout frames.
    // Act after that handoff while the real renderer response remains pending.
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const pending = await figures(page).locator(".bijux-diagram-preview > svg").count();
    expect(pending, "Actual pending renderer when the reader acts").toBeLessThan(5);
    const before = await page.evaluate(() => scrollY);
    records.push({ label: "pending native input geometry", pending, ...await position(page.locator("#reader-native-next")) });
    await page.mouse.move(190, 400);
    await page.mouse.wheel(0, -500);
    await expect.poll(() => page.evaluate(() => scrollY)).toBeLessThan(before);
    await rendered(page);
    records.push({ label: "trusted input exact URL", ...await observeRoute(page, reader(origin)) });
    const owned = calls.filter(call => call.url === reader(origin) && call.stack.includes("mermaid-init.js"));
    records.push({ label: "reader owns deferred restoration", before, pending, after: await page.evaluate(() => scrollY), calls, owned });
    expect(owned, "Owned restoration yields to trusted reader input").toEqual([]);
  } finally {
    await attach(info, records);
  }
});
