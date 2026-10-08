const { test, expect, control, phone } = require("./helpers/document");
const { nativeAnswer } = require("./helpers/search");
const query = page => page.locator("[data-md-component='search-query']");

test("ordinary reading defers the native index until genuine search intent", async ({ page }) => {
  let requests = 0;
  page.on("request", request => { if (request.url().endsWith("/search/search_index.json")) requests += 1; });
  await phone(page, "/bijux-core/");
  await page.waitForTimeout(1200);
  expect(requests).toBe(0);
  expect(await page.evaluate(() => window.bijuxSearchIndex.state.stage)).toBe("index-idle");
  await control(page, "search").click();
  await query(page).pressSequentially("resilient navigation");
  await nativeAnswer(page);
  expect(requests).toBe(1);
  await phone(page, "/bijux-core/platform/details/leaf/?h=resilient+navigation");
  await expect(page.locator("main mark[data-md-highlight]").first()).toBeVisible();
  expect(requests, "A cold shared result link admits the index needed by native highlighting").toBe(2);
});

test("keyboard Cancel preserves the query and keyboard Retry returns the native answer", async ({ page }) => {
  let failedRequestFinished;
  const finished = new Promise(resolve => { failedRequestFinished = resolve; });
  // Controlled incomplete transport exercises controls, not a bandwidth or device claim.
  await page.route("**/search/search_index.json", async route => {
    await new Promise(resolve => setTimeout(resolve, 2000));
    await route.abort("failed");
    failedRequestFinished();
  });
  await phone(page, "/bijux-core/");
  await control(page, "search").click();
  await query(page).pressSequentially("resilient navigation");
  const cancel = page.getByRole("button", { name: "Cancel download", exact: true });
  await expect(cancel).toBeVisible();
  for (let traversal = 0; traversal < 12 && !(await cancel.evaluate(node => node === document.activeElement)); traversal += 1) await page.keyboard.press("Tab");
  await expect(cancel).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator(".bijux-search-recovery [role='status']")).toContainText("canceled");
  const retry = page.getByRole("button", { name: "Retry search", exact: true });
  await expect(retry).toBeFocused();
  await expect(query(page)).toHaveValue("resilient navigation");
  await finished;
  await page.unroute("**/search/search_index.json");
  await page.keyboard.press("Enter");
  await nativeAnswer(page);
  await expect(query(page)).toHaveValue("resilient navigation");
  await expect(query(page)).toBeFocused();
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.insertText("resilient");
  await expect(query(page)).toHaveValue("resilient");
  await nativeAnswer(page, "resilient");
});
