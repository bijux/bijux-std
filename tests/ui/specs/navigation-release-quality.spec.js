const { test, expect } = require("@playwright/test");
const { ensureDrawerOpen, ensureDrawerClosed, extractLinkTexts, navOrderIndex } = require("./helpers/navigation");

const FIXTURE = {
  HUB_HOME: "/tests/ui/fixtures/navigation-hub-home.html",
  HUB_PLATFORM: "/tests/ui/fixtures/navigation-hub-platform.html",
  PROJECT_ROOT: "/tests/ui/fixtures/navigation-project-root.html",
  PROJECT_DEEP: "/tests/ui/fixtures/navigation-project-deep.html",
  PROJECT_EMPTY_SCOPED: "/tests/ui/fixtures/navigation-project-empty-scoped.html",
};

function unique(values) {
  return new Set(values).size === values.length;
}

test.describe("phone release-quality navigation", () => {
  test("drawer toggle closes and reopens without losing local sections", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);
    await expect(page.locator('[data-bijux-mobile-order="1-sections"]')).toBeVisible();

    await ensureDrawerClosed(page);
    await expect(page.locator("#__drawer")).not.toBeChecked();

    await ensureDrawerOpen(page);
    await expect(page.locator('[data-bijux-mobile-order="1-sections"]')).toBeVisible();
    await expect(page.getByRole("link", { name: "Home", exact: true })).toBeVisible();
  });

  test("hub sections row has one active entry and it is Home", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);

    const activeEntries = page.locator('[data-bijux-mobile-order="1-sections"] [aria-current="page"]');
    await expect(activeEntries).toHaveCount(1);
    await expect(activeEntries.first()).toHaveText("Home");
  });

  test("hub pages row link labels are unique and each link has usable href", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);

    const pageLinks = page.locator('[data-bijux-mobile-order="2-pages"] .md-nav__link');
    const labels = await extractLinkTexts(pageLinks);
    expect(labels.length).toBeGreaterThanOrEqual(2);
    expect(unique(labels)).toBeTruthy();

    const hrefs = await pageLinks.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href") || ""));
    expect(hrefs.every((href) => href.trim().length > 0)).toBeTruthy();
  });

  test("hub sites block link labels and href targets are unique", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);

    const siteLinks = page.locator('[data-bijux-mobile-order="3-sites"] .bijux-mobile-hub__link');
    const labels = await extractLinkTexts(siteLinks);
    expect(labels).toEqual(["Bijux", "Core", "Canon", "Atlas", "Proteomics", "Pollenomics", "Masterclass"]);
    expect(unique(labels)).toBeTruthy();

    const hrefs = await siteLinks.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href") || ""));
    expect(unique(hrefs)).toBeTruthy();
    expect(hrefs.every((href) => href.startsWith("/tests/ui/fixtures/navigation-"))).toBeTruthy();
  });

  test("hub to Canon transition marks Canon as active site and keeps project local tree", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);

    await page.locator('[data-bijux-mobile-order="3-sites"] .bijux-mobile-hub__link', { hasText: "Canon" }).click();
    await expect(page).toHaveURL(/navigation-project-root\.html\?site=canon/);

    await ensureDrawerOpen(page);
    await expect(page.locator('[data-bijux-mobile-order="1-top-directories"]')).toBeVisible();
    await expect(page.locator('.bijux-mobile-hub__item--active .bijux-mobile-hub__link')).toHaveText("Canon");
  });

  test("project root local row exposes non-empty navigable entries", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_ROOT);
    await ensureDrawerOpen(page);

    const localLinks = page.locator('[data-bijux-mobile-order="1-top-directories"] .md-nav__link');
    await expect(localLinks).toHaveCount(2);

    const labels = await extractLinkTexts(localLinks);
    expect(labels).toEqual(["Systems", "Data"]);

    const hrefs = await localLinks.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href") || ""));
    expect(hrefs.every((href) => href.trim().length > 0)).toBeTruthy();
  });

  test("project deep row ordering remains strict from 1 to 5", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_DEEP);
    await ensureDrawerOpen(page);

    const row1 = await navOrderIndex(page, '[data-bijux-mobile-order="1-top-directories"]');
    const row2 = await navOrderIndex(page, '[data-bijux-mobile-order="2-subdirectories"]');
    const row3 = await navOrderIndex(page, '[data-bijux-mobile-order="3-third-level-directories"]');
    const row4 = await navOrderIndex(page, '[data-bijux-mobile-order="4-pages"]');
    const row5 = await navOrderIndex(page, '[data-bijux-mobile-order="5-sites"]');

    expect(row1).toBeGreaterThanOrEqual(0);
    expect(row2).toBeGreaterThan(row1);
    expect(row3).toBeGreaterThan(row2);
    expect(row4).toBeGreaterThan(row3);
    expect(row5).toBeGreaterThan(row4);
  });

  test("project deep pages row contains leaf pages and excludes directory labels", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_DEEP);
    await ensureDrawerOpen(page);

    const pagesRow = page.locator('[data-bijux-mobile-order="4-pages"]');
    await expect(pagesRow).toContainText("Contracts");
    await expect(pagesRow).toContainText("Checks");
    await expect(pagesRow).not.toContainText("Directories");
    await expect(pagesRow).not.toContainText("Subdirectories");
  });

  test("empty-scoped project keeps mobile tree visible while scoped nav stays hidden", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_EMPTY_SCOPED);
    await ensureDrawerOpen(page);

    await expect(page.locator('.bijux-nav--scoped[data-bijux-nav-empty="true"]')).toBeHidden();
    await expect(page.locator('[data-bijux-mobile-order="1-top-directories"]')).toBeVisible();
    await expect(page.getByRole("link", { name: "Bootstrap", exact: true })).toBeVisible();
  });

  test("project drawer toggle remains functional after cross-site navigation", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);
    await page.locator('[data-bijux-mobile-order="3-sites"] .bijux-mobile-hub__link', { hasText: "Masterclass" }).click();

    await expect(page).toHaveURL(/navigation-project-root\.html\?site=masterclass/);

    await ensureDrawerOpen(page);
    await expect(page.locator('[data-bijux-mobile-order="1-top-directories"]')).toBeVisible();

    await ensureDrawerClosed(page);
    await ensureDrawerOpen(page);
    await expect(page.locator('.bijux-mobile-hub__item--active .bijux-mobile-hub__link')).toHaveText("Masterclass");
  });
});
