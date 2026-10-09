"use strict";
const { expect } = require("@playwright/test");

// The fixture's authored graph, rather than its rendered anchors, is the oracle.
const destinations = [
  {
    "label": "Home",
    "ancestors": [],
    "route": "/",
    "heading": "Bijux reference"
  },
  {
    "label": "Links",
    "ancestors": [],
    "route": "/links/",
    "heading": "Authored link intent"
  },
  {
    "label": "Overview",
    "ancestors": [
      "Platform"
    ],
    "route": "/platform/",
    "heading": "Platform overview"
  },
  {
    "label": "Getting started",
    "ancestors": [
      "Platform"
    ],
    "route": "/platform/start/",
    "heading": "Platform getting started"
  },
  {
    "label": "Overview",
    "ancestors": [
      "Platform",
      "Details"
    ],
    "route": "/platform/details/",
    "heading": "Platform details overview"
  },
  {
    "label": "Leaf destination",
    "ancestors": [
      "Platform",
      "Details"
    ],
    "route": "/platform/details/leaf/",
    "heading": "Platform leaf destination"
  },
  {
    "label": "Overview",
    "ancestors": [
      "Projects"
    ],
    "route": "/projects/",
    "heading": "Projects overview"
  },
  {
    "label": "Getting started",
    "ancestors": [
      "Projects"
    ],
    "route": "/projects/start/",
    "heading": "Projects getting started"
  },
  {
    "label": "Overview",
    "ancestors": [
      "Projects",
      "Details"
    ],
    "route": "/projects/details/",
    "heading": "Projects details overview"
  },
  {
    "label": "Leaf destination",
    "ancestors": [
      "Projects",
      "Details"
    ],
    "route": "/projects/details/leaf/",
    "heading": "Projects leaf destination"
  },
  {
    "label": "Overview",
    "ancestors": [
      "Handbook"
    ],
    "route": "/handbook/",
    "heading": "Handbook overview"
  },
  {
    "label": "Getting started",
    "ancestors": [
      "Handbook"
    ],
    "route": "/handbook/start/",
    "heading": "Handbook getting started"
  },
  {
    "label": "Overview",
    "ancestors": [
      "Handbook",
      "Details"
    ],
    "route": "/handbook/details/",
    "heading": "Handbook details overview"
  },
  {
    "label": "Leaf destination",
    "ancestors": [
      "Handbook",
      "Details"
    ],
    "route": "/handbook/details/leaf/",
    "heading": "Handbook leaf destination"
  },
  {
    "label": "Overview",
    "ancestors": [
      "Knowledge"
    ],
    "route": "/knowledge/",
    "heading": "Knowledge overview"
  },
  {
    "label": "Getting started",
    "ancestors": [
      "Knowledge"
    ],
    "route": "/knowledge/start/",
    "heading": "Knowledge getting started"
  },
  {
    "label": "Overview",
    "ancestors": [
      "Knowledge",
      "Details"
    ],
    "route": "/knowledge/details/",
    "heading": "Knowledge details overview"
  },
  {
    "label": "Leaf destination",
    "ancestors": [
      "Knowledge",
      "Details"
    ],
    "route": "/knowledge/details/leaf/",
    "heading": "Knowledge leaf destination"
  },
  {
    "label": "Overview",
    "ancestors": [
      "Repository"
    ],
    "route": "/repository/",
    "heading": "Repository overview"
  },
  {
    "label": "Getting started",
    "ancestors": [
      "Repository"
    ],
    "route": "/repository/start/",
    "heading": "Repository getting started"
  },
  {
    "label": "Overview",
    "ancestors": [
      "Repository",
      "Details"
    ],
    "route": "/repository/details/",
    "heading": "Repository details overview"
  },
  {
    "label": "Leaf destination",
    "ancestors": [
      "Repository",
      "Details"
    ],
    "route": "/repository/details/leaf/",
    "heading": "Repository leaf destination"
  },
  {
    "label": "Reading reference",
    "ancestors": [],
    "route": "/reading/",
    "heading": "Rich reading reference"
  },
  {
    "label": "Code boundary reference",
    "ancestors": [],
    "route": "/reader-code/",
    "heading": "Code boundary reference"
  },
  {
    "label": "Table boundary reference",
    "ancestors": [],
    "route": "/reader-table/",
    "heading": "Table boundary reference"
  },
  {
    "label": "Native diagram history reference",
    "ancestors": [],
    "route": "/reader-diagrams/",
    "heading": "Native diagram history reference"
  },
  {
    "label": "Editable reading reference",
    "ancestors": [],
    "route": "/search-modality/",
    "heading": "Editable reading reference"
  }
];
const escaped = value => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const heading = value => new RegExp(`^${escaped(value)}(?:¶)?$`);

