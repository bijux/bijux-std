const { test, expect, control, phone } = require("./helpers/document");
const { nativeAnswer } = require("./helpers/search");
const query = (page) => page.locator("[data-md-component='search-query']");
async function search(page) {
  await phone(page, "/bijux-core/");
  await control(page, "search").click();
  await expect(query(page)).toBeFocused();
}
async function result(page) {
  await nativeAnswer(page);
}

test("paste-like text insertion produces results and reset clears query", async ({ page }) => {
  await search(page);
  await page.keyboard.insertText("resilient navigation");
  await result(page);
  await page.locator("button[type='reset']").click();
  await expect(query(page)).toHaveValue("");
  await expect(page.locator(".md-search-result__meta")).toBeInViewport();
  await expect(page.locator(".md-search-result__meta")).toContainText("Type to start searching");
  await expect(page.locator(".md-search-result__link:visible")).toHaveCount(0);
  await phone(page, "/fixtures/native-header/");
  const nativeOpener = page.locator(".md-header__button[for='__search']");
  await expect(nativeOpener).toHaveCount(1);
  await expect(nativeOpener).toHaveJSProperty("tagName", "BUTTON");
  await expect(nativeOpener).toHaveAttribute("type", "button");
  await nativeOpener.click();
  await expect(query(page)).toBeFocused();
  await page.keyboard.insertText("resilient navigation");
  await result(page);
  await page.locator("button[type='reset']").click();
  await expect(query(page)).toHaveValue("");
  await expect(page.locator(".md-search-result__meta")).toContainText("Type to start searching");
  await page.keyboard.press("Escape");
  await expect(nativeOpener).toBeFocused();
  await page.keyboard.press("Space");
  await expect(query(page)).toBeFocused();
  await page.keyboard.insertText("resilient navigation");
  const answer = await nativeAnswer(page);
  const destination = await answer.getAttribute("href");
  await answer.click();
  await expect(page).toHaveURL(destination);
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.goBack();
  await expect(page).toHaveURL(/\/fixtures\/native-header\/$/);
  await expect(nativeOpener).toHaveCount(1);
  await nativeOpener.click();
  await expect(query(page)).toBeFocused();
});

test("composition completion yields the final input query", async ({ page }) => {
  await search(page);
  // Browser automation has no native IME session; only composition signals are synthetic.
  await query(page).dispatchEvent("compositionstart", { data: "resilient" });
  await page.keyboard.insertText("resilient navigation");
  await query(page).dispatchEvent("compositionend", { data: "resilient navigation" });
  await result(page);
  await expect(query(page)).toHaveValue("resilient navigation");
});

test("Escape dismisses search and returns keyboard context", async ({ page }) => {
  await search(page);
  await page.keyboard.press("Escape");
  await expect(page.locator("#__search")).not.toBeChecked();
  await expect(control(page, "search")).toBeFocused();
});

test("missing search index preserves query and keyboard Retry reaches native results", async ({ page }) => {
  await page.route("**/search/search_index.json", (route) => route.abort("failed"));
  await search(page);
  await page.keyboard.insertText("resilient navigation");
  await expect(query(page)).toHaveValue("resilient navigation");
  await expect(page.locator("[role='status'], [role='alert']").filter({ hasText: /search.*(unavailable|failed|retry)|unable.*search/i }).first()).toBeVisible({ timeout: 12_000 });
  const retry = page.getByRole("button", { name: "Retry search", exact: true });
  await expect(retry).toBeVisible();
  for (let traversal = 0; traversal < 12 && !(await retry.evaluate(node => node === document.activeElement)); traversal += 1) {
    await page.keyboard.press("Tab");
    await expect(page.locator("[data-md-component='search'] :focus")).toHaveCount(1);
  }
  await expect(retry).toBeFocused();
  await page.unroute("**/search/search_index.json");
  await page.keyboard.press("Enter");
  await result(page);
  await expect(query(page)).toHaveValue("resilient navigation");
  await expect(page.locator(".md-search-result__link").first()).toBeInViewport();
  await page.keyboard.press("Escape");
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.route("**/search/search_index.json", route => route.abort("failed"));
  await phone(page, "/fixtures/native-header/");
  await page.locator(".md-header__button[for='__search']").click();
  await page.keyboard.insertText("resilient navigation");
  const nativeRetry = page.getByRole("button", { name: "Retry search", exact: true });
  await expect(nativeRetry).toBeVisible();
  for (let traversal = 0; traversal < 12 && !(await nativeRetry.evaluate(node => node === document.activeElement)); traversal += 1) await page.keyboard.press("Tab");
  await expect(nativeRetry).toBeFocused();
  await page.unroute("**/search/search_index.json");
  await page.keyboard.press("Enter");
  await result(page);
  await expect(query(page)).toHaveValue("resilient navigation");
});

