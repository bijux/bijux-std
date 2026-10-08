"use strict";
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { test, expect } = require("@playwright/test");
const { nativeAnswer } = require("./helpers/search");
const generated = path.resolve(
  process.env.BIJUX_GENERATED_ROOT ||
    path.join(__dirname, "../../../../artifacts/bijux-docs/generated"),
);
const manifestBytes = fs.readFileSync(path.join(generated, "manifest.json"));
const definitions = [
  { name: "owned phone", width: 320 },
  { name: "owned compact", width: 768 },
  { name: "owned desktop", width: 1440 },
  { name: "native inline desktop", width: 1440, native: true },
];
const control = (page, kind) =>
  page.locator(`[data-bijux-header-control='${kind}-toggle']`);
const surface = (page, kind) =>
  page.locator(
    kind === "drawer" ? ".md-sidebar--primary" : "[data-md-component='search']",
  );
const toggle = (page, kind) =>
  page.locator(kind === "drawer" ? "#__drawer" : "#__search");
const query = (page) => page.locator("[data-md-component='search-query']");
const tabKey = (page, reverse = false) =>
  `${page.context().browser().browserType().name() === "webkit" ? "Alt+" : ""}${reverse ? "Shift+" : ""}Tab`;
async function relation(page, kind, evidence) {
  const observed = await page.evaluate((kind) => {
    const invoker = document.querySelector(
      `[data-bijux-header-control='${kind}-toggle']`,
    );
    const popup = document.querySelector(
      kind === "drawer"
        ? ".md-sidebar--primary"
        : "[data-md-component='search']",
    );
    const id = invoker.getAttribute("aria-controls");
    return {
      kind,
      id,
      exactSurface: !!id && document.getElementById(id) === popup,
      matches: [...document.querySelectorAll("[id]")].filter(
        (node) => node.getAttribute("id") === id,
      ).length,
      haspopup: invoker.getAttribute("aria-haspopup"),
      expanded: invoker.getAttribute("aria-expanded"),
      role: popup.getAttribute("role"),
      modal: popup.getAttribute("aria-modal"),
      name: popup.getAttribute("aria-label"),
    };
  }, kind);
  evidence.push(observed);
  expect(observed.exactSurface).toBe(true);
  expect(observed.matches).toBe(1);
  expect(observed.id).not.toBe(
    kind === "drawer" ? "bijux-navigation" : "__search",
  );
  expect(observed.haspopup).toBe("dialog");
  return observed;
}
async function focusThroughTab(page, target, backwards = false) {
  for (
    let step = 0;
    step < 80 &&
    !(await target.evaluate((node) => node === document.activeElement));
    step++
  )
    await page.keyboard.press(tabKey(page, backwards));
  await expect(target).toBeFocused();
}
async function searchJourney(
  page,
  definition,
  evidence,
  returnFromReader = false,
  documentIdentity,
) {
  const inline =
    definition.native && (await control(page, "search").isHidden());
  const invoker = inline ? query(page) : control(page, "search");
  await relation(page, "search", evidence);
  await focusThroughTab(page, invoker, returnFromReader);
  if (!inline) await page.keyboard.press("Space");
  await expect(toggle(page, "search")).toBeChecked();
  await expect(query(page)).toBeFocused();
  await expect(surface(page, "search")).toHaveAttribute("role", "dialog");
  await expect(surface(page, "search")).toHaveAttribute("aria-modal", "true");
  await expect(surface(page, "search")).toHaveAccessibleName(
    "Search documentation",
  );
  expect((await relation(page, "search", evidence)).expanded).toBe("true");
  await page.keyboard.press("ControlOrMeta+A");
  await page.keyboard.insertText("resilient navigation");
  const answer = await nativeAnswer(page);
  for (const key of [...Array(6).fill("Tab"), ...Array(6).fill("Shift+Tab")]) {
    await page.keyboard.press(key);
    await expect(surface(page, "search").locator(":focus")).toHaveCount(1);
    await expect(toggle(page, "search")).toBeChecked();
  }
  await page.keyboard.press("Escape");
  await expect(toggle(page, "search")).not.toBeChecked();
  await expect(invoker).toBeFocused();
  expect((await relation(page, "search", evidence)).expanded).toBe("false");
  if (inline)
    await expect(surface(page, "search")).toHaveAccessibleName(
      "Search documentation",
    );
  if (inline) await query(page).click();
  else await control(page, "search").click();
  await expect(toggle(page, "search")).toBeChecked();
  await nativeAnswer(page);
  const destination = await answer.getAttribute("href");
  for (
    let step = 0;
    step < 40 &&
    !(await answer.evaluate((node) => node === document.activeElement));
    step++
  )
    await page.keyboard.press("ArrowDown");
  await expect(answer).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await expect(answer).not.toBeFocused();
  await page.keyboard.press("ArrowDown");
  await expect(answer).toBeFocused();
  const origin = await page.evaluate(() => performance.timeOrigin),
    beforeURL = page.url(),
    beforeHeading = await page.locator(".md-content h1").textContent();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(destination);
  await expect(page.locator(".md-content h1")).toContainText(
    "leaf destination",
  );
  await expect(toggle(page, "search")).not.toBeChecked();
  expect(
    await page.evaluate(
      (original) => original === document,
      documentIdentity,
    ),
  ).toBe(true);
  await relation(page, "search", evidence);
  await page.goBack();
  await expect(page).toHaveURL(beforeURL);
  await expect(page.locator(".md-content h1")).toHaveText(beforeHeading);
  expect(
    await page.evaluate(
      (original) => original === document,
      documentIdentity,
    ),
  ).toBe(true);
  await relation(page, "search", evidence);
  return { destination, origin, back: beforeURL };
}

