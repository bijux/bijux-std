"use strict";
const { expect } = require("@playwright/test");
const { settle } = require("../contrast-targets/measurement");

async function reachableDrawer(page, info, insets = { top: 0, right: 0, bottom: 0, left: 0 }, navigate = true) {
  const nav = page.locator("#bijux-navigation");
  const expected = await nav.locator("summary, a[href], button[data-bijux-control-close]").evaluateAll(nodes =>
    nodes.map(node => ({ key: node.tagName === "A" ? node.href : node.matches("[data-bijux-control-close]") ? "close-navigation" : node.id, tag: node.tagName })));
  expect(expected.length).toBeGreaterThan(20);
  const seen = new Set();
  const observations = [];
  const key = info.project.use.browserName === "webkit" ? "Alt+Tab" : "Tab";
  for (let action = 0; action < expected.length * 4 && seen.size < new Set(expected.map(entry => entry.key)).size; action++) {
    const current = await page.evaluate(() => {
      const node = document.activeElement;
      if (!node?.closest("#bijux-navigation")) return null;
      return { key: node.tagName === "A" ? node.href : node.matches("[data-bijux-control-close]") ? "close-navigation" : node.id,
        summary: node.tagName === "SUMMARY", open: node.parentElement.open };
    });
    expect(current, "Modal traversal remains inside its complete navigation").not.toBeNull();
    if (current.summary && !current.open) await page.keyboard.press("Space");
    if (expected.some(entry => entry.key === current.key)) {
      await settle(nav);
      const geometry = await page.evaluate(insets => {
        const node = document.activeElement, rect = node.getBoundingClientRect();
        const view = window.visualViewport;
        const usable = { left: (view?.offsetLeft || 0) + insets.left,
          right: (view?.offsetLeft || 0) + (view?.width || innerWidth) - insets.right,
          top: (view?.offsetTop || 0) + insets.top,
          bottom: (view?.offsetTop || 0) + (view?.height || innerHeight) - insets.bottom };
        const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
        const scrollers = [];
        for (let parent = node.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
          const style = getComputedStyle(parent);
          if (["auto", "scroll"].includes(style.overflowY) && parent.scrollHeight > parent.clientHeight + 1)
            scrollers.push({ className: parent.className, primary: parent.matches(".md-sidebar--primary") });
        }
        return { rect: { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom }, usable,
          owned: hit === node || node.contains(hit), scrollers, viewport: { width: innerWidth, height: innerHeight,
            visualWidth: view?.width, visualHeight: view?.height }, pageScroll: document.scrollingElement.scrollTop };
      }, insets);
      expect(geometry.rect.left).toBeGreaterThanOrEqual(geometry.usable.left - 1);
      expect(geometry.rect.right).toBeLessThanOrEqual(geometry.usable.right + 1);
      expect(geometry.rect.top).toBeGreaterThanOrEqual(geometry.usable.top - 1);
      expect(geometry.rect.bottom).toBeLessThanOrEqual(geometry.usable.bottom + 1);
      expect(geometry.owned, "Focused target has an ordinary unoccluded activation point").toBe(true);
      expect(geometry.scrollers, "One primary scroller owns the complete tree and registry").toEqual([
        { className: expect.any(String), primary: true },
      ]);
      observations.push({ key: current.key, ...geometry });
      seen.add(current.key);
    }
    await page.keyboard.press(key);
  }
  expect([...seen].sort(), "Every branch, local destination, site entry and close control is reachable").toEqual(
    [...new Set(expected.map(entry => entry.key))].sort());
  await info.attach("drawer-viewport-reachability", { body: Buffer.from(JSON.stringify({ insets, physicalDeviceQualified: false,
    observations }, null, 2)), contentType: "application/json" });
  if (!navigate) return;
  const close = nav.getByRole("button", { name: "Close navigation", exact: true });
  for (let action = 0; action < expected.length * 2 && !await close.evaluate(node => node === document.activeElement); action++)
    await page.keyboard.press(key);
  await expect(close).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page.locator("#__drawer")).not.toBeChecked();
  const opener = page.locator("[data-bijux-header-control='drawer-toggle']");
  await expect(opener).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page.locator("#__drawer")).toBeChecked();
  const endpoint = nav.getByRole("link", { name: "Research extension", exact: true });
  // Ordinary keyboard traversal, not scrollIntoView or a forced pointer action.
  for (let action = 0; action < expected.length * 2 && !await endpoint.evaluate(node => node === document.activeElement); action++)
    await page.keyboard.press(key);
  await expect(endpoint).toBeFocused();
  const response = page.waitForResponse(response => response.url() === new URL("/reading/", info.project.use.baseURL).href);
  await page.keyboard.press("Enter");
  expect((await response).status()).toBe(200);
  await expect(page).toHaveURL(/\/reading\/$/);
  await expect(page.locator("main h1")).toHaveText(/^Rich reading reference(?:¶)?$/);
  await expect(page.locator("#__drawer")).not.toBeChecked();
  await expect(page).toHaveTitle("Reading reference - Bijux");
}
module.exports = { reachableDrawer };