test("search modal contains native Tab traversal and restores background after ordinary close", async ({ page }) => {
  await search(page);
  const dialog = page.locator("[data-md-component='search']");
  await expect(dialog).toHaveAttribute("role", "dialog");
  await expect(dialog).toHaveAttribute("aria-modal", "true");
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", true);
  await page.keyboard.insertText("resilient navigation");
  await result(page);
  for (const key of [...Array(20).fill("Tab"), ...Array(4).fill("Shift+Tab")]) {
    await page.keyboard.press(key);
    await expect(dialog.locator(":focus")).toHaveCount(1);
  }
  await dialog.getByRole("button", { name: "Close search", exact: true }).click();
  await expect(page.locator("#__search")).not.toBeChecked();
  await expect(page.locator(".md-content")).toHaveJSProperty("inert", false);
  await expect(control(page, "search")).toBeFocused();
});


test("native desktop search restores visible inline input after Escape from a result", async ({ page }, info) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  info.annotations.push({ type: "viewport", description: "1440x900 native inline search" });
  await page.goto("/fixtures/native-header/");
  await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", /desktop|wide/);
  const opener = page.locator(".md-header__button[for='__search']");
  await expect(opener).toBeHidden();
  await query(page).click();
  await page.keyboard.insertText("resilient navigation");
  const answer = await nativeAnswer(page);
  for (let traversal = 0; traversal < 16 && !(await answer.evaluate(node => node === document.activeElement)); traversal += 1) await page.keyboard.press("Tab");
  await expect(answer).toBeFocused();
  // Observe the actual native debounced focus-open attempt; no UI state is injected.
  await page.evaluate(() => {
    window.bijuxSearchFocusEvidence = [];
    const toggle = document.getElementById("__search");
    toggle.addEventListener("click", event => {
      if (!event.isTrusted) window.bijuxSearchFocusEvidence.push({ wasOpening: toggle.checked, cancelled: event.defaultPrevented });
    });
  });
  await page.keyboard.press("Escape");
  await expect.poll(() => page.evaluate(() => window.bijuxSearchFocusEvidence)).toContainEqual({ wasOpening: true, cancelled: true });
  await expect(page.locator("#__search")).not.toBeChecked();
  await expect(query(page)).toBeFocused();
  await expect(query(page)).toBeVisible();
  await query(page).click();
  await expect(page.locator("#__search")).toBeChecked();
  await nativeAnswer(page);
  await page.keyboard.press("Escape");
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.keyboard.press("Tab");
  await expect(query(page)).not.toBeFocused();
  await page.keyboard.press("/");
  await expect(query(page)).toBeFocused();
  await expect(page.locator("#__search")).toBeChecked();
  await page.keyboard.press("Escape");
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.keyboard.press("ControlOrMeta+A");
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#__search")).not.toBeChecked();
  await page.keyboard.press("Space");
  await expect(page.locator("#__search")).toBeChecked();
  await expect(query(page)).toHaveValue("resilient navigation ");
  await page.keyboard.press("Backspace");
  const reopenedAnswer = await nativeAnswer(page);
  const destination = await reopenedAnswer.getAttribute("href");
  await reopenedAnswer.click();
  await expect(page).toHaveURL(destination);
  await expect(page.locator("#__search")).not.toBeChecked();
});
