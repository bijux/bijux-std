"use strict";
const { expect } = require("@playwright/test");
const measure = require("./measurement");
// Exact root/deep selectors for which automated contrast cannot resolve the gradient backdrop.
const samples = [
  {
    "route": "/",
    "selectors": [
      ".bijux-nav__site-name",
      ".md-nav__link--active > .md-ellipsis",
      ".md-nav__link[href$=\"links/\"] > .md-ellipsis",
      "#bijux-node-3",
      "#bijux-node-4",
      "#bijux-node-5",
      "#bijux-node-6",
      "#bijux-node-7",
      ".md-nav__link[href$=\"reading/\"] > .md-ellipsis",
      ".bijux-tree__item:nth-child(9) > .md-nav__link > .md-ellipsis",
      ".bijux-tree__item:nth-child(10) > .md-nav__link > .md-ellipsis",
      ".bijux-tree__item:nth-child(11) > .md-nav__link > .md-ellipsis",
      ".bijux-tree__item:nth-child(12) > .md-nav__link > .md-ellipsis",
      "#bijux-reference",
      "article > p"
    ]
  },
  {
    "route": "/bijux-core/platform/details/leaf/",
    "selectors": [
      ".bijux-nav__site-name",
      ".bijux-tree > .bijux-tree__item:nth-child(1) > .md-nav__link > .md-ellipsis",
      ".bijux-tree > .bijux-tree__item:nth-child(2) > .md-nav__link > .md-ellipsis",
      "#bijux-node-3",
      "ul[aria-labelledby=\"bijux-node-3\"] > .bijux-tree__item:nth-child(1) > .md-nav__link > .md-ellipsis",
      "ul[aria-labelledby=\"bijux-node-3\"] > .bijux-tree__item:nth-child(2) > .md-nav__link > .md-ellipsis",
      "#bijux-node-3-3",
      "ul[aria-labelledby=\"bijux-node-3-3\"] > .bijux-tree__item:nth-child(1) > .md-nav__link > .md-ellipsis",
      ".md-nav__link--active > .md-ellipsis",
      "#bijux-node-4",
      "#bijux-node-5",
      "#bijux-node-6",
      "#bijux-node-7",
      ".bijux-tree__item:nth-child(8) > .md-nav__link > .md-ellipsis",
      ".bijux-tree__item:nth-child(9) > .md-nav__link > .md-ellipsis",
      ".bijux-tree__item:nth-child(10) > .md-nav__link > .md-ellipsis",
      ".bijux-tree__item:nth-child(11) > .md-nav__link > .md-ellipsis",
      ".bijux-tree__item:nth-child(12) > .md-nav__link > .md-ellipsis",
      ".md-nav__item > .md-nav__link > .md-ellipsis",
      ".md-path__item:nth-child(1) > .md-path__link > .md-ellipsis",
      ".md-path__item:nth-child(2) > .md-path__link > .md-ellipsis",
      ".md-path__item:nth-child(3) > .md-path__link > .md-ellipsis",
      "#platform-leaf-destination",
      "p:nth-child(4)",
      "#detailed-heading",
      "p:nth-child(6)"
    ]
  }
];

async function qualify(page, scheme) {
  const observations = [];
  for (const { route, selectors } of samples) {
    await page.goto(route);
    await expect(page.locator("body")).toHaveAttribute("data-md-color-scheme", scheme);
    for (const selector of selectors) {
      const matches = page.locator(selector);
      expect(await matches.count(), `${route} ${selector}: retained uncertain selector exists`).toBeGreaterThan(0);
      for (const node of await matches.all()) {
        await expect(node).toBeVisible();
        await node.scrollIntoViewIfNeeded();
        const observed = await measure.textOrIcon(page, node);
        observations.push({ route, selector, scheme, ...observed });
        expect(observed.minimum, `${scheme} ${route} ${selector}: rendered gradient contrast`).toBeGreaterThanOrEqual(observed.threshold);
      }
    }
  }
  return observations;
}
module.exports = { qualify };