for (const definition of definitions) {
  test(`${definition.name} binds popup relationships to the actual controlled surfaces`, async ({
    browser,
  }, info) => {
    info.annotations.push({
      type: "browser-version",
      description: browser.version(),
    });
    const context = await browser.newContext({
      viewport: { width: definition.width, height: 900 },
    });
    const page = await context.newPage();
    const evidence = {
      definition,
      engine: info.project.use.browserName,
      version: browser.version(),
      manifest_sha256: crypto
        .createHash("sha256")
        .update(manifestBytes)
        .digest("hex"),
      keyboard_protocol:
        info.project.use.browserName === "webkit"
          ? "Option-Tab/Option-Shift-Tab outside modal; ordinary Tab/Shift-Tab inside"
          : "Tab/Shift-Tab",
      observations: [],
      errors: [],
      missing: [],
      started_at: new Date().toISOString(),
    };
    page.on("pageerror", (error) => evidence.errors.push(String(error)));
    page.on("response", (response) => {
      if (
        new URL(response.url()).origin === info.project.use.baseURL &&
        response.status() >= 400
      )
        evidence.missing.push({
          url: response.url(),
          status: response.status(),
        });
    });
    const rootURL =
      info.project.use.baseURL +
      (definition.native ? "/fixtures/native-header/" : "/bijux-core/");
    let documentIdentity;
    try {
      await page.goto(rootURL);
      documentIdentity = await page.evaluateHandle(() => document);
      if (!definition.native) {
        await expect(page.locator("body")).toHaveAttribute(
          "data-bijux-drawer-ready",
          "true",
        );
        await relation(page, "drawer", evidence.observations);
        if (definition.width < 1220) {
          await focusThroughTab(page, control(page, "drawer"));
          await page.keyboard.press("Space");
          await expect(toggle(page, "drawer")).toBeChecked();
          await expect(surface(page, "drawer")).toHaveAttribute(
            "role",
            "dialog",
          );
          await expect(surface(page, "drawer")).toHaveAttribute(
            "aria-modal",
            "true",
          );
          await expect(surface(page, "drawer")).toHaveAccessibleName(
            "Site navigation",
          );
          expect(
            (await relation(page, "drawer", evidence.observations)).expanded,
          ).toBe("true");
          for (const key of [
            ...Array(20).fill("Tab"),
            ...Array(6).fill("Shift+Tab"),
          ]) {
            await page.keyboard.press(key);
            await expect(surface(page, "drawer").locator(":focus")).toHaveCount(
              1,
            );
          }
          await page.keyboard.press("Escape");
          await expect(control(page, "drawer")).toBeFocused();
          expect(
            (await relation(page, "drawer", evidence.observations)).expanded,
          ).toBe("false");
          await expect(surface(page, "drawer")).not.toHaveAttribute(
            "aria-modal",
            "true",
          );
          await control(page, "drawer").click();
          await surface(page, "drawer")
            .locator("summary")
            .filter({ hasText: /^Platform$/ })
            .first()
            .click();
          const destination = surface(page, "drawer")
            .getByRole("link", { name: "Getting started", exact: true })
            .first();
          const href = await destination.getAttribute("href");
          const target = new URL(href, page.url());
          const section = target.pathname.match(
            /\/(platform|projects|handbook|knowledge|repository)\/start\/$/,
          )[1];
          const beforeHeading = await page
              .locator(".md-content h1")
              .textContent(),
            origin = await page.evaluate(() => performance.timeOrigin);
          await destination.click();
          await expect(page).toHaveURL(target.href);
          await expect(page.locator(".md-content h1")).toHaveText(
            new RegExp(
              `^${section[0].toUpperCase()}${section.slice(1)} getting started\\s*¶?\\s*$`,
            ),
          );
          await expect(toggle(page, "drawer")).not.toBeChecked();
          expect(
            await page.evaluate(
              (original) => original === document,
              documentIdentity,
            ),
          ).toBe(true);
          await relation(page, "drawer", evidence.observations);
          await page.goBack();
          await expect(page).toHaveURL(rootURL);
          await expect(page.locator(".md-content h1")).toHaveText(
            beforeHeading,
          );
          expect(
            await page.evaluate(
              (original) => original === document,
              documentIdentity,
            ),
          ).toBe(true);
          await relation(page, "drawer", evidence.observations);
          evidence.drawerNavigation = {
            destination: target.href,
            origin,
            back: rootURL,
          };
        } else {
          await expect(control(page, "drawer")).toBeHidden();
          await expect(surface(page, "drawer")).not.toHaveAttribute(
            "aria-modal",
            "true",
          );
        }
      }
      evidence.searchNavigation = await searchJourney(
        page,
        definition,
        evidence.observations,
        !definition.native && definition.width < 1220,
        documentIdentity,
      );
      // Reopen after actual instant Back: duplicate or stale lifetime listeners fail this intent.
      const inline =
        definition.native && (await control(page, "search").isHidden());
      if (inline) await query(page).click();
      else await control(page, "search").click();
      await expect(toggle(page, "search")).toBeChecked();
      await relation(page, "search", evidence.observations);
      await page
        .getByRole("button", { name: "Close search", exact: true })
        .click();
      await expect(toggle(page, "search")).not.toBeChecked();
      await expect(
        inline ? query(page) : control(page, "search"),
      ).toBeFocused();
      await relation(page, "search", evidence.observations);
      expect(evidence.errors).toEqual([]);
      expect(evidence.missing).toEqual([]);
      evidence.result = "pass";
    } catch (error) {
      evidence.result = "fail";
      evidence.failure = { message: error.message, stack: error.stack };
      throw error;
    } finally {
      if (documentIdentity) await documentIdentity.dispose();
      await context.close();
      evidence.closed_at = new Date().toISOString();
      fs.writeFileSync(
        info.outputPath("popup-relationships-evidence.json"),
        JSON.stringify(evidence, null, 2) + "\n",
      );
      await info.attach("popup-relationships-evidence", {
        body: Buffer.from(JSON.stringify(evidence, null, 2)),
        contentType: "application/json",
      });
    }
  });
}
