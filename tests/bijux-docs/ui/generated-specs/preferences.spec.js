const { test, expect, control, phone, openDrawer } = require("./helpers/document");

test("denied browser storage preserves palette, search and drawer behavior", async ({ page }) => {
  await page.addInitScript(() => {
    for (const name of ["getItem", "setItem", "removeItem"]) Object.defineProperty(Storage.prototype, name, { value() { throw new DOMException("Storage denied", "SecurityError"); } });
  });
  await phone(page);
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", /default|slate/);
  await page.locator("[data-bijux-theme-toggle]").click();
  await openDrawer(page);
  await page.keyboard.press("Escape");
  await control(page, "search").click();
  await page.locator("[data-md-component='search-query']").pressSequentially("resilient navigation");
  await expect(page.locator(".md-search-result__link").first()).toBeVisible();
});

test("malformed and incompatible palette data retain a usable default", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("bijux:theme", "{broken");
    localStorage.setItem("/.__palette", JSON.stringify({ index: 999, color: null }));
  });
  await phone(page);
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", /default|slate/);
  await openDrawer(page);
  await page.keyboard.press("Escape");
  await page.locator("[data-bijux-theme-toggle]").click();
  await expect(page.locator("[data-bijux-theme-toggle]")).toHaveAttribute("aria-label", /Theme mode/);
});

test("explicit dark preference applies across initial load and reload", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("bijux:theme", JSON.stringify({ version: 2, mode: "dark" })));
  await phone(page);
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", "slate");
  await page.reload();
  await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", "slate");
});
