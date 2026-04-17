const { expect } = require("@playwright/test");
const { ensureDrawerOpen, navOrderIndex, extractLinkTexts } = require("./navigation");

const REQUIRED_SITE_LABELS = ["Bijux", "Core", "Canon", "Atlas", "Proteomics", "Pollenomics", "Masterclass"];

function liveE2EEnabled() {
  return process.env.BIJUX_LIVE_E2E === "1";
}

function liveHubUrl() {
  return process.env.BIJUX_LIVE_HUB_URL || "https://bijux.io/";
}

function asAbsoluteUrl(rawUrl, baseUrl) {
  try {
    return new URL(rawUrl, baseUrl).toString();
  } catch {
    return rawUrl;
  }
}

async function gotoLivePage(page, url) {
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await expect(page.locator("body")).toBeVisible();
}

async function openLiveDrawer(page) {
  const mobileTree = page.locator(".bijux-nav--mobile [data-bijux-mobile-order]").first();
  if (!(await mobileTree.isVisible())) {
    await ensureDrawerOpen(page);
  }
  await expect(page.locator(".md-sidebar--primary")).toBeVisible();
  await expect(mobileTree).toBeVisible();
}

function sitesBlock(page) {
  return page.locator(".bijux-mobile-hub[data-bijux-mobile-order$='sites']");
}

async function collectSiteMap(page) {
  await openLiveDrawer(page);
  const entries = await sitesBlock(page).locator(".bijux-mobile-hub__link").evaluateAll((nodes) =>
    nodes
      .map((node) => ({
        label: (node.textContent || "").trim(),
        href: node.getAttribute("href") || "",
      }))
      .filter((entry) => entry.label && entry.href),
  );

  const map = new Map();
  for (const entry of entries) {
    map.set(entry.label, asAbsoluteUrl(entry.href, page.url()));
  }
  return map;
}

async function expectCanonicalSiteEntries(page) {
  const links = sitesBlock(page).locator(".bijux-mobile-hub__link");
  const labels = await extractLinkTexts(links);
  for (const label of REQUIRED_SITE_LABELS) {
    expect(labels).toContain(label);
  }
  expect(new Set(labels).size).toBe(labels.length);

  const hrefs = await links.evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href") || ""));
  expect(hrefs.every((href) => href.trim().length > 0)).toBeTruthy();
}

async function expectLocalBeforeSites(page, localSelector) {
  const localIndex = await navOrderIndex(page, localSelector);
  const sitesIndex = await navOrderIndex(page, ".bijux-mobile-hub[data-bijux-mobile-order$='sites']");
  expect(localIndex).toBeGreaterThanOrEqual(0);
  expect(sitesIndex).toBeGreaterThan(localIndex);
}

module.exports = {
  REQUIRED_SITE_LABELS,
  liveE2EEnabled,
  liveHubUrl,
  gotoLivePage,
  openLiveDrawer,
  sitesBlock,
  collectSiteMap,
  expectCanonicalSiteEntries,
  expectLocalBeforeSites,
};
