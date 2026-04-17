const { expect } = require("@playwright/test");

async function drawerState(page) {
  return page.locator("#__drawer").isChecked();
}

async function ensureDrawerOpen(page) {
  const toggle = page.locator('[data-bijux-header-control="drawer-toggle"]');
  const isOpen = await drawerState(page);
  if (!isOpen) {
    try {
      await toggle.click();
    } catch {
      await toggle.click({ force: true });
    }
  }
  if (!(await drawerState(page))) {
    await page.evaluate(() => {
      const drawer = document.querySelector("#__drawer");
      if (!drawer) return;
      drawer.checked = true;
      drawer.dispatchEvent(new Event("change", { bubbles: true }));
      drawer.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }
  await expect(page.locator("#__drawer")).toBeChecked();
}

async function ensureDrawerClosed(page) {
  const toggle = page.locator('[data-bijux-header-control="drawer-toggle"]');
  const isOpen = await drawerState(page);
  if (isOpen) {
    try {
      await toggle.click();
    } catch {
      await toggle.click({ force: true });
    }
  }
  if (await drawerState(page)) {
    await page.evaluate(() => {
      const drawer = document.querySelector("#__drawer");
      if (!drawer) return;
      drawer.checked = false;
      drawer.dispatchEvent(new Event("change", { bubbles: true }));
      drawer.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }
  await expect(page.locator("#__drawer")).not.toBeChecked();
}

async function navOrderIndex(page, selector) {
  return page.evaluate((targetSelector) => {
    const nodes = Array.from(document.querySelectorAll("[data-bijux-mobile-order]"));
    return nodes.findIndex((node) => node.matches(targetSelector));
  }, selector);
}

async function extractLinkTexts(locator) {
  return locator.evaluateAll((nodes) => nodes.map((node) => node.textContent.trim()).filter(Boolean));
}

async function expectUniqueLinkTexts(locator) {
  const texts = await extractLinkTexts(locator);
  expect(new Set(texts).size).toBe(texts.length);
}

async function expectOrderedRows(page, firstSelector, secondSelector) {
  const firstIndex = await navOrderIndex(page, firstSelector);
  const secondIndex = await navOrderIndex(page, secondSelector);
  expect(firstIndex).toBeGreaterThanOrEqual(0);
  expect(secondIndex).toBeGreaterThan(firstIndex);
}

module.exports = {
  ensureDrawerOpen,
  ensureDrawerClosed,
  navOrderIndex,
  extractLinkTexts,
  expectUniqueLinkTexts,
  expectOrderedRows,
};
