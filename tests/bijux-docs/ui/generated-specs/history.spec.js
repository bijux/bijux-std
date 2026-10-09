const { test, expect } = require("@playwright/test");
const { observeRoute } = require("./history/observations");

async function stable(page, expectedURL, records, label) {
  await expect(page).toHaveURL(expectedURL);
  try {
    records.push({ label, ...await observeRoute(page, expectedURL) });
  } catch (error) {
    records.push({ label, expectedURL, failure: error.message, observations: error.observations || [] });
    throw error;
  }
}
async function fragment(page) {
  await page.locator("#boundary-example > a.headerlink").click();
  await expect(page.locator("#boundary-example")).toBeVisible();
}
async function nextReader(page, expectedURL) {
  const next = page.locator(".md-footer__link--next");
  expect(await next.evaluate(node => node.href)).toBe(expectedURL);
  await next.click();
  await expect(page).toHaveURL(expectedURL);
  await expect(page.locator("h1")).toHaveText(/^Table boundary reference(?:¶)?$/);
}
async function evidence(info, records) {
  await info.attach("reader-history-observations", {
    body: Buffer.from(JSON.stringify(records, null, 2)),
    contentType: "application/json",
  });
}
async function navigationReaderHistory(page, info, records) {
  const root = info.project.use.baseURL + "/";
  await page.goto(root);
  await expect(page.locator("body")).toHaveAttribute("data-bijux-drawer-ready", "true");
  const opener = page.locator('[data-bijux-header-control="drawer-toggle"]');
  const compact = await page.evaluate(() => window.matchMedia("(max-width: 76.2344em)").matches);
  if (compact) await opener.click();
  else {
    await expect(opener).toBeHidden();
    await expect(page.locator(".md-sidebar--primary")).toBeVisible();
  }
  const platform = page.locator("#bijux-navigation summary").filter({ hasText: /^Platform$/ });
  await platform.click();
  const details = platform.locator("..").locator("summary").filter({ hasText: /^Details$/ });
  await details.click();
  const leaf = details.locator("..").locator("a").filter({ hasText: /^\s*Leaf destination\s*$/ });
  const destination = await leaf.evaluate(node => node.href);
  await leaf.click();
  await stable(page, destination, records, "authored nested leaf navigation");
  const heading = page.locator(".md-content h1");
  async function focusedReader(label, name) {
    await expect(heading).toHaveText(name);
    const observation = await heading.evaluate(node => ({
      name: node.textContent, connected: node.isConnected,
      focused: document.activeElement === node, activeTag: document.activeElement.tagName,
    }));
    records.push({ label, ...observation });
    expect(observation.connected).toBe(true);
    await expect(heading).toBeFocused();
  }
  await focusedReader("nested leaf reader focus", /^Platform leaf destination(?:¶)?$/);
  await page.goBack();
  await stable(page, root, records, "nested leaf Back");
  await focusedReader("Back replaces the disconnected reader focus", /^Bijux reference(?:¶)?$/);
  await page.goForward();
  await stable(page, destination, records, "nested leaf Forward");
  await focusedReader("Forward replaces the disconnected reader focus", /^Platform leaf destination(?:¶)?$/);
  await page.reload();
  await expect(page).toHaveURL(destination);
  const active = page.locator('#bijux-navigation a[aria-current="page"]');
  await expect(active).toHaveCount(1);
  expect(await active.evaluate(node => node.href)).toBe(destination);
  const ancestors = await active.evaluate(node => {
    const items = [];
    for (let parent = node.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === "DETAILS") items.push({
        name: parent.querySelector("summary").textContent.trim(), open: parent.open,
      });
    }
    return items;
  });
  records.push({ label: "nested leaf direct reload active ancestors", destination, ancestors });
  expect(ancestors).toEqual([{ name: "Details", open: true }, { name: "Platform", open: true }]);
}
test.beforeEach(async ({ browser, page }, info) => {
  info.annotations.push({ type: "browser-version", description: browser.version() });
  page.on("pageerror", error => { throw error; });
});

test("fragment Back stays stable through the next ordinary reader journey", async ({ page }, info) => {
  const records = [], origin = info.project.use.baseURL;
  const reader = origin + "/reader-code/", destination = origin + "/reader-table/";
  try {
    await navigationReaderHistory(page, info, records);
    await page.goto(reader);
    await expect(page.locator("body")).toHaveAttribute("data-bijux-drawer-ready", "true");
    const identity = await page.evaluate(() => window.bijuxDocumentIdentity = crypto.randomUUID());
    await fragment(page);
    await expect(page).toHaveURL(reader + "#boundary-example");
    await page.goBack();
    await stable(page, reader, records, "fragment Back before pointer settling");
    await nextReader(page, destination);
    expect(await page.evaluate(() => window.bijuxDocumentIdentity)).toBe(identity);
    await page.goBack();
    await stable(page, reader, records, "reader Back preserves cleared fragment");
    await expect(page.locator("h1")).toHaveText(/^Code boundary reference(?:¶)?$/);
    await page.goForward();
    await stable(page, destination, records, "reader Forward");
  } finally { await evidence(info, records); }
});

test("direct product fragment survives ordinary reader Back and Forward", async ({ page }, info) => {
  const records = [], origin = info.project.use.baseURL;
  const reader = origin + "/bijux-core/reader-code/#boundary-example";
  const destination = origin + "/bijux-core/reader-table/";
  try {
    await page.goto(reader);
    await expect(page.locator("body")).toHaveAttribute("data-bijux-drawer-ready", "true");
    await stable(page, reader, records, "direct authored product fragment");
    const identity = await page.evaluate(() => window.bijuxDocumentIdentity = crypto.randomUUID());
    await nextReader(page, destination);
    expect(await page.evaluate(() => window.bijuxDocumentIdentity)).toBe(identity);
    await page.goBack();
    await stable(page, reader, records, "direct fragment reader Back");
    await expect(page.locator("#boundary-example")).toBeVisible();
    await page.goForward();
    await stable(page, destination, records, "direct fragment reader Forward");
  } finally { await evidence(info, records); }
});

test("no-script fragment and reader history preserve ordinary destinations", async ({ browser }, info) => {
  const records = [], origin = info.project.use.baseURL;
  const reader = origin + "/reader-code/", destination = origin + "/reader-table/";
  const context = await browser.newContext({ javaScriptEnabled: false, viewport: info.project.use.viewport });
  const page = await context.newPage();
  try {
    await page.goto(reader);
    await fragment(page);
    await expect(page).toHaveURL(reader + "#boundary-example");
    await page.goBack();
    await stable(page, reader, records, "no-script fragment Back");
    await page.goForward();
    await stable(page, reader + "#boundary-example", records, "no-script fragment Forward");
    await nextReader(page, destination);
    await page.goBack();
    await stable(page, reader + "#boundary-example", records, "no-script reader Back");
  } finally { await evidence(info, records); await context.close(); }
});