async function openNavigation(page) {
  await page.locator("[data-bijux-header-control='drawer-toggle']").click();
  await expect(page.locator("#__drawer")).toBeChecked();
  await expect(page.locator("#bijux-navigation")).toBeVisible();
}

async function destinationLink(page, destination) {
  let children = page.locator("#bijux-navigation > .bijux-tree");
  for (const name of destination.ancestors) {
    const group = children.locator(":scope > li > details").filter({
      has: page.locator("summary").filter({ hasText: new RegExp(`^${escaped(name)}$`) }),
    });
    await expect(group).toHaveCount(1);
    const summary = group.locator(":scope > summary");
    await expect(summary).toHaveAccessibleName(name);
    if (!await group.evaluate(node => node.open)) await summary.click();
    await expect(group).toHaveJSProperty("open", true);
    children = group.locator(":scope > ul");
  }
  const link = children.locator(":scope > li > a").filter({ hasText: new RegExp(`^\\s*${escaped(destination.label)}\\s*$`) });
  await expect(link).toHaveCount(1);
  await expect(link).toHaveAccessibleName(destination.label);
  expect(await link.evaluate(node => new URL(node.href).pathname)).toBe(destination.route);
  return link;
}

async function authoredDestinationCoverage(page, info) {
  const observations = [];
  const rootURL = new URL("/", info.project.use.baseURL).href;
  await page.goto(rootURL);
  await expect(page.locator("main h1")).toHaveText(heading("Bijux reference"));
  for (const destination of destinations) {
    await expect(page).toHaveURL(rootURL);
    await openNavigation(page);
    const link = await destinationLink(page, destination);
    const previousDocument = await page.evaluateHandle(() => document);
    let retainedDocument;
    try {
      await link.click();
      await expect(page).toHaveURL(new URL(destination.route, rootURL).href);
      await expect(page.locator("main h1")).toHaveText(heading(destination.heading));
      try { retainedDocument = await previousDocument.evaluate(original => original === document); }
      catch (error) {
        if (!/Execution context was destroyed|JSHandles can be evaluated only in the context|Execution context is not available|Cannot find context/.test(error.message)) throw error;
        await page.waitForLoadState("domcontentloaded");
        retainedDocument = false;
      }
    } finally { await previousDocument.dispose(); }
    await expect(page.locator("#__drawer")).not.toBeChecked();
    if (retainedDocument && destination.route !== "/") await expect(page.locator("main h1")).toBeFocused();
    expect(await page.evaluate(() => document.activeElement.isConnected)).toBe(true);
    await openNavigation(page);
    const current = page.locator("#bijux-navigation .bijux-tree a[aria-current='page']");
    await expect(current).toHaveCount(1);
    expect(await current.evaluate(node => new URL(node.href).pathname)).toBe(destination.route);
    const ancestors = await current.evaluate(node => {
      const names = [];
      for (let parent = node.parentElement; parent; parent = parent.parentElement) {
        if (parent.tagName === "DETAILS") names.push({ name: parent.querySelector(":scope > summary").textContent.trim(), open: parent.open });
      }
      return names.reverse();
    });
    expect(ancestors).toEqual(destination.ancestors.map(name => ({ name, open: true })));
    await page.keyboard.press("Escape");
    await expect(page.locator("#__drawer")).not.toBeChecked();
    await expect(page.locator("[data-bijux-header-control='drawer-toggle']")).toBeFocused();
    observations.push({ ...destination, retainedDocument, observedURL: page.url(), current: await current.getAttribute("aria-current") });
    if (destination.route !== "/") {
      await page.goBack();
      await expect(page).toHaveURL(rootURL);
      await expect(page.locator("main h1")).toHaveText(heading("Bijux reference"));
      await expect(page.locator("#__drawer")).not.toBeChecked();
    }
  }
  await info.attach("authored-destination-coverage.json", { body: Buffer.from(JSON.stringify(observations)), contentType: "application/json" });
  expect(observations).toHaveLength(destinations.length);
}
module.exports = { destinations, authoredDestinationCoverage };
