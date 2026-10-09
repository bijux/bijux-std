const fs = require("node:fs"),
  path = require("node:path"),
  crypto = require("node:crypto");
const { test, expect } = require("@playwright/test");
const root = path.resolve(
  process.env.BIJUX_GENERATED_ROOT ||
    path.join(__dirname, "../../../../artifacts/bijux-docs/generated"),
);
const fixture = JSON.parse(fs.readFileSync(path.join(root, "manifest.json")));
const hash = (text) => crypto.createHash("sha256").update(text).digest("hex");
const region = (page, kind) =>
  page.getByRole("region", {
    name: kind === "code" ? /^Scrollable code example / : /^Scrollable table /,
  });
const surface = (page, kind) =>
  page.locator(
    kind === "code" ? "article .highlight" : "article .md-typeset__scrollwrap",
  );
const route = (kind, profile) =>
  `${profile === "rtl" ? "/fixtures/rtl" : ""}/reader-${kind}/`;

async function content(page) {
  return page.locator("article").evaluate((article) => ({
    code: [...article.querySelectorAll(".highlight td.code pre > code")].map(
      (node) => ({
        text: node.textContent,
        anchors: [...node.querySelectorAll("[id]")].map((anchor) => anchor.id),
      }),
    ),
    tables: [...article.querySelectorAll("table:not(.highlighttable)")].map(
      (table) =>
        [...table.rows].map((row) =>
          [...row.cells].map((cell) => ({
            tag: cell.tagName,
            text: cell.textContent.trim(),
            colSpan: cell.colSpan,
            rowSpan: cell.rowSpan,
          })),
        ),
    ),
    lineLinks: [...article.querySelectorAll("a[href*='#__codelineno']")].map(
      (anchor) => {
        const destination = new URL(anchor.href);
        return {
          fragment: destination.hash,
          url: destination.href,
          sameDocument:
            destination.origin === location.origin &&
            destination.pathname === location.pathname,
          resolves: !!document.getElementById(
            decodeURIComponent(destination.hash.slice(1)),
          ),
        };
      },
    ),
  }));
}

async function sourceOracle(page, kind) {
  const observed = await content(page);
  if (kind === "code") {
    expect(observed.code).toHaveLength(1);
    expect(observed.code[0].text).toBe(fixture.reader_fixture.code);
    expect(hash(observed.code[0].text)).toBe(
      fixture.reader_fixture.code_sha256,
    );
    expect(observed.lineLinks).toHaveLength(3);
    expect(
      observed.lineLinks.every((link) => link.resolves && link.sameDocument),
    ).toBe(true);
  } else {
    expect(observed.tables).toHaveLength(1);
    expect(
      observed.tables[0].map((row) => row.map((cell) => cell.text)),
    ).toEqual([
      fixture.reader_fixture.table_headers,
      ...fixture.reader_fixture.table_rows,
    ]);
    expect(observed.tables[0][0].every((cell) => cell.tag === "TH")).toBe(true);
    expect(
      observed.tables[0]
        .slice(1)
        .flat()
        .every(
          (cell) =>
            cell.tag === "TD" && cell.colSpan === 1 && cell.rowSpan === 1,
        ),
    ).toBe(true);
  }
  return observed;
}

async function geometry(page) {
  const measured = await page.evaluate(() => ({
    width: innerWidth,
    document: document.documentElement.scrollWidth,
    prose: [
      ...document.querySelectorAll("article > p, article > h1, article > h2"),
    ]
      .map((node) => {
        const range = document.createRange();
        range.selectNodeContents(node);
        return [...range.getClientRects()].map((box) => ({
          left: box.left,
          right: box.right,
        }));
      })
      .flat(),
  }));
  expect(measured.document).toBeLessThanOrEqual(measured.width + 1);
  expect(
    measured.prose.every(
      (box) => box.left >= -1 && box.right <= measured.width + 1,
    ),
  ).toBe(true);
  return measured;
}

