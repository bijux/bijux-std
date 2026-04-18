const { test, expect } = require("@playwright/test");
const {
  liveE2EEnabled,
  liveHubUrl,
  gotoLivePage,
  openLiveDrawer,
  sitesBlock,
  collectSiteMap,
  expectCanonicalSiteEntries,
  expectLocalBeforeSites,
} = require("./helpers/live-navigation");

test.describe("live navigation release gate", () => {
  test.skip(!liveE2EEnabled(), "set BIJUX_LIVE_E2E=1 to run live-site navigation checks");
  test.describe.configure({ mode: "serial" });
  test.setTimeout(45_000);

  test("hub phone drawer renders local sections before sites", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await gotoLivePage(page, liveHubUrl());
    await openLiveDrawer(page);

    const sections = page.locator(
      '[data-bijux-mobile-order="1-sections"], [data-bijux-mobile-order="1-tree"], section[aria-label="Hub sections"]',
    );
    await expect(sections).toBeVisible();
    await expect(sections).toContainText("Home");
    await expect(sections).toContainText("Platform");
    await expect(sections).toContainText("Projects");
    await expect(sections).toContainText("Learning");

    await expectLocalBeforeSites(
      page,
      '[data-bijux-mobile-order="1-sections"], [data-bijux-mobile-order="1-tree"], section[aria-label="Hub sections"]',
    );
  });

  test("hub phone Home exposes overview pages without top-level leakage", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await gotoLivePage(page, liveHubUrl());
    await openLiveDrawer(page);

    const pages = page.locator('[data-bijux-mobile-order="2-pages"]');
    await expect(pages).toBeVisible();
    await expect(pages).toContainText("Overview");
    await expect(pages).toContainText("Reading Paths");

    const sectionsText = await page
      .locator('[data-bijux-mobile-order="1-sections"], [data-bijux-mobile-order="1-tree"], section[aria-label="Hub sections"]')
      .innerText();
    expect(sectionsText).not.toContain("Reading Paths");
  });

  test("hub phone Platform branch keeps one-level child model", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    const platformUrl = new URL("/platform/system-map/", liveHubUrl()).toString();
    await gotoLivePage(page, platformUrl);
    await openLiveDrawer(page);

    const sections = page.locator(
      '[data-bijux-mobile-order="1-sections"], [data-bijux-mobile-order="1-tree"], section[aria-label="Hub sections"]',
    );
    await expect(sections.getByRole("link", { name: "Platform", exact: true })).toBeVisible();
    await expect(sections.locator('[aria-current="page"]')).toContainText("Platform");

    const pages = page.locator('[data-bijux-mobile-order="2-pages"]');
    await expect(pages).toContainText("Overview");
    await expect(pages).toContainText("System Map");
    await expect(pages).toContainText("Repository Matrix");
  });

  test("hub phone sites block exposes canonical entries with usable links", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await gotoLivePage(page, liveHubUrl());
    await openLiveDrawer(page);

    await expectCanonicalSiteEntries(page);
  });

  test("hub to Core cross-site transition preserves drawer usability", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await gotoLivePage(page, liveHubUrl());
    await openLiveDrawer(page);

    const siteMap = await collectSiteMap(page);
    const coreUrl = siteMap.get("Core");
    expect(coreUrl).toBeTruthy();

    await page.locator('.bijux-mobile-hub__link', { hasText: "Core" }).first().click();
    await expect(page).toHaveURL(new RegExp(coreUrl.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));

    await openLiveDrawer(page);
    await expect(
      page.locator('[data-bijux-mobile-order="1-top-directories"], [data-bijux-mobile-order="2-tree"]'),
    ).toBeVisible();
    await expect(sitesBlock(page).locator('.bijux-mobile-hub__link[aria-current="page"]')).toContainText("Core");
  });

  test("project root phone drawer keeps local tree before global sites", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await gotoLivePage(page, liveHubUrl());
    const siteMap = await collectSiteMap(page);
    const coreUrl = siteMap.get("Core");
    expect(coreUrl).toBeTruthy();

    await gotoLivePage(page, coreUrl);
    await openLiveDrawer(page);

    const rowOne = page.locator('[data-bijux-mobile-order="1-top-directories"], [data-bijux-mobile-order="2-tree"]');
    await expect(rowOne).toBeVisible();
    await expect(rowOne.locator('.md-nav__link').first()).toBeVisible();
    await expectLocalBeforeSites(
      page,
      '[data-bijux-mobile-order="1-top-directories"], [data-bijux-mobile-order="2-tree"]',
    );
  });

  test("project phone row model progresses into deeper rows on at least one branch", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await gotoLivePage(page, liveHubUrl());
    const siteMap = await collectSiteMap(page);
    const coreUrl = siteMap.get("Core");
    expect(coreUrl).toBeTruthy();

    await gotoLivePage(page, coreUrl);
    await openLiveDrawer(page);

    const rowLinks = page.locator(
      '[data-bijux-mobile-order="1-top-directories"] .md-nav__link, [data-bijux-mobile-order="2-tree"] .md-nav__link',
    );
    const candidates = await rowLinks.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href") || "").filter(Boolean));

    let foundDeeperRows = false;
    for (const href of candidates.slice(0, 4)) {
      await gotoLivePage(page, new URL(href, page.url()).toString());
      await openLiveDrawer(page);

      if (
        (await page.locator('[data-bijux-mobile-order="2-subdirectories"]').isVisible()) ||
        (await page.locator('[data-bijux-mobile-order="3-third-level-directories"]').isVisible())
      ) {
        foundDeeperRows = true;
        break;
      }
    }

    expect(foundDeeperRows).toBeTruthy();

    await expect(
      page.locator('[data-bijux-mobile-order="2-subdirectories"], [data-bijux-mobile-order="3-third-level-directories"]'),
    ).toBeVisible();
  });

  test("phone drawer avoids duplicate wrapper entries on hub and project roots", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await gotoLivePage(page, liveHubUrl());
    await openLiveDrawer(page);

    const hubTexts = await page
      .locator(
        '[data-bijux-mobile-order="1-sections"] .md-nav__link, [data-bijux-mobile-order="1-tree"] .md-nav__link',
      )
      .evaluateAll((nodes) => nodes.map((node) => (node.textContent || "").trim()).filter(Boolean));
    expect(new Set(hubTexts).size).toBe(hubTexts.length);

    const siteMap = await collectSiteMap(page);
    const coreUrl = siteMap.get("Core");
    expect(coreUrl).toBeTruthy();

    await gotoLivePage(page, coreUrl);
    await openLiveDrawer(page);

    const projectTexts = await page
      .locator(
        '[data-bijux-mobile-order="1-top-directories"] .md-nav__link, [data-bijux-mobile-order="2-tree"] .md-nav__link',
      )
      .evaluateAll((nodes) => nodes.map((node) => (node.textContent || "").trim()).filter(Boolean));
    expect(new Set(projectTexts).size).toBe(projectTexts.length);
  });

  test("tablet keeps compact shell and avoids phone drawer-first mode", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "normal", "normal/tablet-only assertions");

    await gotoLivePage(page, liveHubUrl());

    await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "normal");
    await expect(page.locator(".bijux-hub-strip")).toBeVisible();
    await expect(page.locator(".bijux-site-tabs")).toBeVisible();
    await expect(page.locator(".bijux-nav--mobile")).toBeHidden();
  });

  test("desktop keeps full shell and blocks phone row-model leakage", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "wide", "wide-only assertions");

    await gotoLivePage(page, liveHubUrl());

    await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "wide");
    await expect(page.locator(".bijux-hub-strip")).toBeVisible();
    await expect(page.locator(".bijux-site-tabs")).toBeVisible();
    await expect(page.locator(".bijux-detail-tabs")).toBeVisible();
    await expect(page.locator(".bijux-nav--mobile")).toBeHidden();
  });
});
