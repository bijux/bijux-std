const { test, expect, control, phone } = require("./helpers/document");
const { nativeAnswer } = require("./helpers/search");
const query = page => page.locator("[data-md-component='search-query']");
const workerURL = "**/assets/javascripts/workers/search*.js";
async function openSearch(page) {
  await phone(page, "/bijux-core/");
  await control(page, "search").click();
  await query(page).pressSequentially("resilient navigation");
}
async function recover(page) {
  await expect(query(page)).toHaveValue("resilient navigation");
  await expect(page.locator("[role='status'], [role='alert']").filter({ hasText: /search.*(unavailable|failed|retry)|unable.*search/i }).first()).toBeVisible({ timeout: 12_000 });
  await expect(page.locator(".md-search-result__link:visible")).toHaveCount(0);
  const retry = page.getByRole("button", { name: "Retry search", exact: true });
  await expect(retry).toBeVisible();
  for (let traversal = 0; traversal < 12 && !(await retry.evaluate(node => node === document.activeElement)); traversal += 1) await page.keyboard.press("Tab");
  await expect(retry).toBeFocused();
  await page.unroute(workerURL);
  await page.keyboard.press("Enter");
  await nativeAnswer(page);
  await expect(query(page)).toHaveValue("resilient navigation");
  await (await nativeAnswer(page)).click();
  await expect(page).toHaveURL(/\/bijux-core\//);
  await expect(page.locator("main")).toContainText("resilient navigation");
}

test("missing native worker exposes useful recovery and keyboard Retry returns real results", async ({ page }) => {
  await page.route(workerURL, route => route.fulfill({ status: 404, contentType: "text/plain", body: "Search worker unavailable" }));
  await openSearch(page);
  await recover(page);
});
test("native worker initialization exception remains contained and ordinary Retry restores search", async ({ page }) => {
  await page.route(workerURL, route => route.fulfill({ status: 200, contentType: "application/javascript", body: "throw new Error('Controlled search-worker initialization failure');" }));
  await openSearch(page);
  await recover(page);
});
test("unresponsive worker setup reaches a bounded failure and genuine retry restores native results", async ({ page }) => {
  await page.route(workerURL, route => route.fulfill({ status: 200, contentType: "application/javascript", body: "self.addEventListener('message', function () {});" }));
  await openSearch(page);
  await recover(page);
});

test("simultaneous missing index and worker recover through one ordinary Retry activation", async ({ page }) => {
  let indexRequests = 0;
  page.on("request", request => { if (request.url().endsWith("/search/search_index.json")) indexRequests += 1; });
  await page.route("**/search/search_index.json", route => route.fulfill({ status: 404, contentType: "application/json", body: "{}" }));
  await page.route(workerURL, route => route.fulfill({ status: 404, contentType: "text/plain", body: "Search worker unavailable" }));
  await openSearch(page);
  await expect.poll(() => page.evaluate(() => window.bijuxSearchWorker?.state.stage)).toBe("worker-unavailable");
  await expect.poll(() => page.evaluate(() => window.bijuxSearchIndex?.state.stage)).toBe("index-unavailable");
  await page.unroute("**/search/search_index.json");
  await recover(page);
  expect(indexRequests, "One failed corpus request and one genuine recovery request").toBe(2);
});
test("ten ordinary instant journeys retain one actual search worker and one corpus request", async ({ page }) => {
  let workerInstances = 0, indexRequests = 0;
  page.on("worker", () => { workerInstances += 1; });
  page.on("request", request => { if (request.url().endsWith("/search/search_index.json")) indexRequests += 1; });
  await phone(page, "/bijux-core/platform/");
  for (let journey = 0; journey < 10; journey += 1) {
    await page.locator("main").getByRole("link", { name: "Getting started", exact: true }).click();
    await expect(page).toHaveURL(/\/bijux-core\/platform\/start\/$/);
    await page.goBack();
    await expect(page).toHaveURL(/\/bijux-core\/platform\/$/);
  }
  await control(page, "search").click();
  await query(page).pressSequentially("resilient navigation");
  await nativeAnswer(page);
  expect(workerInstances).toBe(1);
  expect(indexRequests).toBe(1);
});

test("failure after native readiness retries the preserved query without fetching the healthy corpus again", async ({ page }) => {
  let indexRequests = 0;
  page.on("request", request => { if (request.url().endsWith("/search/search_index.json")) indexRequests += 1; });
  await page.route(workerURL, async route => {
    const response = await route.fetch();
    const native = await response.text();
    await route.fulfill({ response, body: native + "\nself.addEventListener('message', function (event) { if (event.data.type === 2 && event.data.data === 'stop worker') throw new Error('Controlled running search-worker failure'); });" });
  });
  await openSearch(page);
  await nativeAnswer(page);
  await query(page).fill("stop worker");
  await expect.poll(() => page.evaluate(() => window.bijuxSearchWorker?.state.stage)).toBe("worker-unavailable");
  await query(page).fill("resilient navigation");
  await recover(page);
  expect(indexRequests, "Replacing a failed native worker reuses the admitted healthy corpus").toBe(1);
});
