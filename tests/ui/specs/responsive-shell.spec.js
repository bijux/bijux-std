const { test, expect } = require("@playwright/test");

const FIXTURE_PATH = "/tests/ui/fixtures/responsive-shell.html";

async function displayValue(page, selector) {
  return page.locator(selector).first().evaluate((el) => window.getComputedStyle(el).display);
}

function parseTranslateX(transformValue) {
  if (!transformValue || transformValue === "none") return 0;
  const matrix3dMatch = transformValue.match(/^matrix3d\((.+)\)$/);
  if (matrix3dMatch) {
    const parts = matrix3dMatch[1].split(",").map((value) => Number.parseFloat(value.trim()));
    return Number.isFinite(parts[12]) ? parts[12] : 0;
  }
  const matrixMatch = transformValue.match(/^matrix\((.+)\)$/);
  if (matrixMatch) {
    const parts = matrixMatch[1].split(",").map((value) => Number.parseFloat(value.trim()));
    return Number.isFinite(parts[4]) ? parts[4] : 0;
  }
  return 0;
}

test.describe("bijux docs shell responsive behavior", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(FIXTURE_PATH);
    await page.waitForFunction(() => Boolean(window.bijuxViewportProfile));
  });

  test("viewport-profile exposes required reference contract", async ({ page }) => {
    const references = await page.evaluate(() => window.bijuxViewportProfile.verifyReferenceWidths());
    expect(references).toEqual({
      390: "phone",
      768: "normal",
      1024: "normal",
      1280: "desktop",
      1920: "wide",
    });

    const contract = await page.evaluate(() => window.bijuxViewportProfile.verifyContract());
    expect(contract.ok).toBeTruthy();
  });

  test("phone keeps drawer-first navigation and hides ribbons", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "phone", "phone-only assertions");

    await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "phone");
    await expect(page.locator("body")).toHaveAttribute("data-bijux-viewport", "phone");

    await expect(page.locator(".bijux-nav--mobile")).toBeVisible();
    await expect(page.locator(".bijux-nav--scoped")).toBeHidden();

    expect(await displayValue(page, ".bijux-hub-strip")).toBe("none");
    expect(await displayValue(page, ".bijux-site-tabs")).toBe("none");
    expect(await displayValue(page, ".bijux-detail-tabs:not(.bijux-course-tabs)")).toBe("none");

    const sidebarWidth = await page.locator(".md-sidebar--primary").evaluate((el) => el.getBoundingClientRect().width);
    const viewportWidth = page.viewportSize().width;
    expect(sidebarWidth).toBeLessThanOrEqual(Math.ceil(viewportWidth * 0.9) + 1);

    const closedSidebarLeft = await page
      .locator(".md-sidebar--primary")
      .evaluate((el) => Number.parseFloat(window.getComputedStyle(el).left || "0"));
    expect(closedSidebarLeft).toBeLessThan(0);

    await page.locator('[data-bijux-header-control="drawer-toggle"]').click();
    const openSidebarTransform = await page
      .locator(".md-sidebar--primary")
      .evaluate((el) => window.getComputedStyle(el).transform || "none");
    const openSidebarLeft = await page
      .locator(".md-sidebar--primary")
      .evaluate((el) => Number.parseFloat(window.getComputedStyle(el).left || "0"));
    expect(openSidebarLeft).toBeGreaterThanOrEqual(0);
    expect(Math.abs(parseTranslateX(openSidebarTransform))).toBeLessThanOrEqual(0.5);

    const toggleHitTarget = await page.locator('[data-bijux-header-control="drawer-toggle"]').evaluate((el) => {
      const rect = el.getBoundingClientRect();
      const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
      return hit === el || el.contains(hit);
    });
    expect(toggleHitTarget).toBeTruthy();

    const viewportMetrics = await page.evaluate(() => ({
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      scrollX: window.scrollX,
    }));
    expect(viewportMetrics.scrollWidth).toBeLessThanOrEqual(viewportMetrics.clientWidth);
    expect(viewportMetrics.scrollX).toBe(0);

    await expect(page.locator(".bijux-header-tools .md-search")).toBeHidden();
    await page.locator('[data-bijux-header-control="search-toggle"]').click();
    await expect(page.locator(".bijux-header-tools .md-search")).toBeVisible();
  });

  test("normal keeps compact ribbons and hides phone row model", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "normal", "normal-only assertions");

    await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "normal");

    await expect(page.locator(".bijux-nav--mobile")).toBeHidden();
    await expect(page.locator(".bijux-nav--scoped")).toBeVisible();

    expect(await displayValue(page, ".bijux-hub-strip")).not.toBe("none");
    expect(await displayValue(page, ".bijux-site-tabs")).toBe("block");
    expect(await displayValue(page, ".bijux-detail-tabs:not(.bijux-course-tabs)")).toBe("block");
    expect(await displayValue(page, ".bijux-course-tabs")).toBe("none");
  });

  test("wide keeps desktop shell and suppresses mobile navigation", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "wide", "wide-only assertions");

    await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "wide");

    await expect(page.locator(".bijux-nav--mobile")).toBeHidden();
    await expect(page.locator(".bijux-nav--scoped")).toBeVisible();
    expect(await displayValue(page, ".md-header__title")).toBe("none");
  });

  test("tablet keeps compact ribbons while course strip stays hidden", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "normal", "normal-only assertions");

    await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "normal");
    await expect(page.locator(".bijux-hub-strip")).toBeVisible();
    await expect(page.locator(".bijux-site-tabs")).toBeVisible();
    await expect(page.locator(".bijux-detail-tabs:not(.bijux-course-tabs)")).toBeVisible();
    await expect(page.locator(".bijux-course-tabs")).toBeHidden();
    await expect(page.locator(".bijux-mobile-local").first()).toBeHidden();
    await expect(page.locator(".bijux-mobile-hub").first()).toBeHidden();
  });

  test("desktop prevents phone row-model leakage", async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== "wide", "wide-only assertions");

    await expect(page.locator("html")).toHaveAttribute("data-bijux-viewport", "wide");
    await expect(page.locator(".bijux-nav--mobile")).toBeHidden();
    await expect(page.locator(".bijux-mobile-local").first()).toBeHidden();
    await expect(page.locator(".bijux-mobile-hub").first()).toBeHidden();
    await expect(page.locator("[data-bijux-mobile-order]").first()).toBeHidden();
    await expect(page.locator(".bijux-hub-strip")).toBeVisible();
    await expect(page.locator(".bijux-site-tabs")).toBeVisible();
  });
});
