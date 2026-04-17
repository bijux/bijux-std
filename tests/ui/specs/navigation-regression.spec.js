const { test, expect } = require("@playwright/test");
const {
  ensureDrawerOpen,
  expectOrderedRows,
  extractLinkTexts,
  expectUniqueLinkTexts,
} = require("./helpers/navigation");

const FIXTURE = {
  HUB_HOME: "/tests/ui/fixtures/navigation-hub-home.html",
  HUB_PLATFORM: "/tests/ui/fixtures/navigation-hub-platform.html",
  PROJECT_ROOT: "/tests/ui/fixtures/navigation-project-root.html",
  PROJECT_DEEP: "/tests/ui/fixtures/navigation-project-deep.html",
  PROJECT_EMPTY_SCOPED: "/tests/ui/fixtures/navigation-project-empty-scoped.html",
};

test.describe("hub mobile navigation", () => {
  test("hub drawer shows local sections before site switcher", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);

    await expect(page.locator('[data-bijux-mobile-order="1-sections"]')).toBeVisible();
    await expect(page.getByRole("link", { name: "Home", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Platform", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Projects", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Learning", exact: true })).toBeVisible();
    await expect(page.locator('[data-bijux-mobile-order="3-sites"]')).toBeVisible();

    await expectOrderedRows(page, '[data-bijux-mobile-order="1-sections"]', '[data-bijux-mobile-order="3-sites"]');
  });

  test("hub Home exposes overview and reading paths as page children", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);

    const pagesRow = page.locator('[data-bijux-mobile-order="2-pages"]');
    await expect(pagesRow).toContainText("Overview");
    await expect(pagesRow).toContainText("Reading Paths");

    const sectionsRowText = await page.locator('[data-bijux-mobile-order="1-sections"]').innerText();
    expect(sectionsRowText).not.toContain("Reading Paths");
  });

  test("hub Platform shows one-level child pages without deep recursion", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_PLATFORM);
    await ensureDrawerOpen(page);

    const pagesRow = page.locator('[data-bijux-mobile-order="2-pages"]');
    await expect(pagesRow).toContainText("Bijux Standard Layer");
    await expect(pagesRow).toContainText("Work Qualities");
    await expect(pagesRow).toContainText("System Map");
    await expect(pagesRow).toContainText("Repository Matrix");
    await expect(pagesRow).not.toContainText("Deep Child Example");
  });

  test("hub sites list includes all canonical entries in expected order", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);

    const siteLinks = page.locator('[data-bijux-mobile-order="3-sites"] .bijux-mobile-hub__link');
    await expect(siteLinks).toHaveCount(7);
    await expect(siteLinks).toHaveText([
      "Bijux",
      "Core",
      "Canon",
      "Atlas",
      "Proteomics",
      "Pollenomics",
      "Masterclass",
    ]);
  });

  test("hub cross-site transition to Core keeps drawer usable", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);

    await page.locator('[data-bijux-mobile-order="3-sites"] .bijux-mobile-hub__link', { hasText: "Core" }).click();
    await expect(page).toHaveURL(/navigation-project-root\.html/);

    await ensureDrawerOpen(page);
    await expect(page.locator('[data-bijux-mobile-order="1-top-directories"]')).toBeVisible();
    await expect(page.locator('.bijux-mobile-hub__item--active .bijux-mobile-hub__link', { hasText: "Core" })).toBeVisible();
  });
});

test.describe("project mobile navigation", () => {
  test("project root drawer exposes top-level directory row", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_ROOT);
    await ensureDrawerOpen(page);

    await expect(page.locator(".md-sidebar--primary")).toBeVisible();
    await expect(page.locator('[data-bijux-mobile-order="1-top-directories"]')).toBeVisible();
    await expect(page.locator('[data-bijux-mobile-order="1-top-directories"] .md-nav__item')).toHaveCount(2);
  });

  test("project top directories render before sites list", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_ROOT);
    await ensureDrawerOpen(page);

    await expectOrderedRows(page, '[data-bijux-mobile-order="1-top-directories"]', '[data-bijux-mobile-order="5-sites"]');
  });

  test("project deep page follows row progression from directories to pages", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_DEEP);
    await ensureDrawerOpen(page);

    await expect(page.locator('[data-bijux-mobile-order="1-top-directories"]')).toContainText("Directories");
    await expect(page.locator('[data-bijux-mobile-order="2-subdirectories"]')).toContainText("Subdirectories");
    await expect(page.locator('[data-bijux-mobile-order="3-third-level-directories"]')).toContainText("Nested Directories");
    await expect(page.locator('[data-bijux-mobile-order="4-pages"]')).toContainText("Contracts");
    await expect(page.locator('[data-bijux-mobile-order="4-pages"]')).toContainText("Checks");
  });

  test("empty scoped desktop tree does not collapse phone drawer", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_EMPTY_SCOPED);
    await ensureDrawerOpen(page);

    const sidebarWidth = await page.locator(".md-sidebar--primary").evaluate((el) => el.getBoundingClientRect().width);
    expect(sidebarWidth).toBeGreaterThan(0);
    await expect(page.locator(".md-sidebar--primary")).toBeVisible();
    await expect(page.locator('[data-bijux-mobile-order="1-top-directories"]')).toBeVisible();
    await expect(page.locator('.bijux-nav--scoped[data-bijux-nav-empty="true"]')).toBeHidden();
  });

  test("phone drawer rows avoid duplicate wrapper entries", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await ensureDrawerOpen(page);
    const hubSectionLinks = page.locator('[data-bijux-mobile-order="1-sections"] .md-nav__link');
    await expectUniqueLinkTexts(hubSectionLinks);

    const hubSectionTexts = await extractLinkTexts(hubSectionLinks);
    expect(hubSectionTexts).not.toContain("SECTION");

    await page.goto(FIXTURE.PROJECT_ROOT);
    await ensureDrawerOpen(page);
    const projectRowLinks = page.locator('[data-bijux-mobile-order="1-top-directories"] .md-nav__link');
    await expectUniqueLinkTexts(projectRowLinks);

    const projectRowTexts = await extractLinkTexts(projectRowLinks);
    expect(projectRowTexts).not.toContain("Home");
  });
});

test.describe("responsive navigation regressions", () => {
  test("tablet keeps compact top navigation and avoids phone mode", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "normal", "normal/tablet-only assertions");

    await page.goto(FIXTURE.HUB_HOME);

    await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "normal");
    await expect(page.locator(".bijux-hub-strip")).toBeVisible();
    await expect(page.locator(".bijux-site-tabs")).toBeVisible();
    await expect(page.locator(".bijux-detail-tabs")).toBeVisible();
    await expect(page.locator(".bijux-nav--mobile")).toBeHidden();
  });

  test("desktop keeps shell rows and top-level navigation remains active", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "wide", "wide-only assertions");

    await page.goto(FIXTURE.HUB_HOME);

    await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "wide");
    await expect(page.locator(".bijux-hub-strip")).toBeVisible();
    await expect(page.locator(".bijux-site-tabs")).toBeVisible();
    await expect(page.locator(".bijux-detail-tabs")).toBeVisible();
    await expect(page.locator(".bijux-nav--mobile")).toBeHidden();

    await page.getByRole("link", { name: "Platform", exact: true }).click();
    await expect(page).toHaveURL(/navigation-hub-platform\.html/);
  });
});
