const { test, expect } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const outside = "https://outside.example";
test.beforeEach(async ({ page, browser, context }, info) => {
  info.annotations.push({
    type: "browser-version",
    description: browser.version(),
  });
  page.on("pageerror", (error) => {
    throw error;
  });
  await info.attach("engine-version", {
    body: JSON.stringify({
      engine: info.project.use.browserName,
      version: browser.version(),
    }),
    contentType: "application/json",
  });
  await context.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (
      url.origin === new URL(info.project.use.baseURL).origin ||
      url.origin === outside
    )
      await route.fallback();
    else await route.abort("blockedbyclient");
  });
});
async function mount(page) {
  await page.goto("/links/");
  await expect(page.locator("#link-new-tab")).toHaveAttribute(
    "rel",
    "sponsored noopener",
  );
}
async function controlledOutside(context) {
  await context.route(outside + "/**", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: "<!doctype html><h1>Controlled external destination</h1>",
    }),
  );
}

test("authored target, download, relation and description remain distinct", async ({
  page,
}) => {
  await mount(page);
  await expect(page.locator("#link-ordinary")).not.toHaveAttribute("target");
  await expect(page.locator("#link-ordinary")).toHaveAttribute(
    "rel",
    "external nofollow",
  );
  await expect(page.locator("#link-ordinary")).toHaveAttribute(
    "referrerpolicy",
    "no-referrer",
  );
  await expect(page.locator("#link-explicit-self")).toHaveAttribute(
    "target",
    "_self",
  );
  await expect(page.locator("#link-named")).toHaveAttribute(
    "target",
    "research-window",
  );
  await expect(page.locator("#link-download")).toHaveAttribute(
    "download",
    "authored-report.txt",
  );
  await expect(page.locator("#link-download")).not.toHaveAttribute("target");
  await expect(page.locator("#link-privacy")).toHaveAttribute(
    "rel",
    "noreferrer nofollow noopener",
  );
  await expect(page.locator("#link-privacy")).toHaveAttribute(
    "referrerpolicy",
    "strict-origin",
  );
  await expect(page.locator("#link-new-tab")).toHaveAccessibleName(
    "Authored new tab (opens in new tab) ↗",
  );
  await expect(page.locator("#link-download")).toHaveAccessibleName(
    "Reader report (download)",
  );
  await expect(page.locator("#link-described")).toHaveAccessibleName(
    "Authored accessible name",
  );
  await expect(page.locator("#link-described")).toHaveAccessibleDescription(
    /Authored resource context.*opens in new tab/,
  );
  await expect(
    page
      .locator("#link-mail, #link-phone, #link-internal, #link-hash")
      .locator("[data-bijux-link-indication]"),
  ).toHaveCount(0);
});

test("ordinary external click stays in its window and Back returns to reading", async ({
  page,
  context,
}) => {
  await controlledOutside(context);
  await mount(page);
  const url = page.url();
  await page
    .getByRole("link", { name: "Ordinary external reader ↗", exact: true })
    .click();
  await expect(page).toHaveURL(outside + "/ordinary");
  await expect(
    page.getByRole("heading", { name: "Controlled external destination" }),
  ).toBeVisible();
  expect(context.pages()).toHaveLength(1);
  await page.goBack();
  await expect(page).toHaveURL(url);
  await expect(
    page.getByRole("heading", { name: /^Authored link intent/ }),
  ).toBeVisible();
  await expect(page.locator("#link-ordinary")).not.toHaveAttribute("target");
});

test("authored new tab uses native activation with an isolated opener", async ({
  page,
  context,
}) => {
  await controlledOutside(context);
  await mount(page);
  const url = page.url();
  const popupJob = page.waitForEvent("popup");
  await page
    .getByRole("link", {
      name: "Authored new tab (opens in new tab) ↗",
      exact: true,
    })
    .click();
  const popup = await popupJob;
  await expect(popup).toHaveURL(outside + "/new-tab");
  await expect(
    popup.getByRole("heading", { name: "Controlled external destination" }),
  ).toBeVisible();
  expect(await popup.evaluate(() => window.opener === null)).toBe(true);
  await expect(page).toHaveURL(url);
  await popup.close();
});

test("authored download keeps its filename and actual delivered bytes", async ({
  page,
}, info) => {
  await mount(page);
  const url = page.url();
  const downloadJob = page.waitForEvent("download");
  await page
    .getByRole("link", { name: "Reader report (download)", exact: true })
    .click();
  const download = await downloadJob;
  expect(download.suggestedFilename()).toBe("authored-report.txt");
  const output = info.outputPath("authored-report.txt");
  await download.saveAs(output);
  expect(await download.failure()).toBeNull();
  const bytes = fs.readFileSync(output);
  expect(bytes.toString()).toBe("Authored reader report bytes.\n");
  await info.attach("download-bytes", {
    path: output,
    contentType: "text/plain",
  });
  await info.attach("download-sha256", {
    body: crypto.createHash("sha256").update(bytes).digest("hex"),
    contentType: "text/plain",
  });
  await expect(page).toHaveURL(url);
});

test("native internal and fragment journeys retain Back and Forward", async ({
  page,
}) => {
  await mount(page);
  const url = page.url();
  await page.getByRole("link", { name: "Local heading", exact: true }).click();
  await expect(page).toHaveURL(url + "#authored-heading");
  await expect(
    page.getByRole("heading", { name: /^Authored heading/ }),
  ).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(url);
  await page
    .getByRole("link", { name: "Internal document", exact: true })
    .click();
  await expect(page).toHaveURL(/\/platform\/start\/$/);
  await expect(
    page.getByRole("heading", { name: /^Platform getting started/ }),
  ).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(url);
  await expect(
    page.locator("#link-new-tab [data-bijux-link-indication]"),
  ).toHaveCount(1);
  await page.goForward();
  await expect(page).toHaveURL(/\/platform\/start\/$/);
});