async function ordinaryKeyboard(page, kind) {
  const target = region(page, kind);
  await expect(target).toHaveCount(1);
  await expect(target).toHaveAccessibleName(
    kind === "code"
      ? "Scrollable code example 1: Boundary example"
      : "Scrollable table 1: Checkpoint matrix",
  );
  await expect(target).toHaveAttribute("tabindex", "0");
  await expect
    .poll(() => target.evaluate((node) => node.scrollWidth - node.clientWidth))
    .toBeGreaterThan(1);
  let tabs = 0;
  while (
    !(await target.evaluate((node) => node === document.activeElement)) &&
    tabs < 256
  ) {
    await page.keyboard.press("Tab");
    tabs++;
  }
  await expect(target).toBeFocused();
  const initial = await target.evaluate((node) => ({
    left: node.scrollLeft,
    max: node.scrollWidth - node.clientWidth,
    direction: getComputedStyle(node).direction,
    focusVisible: node.matches(":focus-visible"),
    outline: getComputedStyle(node).outlineStyle,
    outlineWidth: parseFloat(getComputedStyle(node).outlineWidth),
    label: node.getAttribute("aria-label"),
  }));
  expect(initial.focusVisible).toBe(true);
  expect(initial.outline).not.toBe("none");
  expect(initial.outlineWidth).toBeGreaterThanOrEqual(1);
  await page.keyboard.press(
    initial.direction === "rtl" ? "ArrowLeft" : "ArrowRight",
  );
  await expect
    .poll(() => target.evaluate((node) => Math.abs(node.scrollLeft)))
    .toBeGreaterThan(0);
  await page.keyboard.press("End");
  await expect
    .poll(() =>
      target.evaluate(
        (node) =>
          Math.abs(node.scrollLeft) >= node.scrollWidth - node.clientWidth - 1,
      ),
    )
    .toBe(true);
  const last = await target.evaluate((node) => ({
    left: node.scrollLeft,
    max: node.scrollWidth - node.clientWidth,
  }));
  const endContent = await target.evaluate((node, kind) => {
    const content =
      kind === "code"
        ? node.closest(".highlight").querySelector("td.code pre > code")
        : node.querySelector("tbody tr:first-child td:last-child");
    const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
    const needle = kind === "code" ? 'input"' : "TARGET_FINAL_COLUMN";
    let text;
    let range;
    while ((text = walker.nextNode())) {
      const offset = text.textContent.indexOf(needle);
      if (offset >= 0) {
        range = document.createRange();
        range.setStart(text, offset);
        range.setEnd(text, offset + needle.length);
        break;
      }
    }
    if (!range) return { found: false, needle };
    const box = range.getBoundingClientRect();
    const owner = node.getBoundingClientRect();
    const left = Math.max(owner.left, 0);
    const right = Math.min(owner.right, innerWidth);
    const centerX = (box.left + box.right) / 2;
    const centerY = (box.top + box.bottom) / 2;
    const hit = document.elementFromPoint(centerX, centerY);
    return {
      found: true,
      needle,
      left: box.left,
      right: box.right,
      ownerLeft: left,
      ownerRight: right,
      visible: box.width > 0 && box.left >= left - 1 && box.right <= right + 1,
      hittable:
        !!hit &&
        (content === hit || content.contains(hit) || hit.contains(content)),
    };
  }, kind);
  expect(endContent.found).toBe(true);
  expect(endContent.visible).toBe(true);
  expect(endContent.hittable).toBe(true);
  await page.keyboard.press("Home");
  await expect
    .poll(() => target.evaluate((node) => Math.abs(node.scrollLeft) <= 1))
    .toBe(true);
  return { tabs, initial, last, endContent };
}

