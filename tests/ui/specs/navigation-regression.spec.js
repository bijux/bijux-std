const { test, expect } = require("@playwright/test");

const FIXTURE = {
  HUB_HOME: "/tests/ui/fixtures/navigation-hub-home.html",
  HUB_PLATFORM: "/tests/ui/fixtures/navigation-hub-platform.html",
  PROJECT_ROOT: "/tests/ui/fixtures/navigation-project-root.html",
  PROJECT_DEEP: "/tests/ui/fixtures/navigation-project-deep.html",
  PROJECT_EMPTY_SCOPED: "/tests/ui/fixtures/navigation-project-empty-scoped.html",
};

async function openDrawer(page) {
  await page.locator('[data-bijux-header-control="drawer-toggle"]').click();
  await expect(page.locator("#__drawer")).toBeChecked();
}

async function indexInNavOrder(page, selector) {
  return page.evaluate((targetSelector) => {
    const nodes = Array.from(document.querySelectorAll("[data-bijux-mobile-order]"));
    return nodes.findIndex((node) => node.matches(targetSelector));
  }, selector);
}

test.describe("hub mobile navigation", () => {
  test("1) hub phone drawer opens and shows local navigation first", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await openDrawer(page);

    await expect(page.locator('[data-bijux-mobile-order="1-sections"]')).toBeVisible();
    await expect(page.getByRole("link", { name: "Home", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Platform", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Projects", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Learning", exact: true })).toBeVisible();
    await expect(page.locator('[data-bijux-mobile-order="3-sites"]')).toBeVisible();

    const localIndex = await indexInNavOrder(page, '[data-bijux-mobile-order="1-sections"]');
    const sitesIndex = await indexInNavOrder(page, '[data-bijux-mobile-order="3-sites"]');
    expect(localIndex).toBeGreaterThanOrEqual(0);
    expect(sitesIndex).toBeGreaterThan(localIndex);
  });

  test("2) hub phone Home expands to Overview and Reading Paths", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await openDrawer(page);

    const pagesRow = page.locator('[data-bijux-mobile-order="2-pages"]');
    await expect(pagesRow).toContainText("Overview");
    await expect(pagesRow).toContainText("Reading Paths");

    const sectionsRowText = await page.locator('[data-bijux-mobile-order="1-sections"]').innerText();
    expect(sectionsRowText).not.toContain("Reading Paths");
  });

  test("3) hub phone active Platform shows one child level only", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_PLATFORM);
    await openDrawer(page);

    const pagesRow = page.locator('[data-bijux-mobile-order="2-pages"]');
    await expect(pagesRow).toContainText("Bijux Standard Layer");
    await expect(pagesRow).toContainText("Work Qualities");
    await expect(pagesRow).toContainText("System Map");
    await expect(pagesRow).toContainText("Repository Matrix");
    await expect(pagesRow).not.toContainText("Deep Child Example");
  });

  test("4) hub phone cross-site switching to Core works", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await openDrawer(page);

    await page.locator('[data-bijux-mobile-order="3-sites"] .bijux-mobile-hub__link', { hasText: "Core" }).click();
    await expect(page).toHaveURL(/navigation-project-root\.html/);

    await openDrawer(page);
    await expect(page.locator('.bijux-mobile-hub__item--active .bijux-mobile-hub__link', { hasText: "Core" })).toBeVisible();
  });
});