test("real document replacement never accumulates link warnings", async ({
  page,
}) => {
  await mount(page);
  const url = page.url();
  for (let index = 0; index < 5; index++) {
    await page
      .getByRole("link", { name: "Internal document", exact: true })
      .click();
    await expect(page).toHaveURL(/\/platform\/start\/$/);
    await page.goBack();
    await expect(page).toHaveURL(url);
    await expect(
      page.locator("#link-new-tab [data-bijux-link-indication]"),
    ).toHaveCount(1);
    await expect(page.locator("#link-described")).toHaveAccessibleDescription(
      /Authored resource context.*opens in new tab/,
    );
    const ids = await page
      .locator("[data-bijux-link-indication]")
      .evaluateAll((nodes) => nodes.map((node) => node.id));
    expect(new Set(ids).size).toBe(ids.length);
  }
});

test("product extension link changes preserve new intent and disposable annotations", async ({
  page,
}) => {
  await mount(page);
  // This is an explicit extension fixture, not synthetic activation or control-state acceptance.
  await page.evaluate(() => {
    const link = document.createElement("a");
    link.id = "link-extension";
    link.href = "https://outside.example/extension";
    link.target = "_blank";
    link.rel = "nofollow opener";
    link.textContent = "Extension destination";
    document.querySelector("article").append(link);
  });
  await expect(page.locator("#link-extension")).toHaveAttribute(
    "rel",
    "nofollow noopener",
  );
  await expect(
    page.locator("#link-extension [data-bijux-link-indication]"),
  ).toHaveCount(1);
  await page.locator("#link-extension").evaluate((link) => {
    link.target = "_self";
    link.download = "extension-data.txt";
    link.rel = "author noreferrer";
  });
  await expect(page.locator("#link-extension")).toHaveAttribute(
    "target",
    "_self",
  );
  await expect(page.locator("#link-extension")).toHaveAttribute(
    "rel",
    "author noreferrer",
  );
  await expect(page.locator("#link-extension")).toHaveAccessibleName(
    "Extension destination (download) ↗",
  );
  await page.locator("#link-extension").evaluate((link) => {
    link.remove();
    window.retainedExtensionLink = link;
  });
  await expect
    .poll(() =>
      page.evaluate(
        () =>
          window.retainedExtensionLink.querySelectorAll(
            "[data-bijux-link-indication]",
          ).length,
      ),
    )
    .toBe(0);
  expect(
    await page.evaluate(() => window.retainedExtensionLink.getAttribute("rel")),
  ).toBe("author noreferrer");
});

test("exact historical authored producer demonstrates blanket target and relation loss", async ({
  page,
}) => {
  const old = fs.readFileSync(
    path.join(__dirname, "external-link-policy/historical-consumer.js"),
  );
  await page.route("**/assets/javascripts/external-links.js", (route) =>
    route.fulfill({ contentType: "text/javascript", body: old }),
  );
  await page.goto("/links/");
  await expect(page.locator("#link-ordinary")).toHaveAttribute(
    "target",
    "_blank",
  );
  await expect(page.locator("#link-ordinary")).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );
  await expect(page.locator("#link-explicit-self")).toHaveAttribute(
    "target",
    "_blank",
  );
  await expect(page.locator("#link-named")).toHaveAttribute("target", "_blank");
  await expect(page.locator("#link-new-tab")).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );
  await expect(
    page.locator("#link-new-tab [data-bijux-link-indication]"),
  ).toHaveCount(0);
});

test("no-script native same-window, fragment and download intent remains usable", async ({
  browser,
}, info) => {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: info.project.use.viewport,
  });
  try {
    await controlledOutside(context);
    const page = await context.newPage();
    await page.goto(new URL("/links/", info.project.use.baseURL).href);
    const url = page.url();
    await expect(page.locator("#link-ordinary")).not.toHaveAttribute("target");
    await expect(page.locator("#link-explicit-self")).toHaveAttribute(
      "target",
      "_self",
    );
    await expect(page.locator("#link-new-tab")).toHaveAttribute(
      "target",
      "_blank",
    );
    await page
      .getByRole("link", { name: "Local heading", exact: true })
      .click();
    await expect(page).toHaveURL(url + "#authored-heading");
    await expect(
      page.getByRole("heading", { name: /^Authored heading/ }),
    ).toBeVisible();
    await page.goBack();
    await expect(page).toHaveURL(url);
    await page
      .getByRole("link", { name: "Ordinary external reader", exact: true })
      .click();
    await expect(page).toHaveURL(outside + "/ordinary");
    await page.goBack();
    await expect(page).toHaveURL(url);
    const job = page.waitForEvent("download");
    await page
      .getByRole("link", { name: "Reader report", exact: true })
      .click();
    const download = await job;
    expect(download.suggestedFilename()).toBe("authored-report.txt");
    const file = info.outputPath("no-script-authored-report.txt");
    await download.saveAs(file);
    expect(fs.readFileSync(file).toString()).toBe(
      "Authored reader report bytes.\n",
    );
    await info.attach("no-script-download-bytes", {
      path: file,
      contentType: "text/plain",
    });
    // No-script new-tab warning/security admission is authored responsibility,
    // not certified by this ordinary native fallback case.
  } finally {
    await context.close();
  }
});