for (const profile of [
  "phone",
  "text-spacing",
  "rtl",
  "no-js",
  "desktop",
  "lifetime",
]) {
  for (const kind of ["code", "table"]) {
    test(`${profile} ${kind} preserves source and local reader access`, async ({
      browser,
    }, info) => {
      info.annotations.push({
        type: "browser-version",
        description: browser.version(),
      });
      const context = await browser.newContext({
        viewport: { width: profile === "desktop" ? 1920 : 320, height: 900 },
        javaScriptEnabled: profile !== "no-js",
      });
      const page = await context.newPage(),
        errors = [],
        missing = [];
      let documentIdentity;
      const evidence = {
        profile,
        kind,
        browser: info.project.use.browserName,
        version: browser.version(),
        manifest_sha256: hash(
          fs.readFileSync(path.join(root, "manifest.json")),
        ),
        started_at: new Date().toISOString(),
      };
      page.on("pageerror", (error) =>
        errors.push({
          name: error.name,
          message: error.message,
          stack: error.stack,
        }),
      );
      page.on("response", (response) => {
        if (
          new URL(response.url()).origin === info.project.use.baseURL &&
          response.status() >= 400
        )
          missing.push({ url: response.url(), status: response.status() });
      });
      try {
        await page.goto(info.project.use.baseURL + route(kind, profile));
        await expect(page.locator("article h1")).toHaveText(
          kind === "code"
            ? /^Code boundary reference/
            : /^Table boundary reference/,
        );
        if (profile !== "no-js")
          await expect(page.locator("body")).toHaveAttribute(
            "data-bijux-drawer-ready",
            "true",
          );
        const before = await sourceOracle(page, kind);
        evidence.source_before = before;
        if (profile === "text-spacing") {
          const size = await page.evaluate(() =>
            parseFloat(getComputedStyle(document.documentElement).fontSize),
          );
          const declaration = `html{font-size:${size * 2}px!important} article{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important} article p{margin-block-end:2em!important}`;
          await page.addStyleTag({ content: declaration });
          evidence.text_override = {
            source_root_px: size,
            declaration,
            kind: "controlled doubled text and spacing, not physical browser zoom",
          };
        }
        if (profile === "rtl")
          await expect(page.locator("body")).toHaveAttribute("dir", "rtl");
        evidence.geometry = await geometry(page);
        if (profile === "desktop") {
          await expect
            .poll(() =>
              surface(page, kind).evaluate(
                (node) => node.scrollWidth <= node.clientWidth + 1,
              ),
            )
            .toBe(true);
          await expect(surface(page, kind)).not.toHaveAttribute(
            "tabindex",
            "0",
          );
          expect(await region(page, kind).count()).toBe(0);
        } else if (profile === "no-js") {
          expect(await region(page, kind).count()).toBe(0);
          expect(await page.locator(".bijux-content-scroll-hint").count()).toBe(
            0,
          );
          if (kind === "table")
            expect(
              await page
                .locator("article th, article td")
                .evaluateAll((cells) =>
                  cells.every(
                    (cell) => cell.scrollWidth <= cell.clientWidth + 1,
                  ),
                ),
            ).toBe(true);
          evidence.no_script_scope =
            "Readable geometry and source/cell preservation; enhanced named keyboard path is unavailable";
        } else {
          evidence.keyboard = await ordinaryKeyboard(page, kind);
        }
        evidence.source_after = await sourceOracle(page, kind);
        expect(evidence.source_after).toEqual(before);
        if (profile === "lifetime") {
          documentIdentity = await page.evaluateHandle(() => document);
          const target = region(page, kind),
            old = await target.elementHandle(),
            timeOrigin = await page.evaluate(() => performance.timeOrigin);
          const other = kind === "code" ? "table" : "code";
          await page
            .locator(
              kind === "code"
                ? "a.md-footer__link--next"
                : "a.md-footer__link--prev",
            )
            .click();
          await expect(page).toHaveURL(
            (url) =>
              url.origin === info.project.use.baseURL &&
              url.pathname === route(other, "phone"),
          );
          await expect(page.locator("article h1")).toHaveText(
            other === "code"
              ? /^Code boundary reference/
              : /^Table boundary reference/,
          );
          expect(await page.evaluate(original => original === document, documentIdentity)).toBe(true);
          const disposed = await old.evaluate((node) => ({
            connected: node.isConnected,
            tabindex: node.getAttribute("tabindex"),
            role: node.getAttribute("role"),
            label: node.getAttribute("aria-label"),
            describedBy: node.getAttribute("aria-describedby"),
          }));
          expect(disposed).toEqual({
            connected: false,
            tabindex: null,
            role: null,
            label: null,
            describedBy: null,
          });
          await page.goBack();
          await expect(page).toHaveURL(
            (url) =>
              url.origin === info.project.use.baseURL &&
              url.pathname === route(kind, "phone"),
          );
          await expect(page.locator("article h1")).toHaveText(
            kind === "code"
              ? /^Code boundary reference/
              : /^Table boundary reference/,
          );
          expect(await page.evaluate(original => original === document, documentIdentity)).toBe(true);
          expect(await sourceOracle(page, kind)).toEqual(before);
          evidence.remounted_keyboard = await ordinaryKeyboard(page, kind);
          evidence.geometry_after_back = await geometry(page);
          evidence.lifetime = {
            timeOrigin,
            disposed,
            retained_document: true,
            kind: "ordinary footer destination and browser Back, genuine retained document",
          };
        }
        expect(errors).toEqual([]);
        expect(missing).toEqual([]);
        evidence.status = "passed";
      } catch (error) {
        evidence.status = "failed";
        evidence.failure = { message: error.message, stack: error.stack };
        throw error;
      } finally {
        evidence.page_errors = errors;
        evidence.missing_local_assets = missing;
        evidence.reader_surfaces = await page
          .locator(
            "article .highlight, article .highlight pre, article .highlight pre > code, article .highlighttable, article td.code",
          )
          .evaluateAll((nodes) =>
            nodes.map((node) => ({
              tag: node.tagName,
              className: node.className,
              client: node.clientWidth,
              scroll: node.scrollWidth,
              overflow: getComputedStyle(node).overflowX,
              direction: getComputedStyle(node).direction,
              tabindex: node.getAttribute("tabindex"),
              role: node.getAttribute("role"),
            })),
          );
        if (documentIdentity) await documentIdentity.dispose();
        await context.close();
        evidence.closed_at = new Date().toISOString();
        await info.attach("reader-source-and-lifetime", {
          body: Buffer.from(JSON.stringify(evidence, null, 2)),
          contentType: "application/json",
        });
        fs.writeFileSync(
          info.outputPath("reader-evidence.json"),
          JSON.stringify(evidence, null, 2) + "\n",
        );
      }
    });
  }
}
