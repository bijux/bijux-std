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

async function linkTexts(locator) {
  return locator.evaluateAll((nodes) => nodes.map((node) => node.textContent.trim()).filter(Boolean));
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

test.describe("project mobile navigation", () => {
  test("5) project root phone drawer opens on bijux-core", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_ROOT);
    await openDrawer(page);

    await expect(page.locator(".md-sidebar--primary")).toBeVisible();
    await expect(page.locator('[data-bijux-mobile-order=\"1-top-directories\"]')).toBeVisible();
    await expect(page.locator('[data-bijux-mobile-order=\"1-top-directories\"] .md-nav__item')).toHaveCount(2);
  });

  test("6) project phone drawer shows local top-level directories before Sites", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_ROOT);
    await openDrawer(page);

    const localIndex = await indexInNavOrder(page, '[data-bijux-mobile-order=\"1-top-directories\"]');
    const sitesIndex = await indexInNavOrder(page, '[data-bijux-mobile-order=\"5-sites\"]');
    expect(localIndex).toBeGreaterThanOrEqual(0);
    expect(sitesIndex).toBeGreaterThan(localIndex);
  });

  test("7) project phone row progression works: row2 -> row3 -> row4 -> files", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_DEEP);
    await openDrawer(page);

    await expect(page.locator('[data-bijux-mobile-order=\"1-top-directories\"]')).toContainText("Directories");
    await expect(page.locator('[data-bijux-mobile-order=\"2-subdirectories\"]')).toContainText("Subdirectories");
    await expect(page.locator('[data-bijux-mobile-order=\"3-third-level-directories\"]')).toContainText("Nested Directories");
    await expect(page.locator('[data-bijux-mobile-order=\"4-pages\"]')).toContainText("Contracts");
    await expect(page.locator('[data-bijux-mobile-order=\"4-pages\"]')).toContainText("Checks");
  });

  test("8) empty-scoped project root does not hide drawer", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.PROJECT_EMPTY_SCOPED);
    await openDrawer(page);

    const sidebarWidth = await page.locator(".md-sidebar--primary").evaluate((el) => el.getBoundingClientRect().width);
    expect(sidebarWidth).toBeGreaterThan(0);
    await expect(page.locator(".md-sidebar--primary")).toBeVisible();
    await expect(page.locator('[data-bijux-mobile-order=\"1-top-directories\"]')).toBeVisible();
    await expect(page.locator('.bijux-nav--scoped[data-bijux-nav-empty=\"true\"]')).toBeHidden();
  });

  test("11) hub phone sites block exposes the seven canonical site entries", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await openDrawer(page);

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

  test("12) cross-site transition keeps project phone drawer usable", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await openDrawer(page);
    await page.locator('[data-bijux-mobile-order="3-sites"] .bijux-mobile-hub__link', { hasText: "Core" }).click();

    await expect(page).toHaveURL(/navigation-project-root\.html/);
    await openDrawer(page);

    await expect(page.locator('[data-bijux-mobile-order="1-top-directories"]')).toBeVisible();
    await expect(page.locator('[data-bijux-mobile-order="1-top-directories"] .md-nav__item')).toHaveCount(2);
    await expect(page.locator('.bijux-mobile-hub__item--active .bijux-mobile-hub__link', { hasText: "Core" })).toBeVisible();
  });

  test("13) phone drawer navigation has no duplicate wrapper junk entries", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await page.goto(FIXTURE.HUB_HOME);
    await openDrawer(page);
    const hubSectionTexts = await linkTexts(page.locator('[data-bijux-mobile-order="1-sections"] .md-nav__link'));
    expect(new Set(hubSectionTexts).size).toBe(hubSectionTexts.length);
    expect(hubSectionTexts).not.toContain("SECTION");

    await page.goto(FIXTURE.PROJECT_ROOT);
    await openDrawer(page);
    const projectRowTexts = await linkTexts(page.locator('[data-bijux-mobile-order="1-top-directories"] .md-nav__link'));
    expect(new Set(projectRowTexts).size).toBe(projectRowTexts.length);
    expect(projectRowTexts).not.toContain("Home");
  });
});

test.describe("responsive navigation regressions", () => {
  test("9) tablet keeps compact top navigation and does not fall into phone mode", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "normal", "normal/tablet-only assertions");

    await page.goto(FIXTURE.HUB_HOME);

    await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "normal");
    await expect(page.locator(".bijux-hub-strip")).toBeVisible();
    await expect(page.locator(".bijux-site-tabs")).toBeVisible();
    await expect(page.locator(".bijux-detail-tabs")).toBeVisible();
    await expect(page.locator(".bijux-nav--mobile")).toBeHidden();
  });

  test("10) desktop keeps full shell and top-row navigation still works", async ({ page }, testInfo) => {
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
