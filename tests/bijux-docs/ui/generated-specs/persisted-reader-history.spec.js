"use strict";
const fs = require("node:fs");
const crypto = require("node:crypto");
const { test, expect } = require("./helpers/document");
const figures = page => page.locator(".md-content article .bijux-diagram");
const prefix = "bijux-native-cache:";
async function snapshot(page) {
  return page.evaluate(() => {
    const link = document.querySelector("#reader-native-next");
    return { href: location.href, entryKey: window.navigation?.currentEntry?.key,
      timeOrigin: performance.timeOrigin, y: scrollY, top: link?.getBoundingClientRect().top,
      sources: [...document.querySelectorAll(".md-content article .bijux-diagram-source code")].map(node => node.textContent),
      disclosures: [...document.querySelectorAll(".md-content article .bijux-diagram-source")].map(node => node.open),
    };
  });
}

test("actual cached native reader Back and Forward retain this entry and its source inspection", async ({ page, browser }, info) => {
  const origin = info.project.use.baseURL, reader = origin + "/reader-diagrams/", checkpoint = origin + "/reader-table/";
  const events = [], records = [], external = [], observed = new Set();
  page.on("request", request => { if (new URL(request.url()).origin !== origin) external.push(request.url()); });
  page.on("console", message => {
    if (!message.text().startsWith(prefix)) return;
    const event = JSON.parse(message.text().slice(prefix.length));
    const identity = JSON.stringify([event.timeOrigin, event.entryKey, event.sequence]);
    // Chromium replays console output from cached realms. A previous event must
    // never stand in for the genuinely new native lifecycle being awaited.
    if (!observed.has(identity)) { observed.add(identity); events.push(event); }
  });
  await page.addInitScript(({ prefix }) => {
    let sequence = 0;
    function observe(event) {
      const link = document.querySelector("#reader-native-next");
      console.log(prefix + JSON.stringify({ type: event.type, sequence: ++sequence, trusted: event.isTrusted,
        persisted: event.persisted, href: location.href, entryKey: window.navigation?.currentEntry?.key,
        timeOrigin: performance.timeOrigin, y: scrollY, top: link?.getBoundingClientRect().top,
        sources: [...document.querySelectorAll(".md-content article .bijux-diagram-source code")].map(node => node.textContent),
        disclosures: [...document.querySelectorAll(".md-content article .bijux-diagram-source")].map(node => node.open),
      }));
    }
    window.addEventListener("pageshow", observe);
    window.addEventListener("pagehide", observe);
    document.addEventListener("click", event => { if (event.target.closest?.("#reader-native-next")) observe(event); }, true);
  }, { prefix });
  const protocol = await browser.newBrowserCDPSession();
  const runtime = { version: await protocol.send("Browser.getVersion"),
    commandLine: await protocol.send("Browser.getBrowserCommandLine") };
  await protocol.detach();
  const executable = runtime.commandLine.arguments[0];
  expect(executable).toBeTruthy(); expect(executable).not.toMatch(/headless[_-]shell/i);
  expect(runtime.commandLine.arguments).not.toContain("--disable-back-forward-cache");
  runtime.executableSha256 = crypto.createHash("sha256").update(fs.readFileSync(executable)).digest("hex");
  info.annotations.push({ type: "persisted-browser-runtime", description: JSON.stringify(runtime) });
  try {
    await page.goto(reader);
    await expect(figures(page).locator(".bijux-diagram-preview > svg")).toHaveCount(5);
    await expect(figures(page).locator("details[open]")).toHaveCount(0);
    const initial = await snapshot(page);
    expect(initial.entryKey).toBeTruthy();
    await figures(page).first().locator("summary").click();
    await expect(figures(page).locator("details[open]")).toHaveCount(1);
    const link = page.locator("#reader-native-next");
    await expect(link).toHaveAttribute("target", "_self");
    await link.click();
    await expect(page).toHaveURL(checkpoint);
    const departure = events.find(event => event.type === "click" && event.href === reader);
    expect(departure?.trusted).toBe(true);
    expect(departure.disclosures).toEqual([true, false, false, false, false]);
    expect(departure.sources).toEqual(initial.sources);
    const target = await snapshot(page);
    target.sequence = events.find(event => event.type === "pageshow" && event.href === checkpoint && !event.persisted)?.sequence;
    let readerSequence = departure.sequence, targetSequence = target.sequence;
    records.push({ label: "native departure", departure, target });
    for (let cycle = 0; cycle < 2; cycle++) {
      const start = events.length;
      await page.goBack({ waitUntil: "commit", timeout: 5000 });
      await expect.poll(() => events.slice(start).some(event => event.type === "pageshow" && event.href === reader && event.trusted && event.persisted), { timeout: 5000 }).toBe(true);
      await expect(figures(page).locator(".bijux-diagram-preview > svg")).toHaveCount(5);
      await expect.poll(async () => (await snapshot(page)).disclosures, { timeout: 5000 }).toEqual(departure.disclosures);
      await expect.poll(async () => Math.abs((await snapshot(page)).top - departure.top), { timeout: 5000 }).toBeLessThan(1);
      const returned = await snapshot(page);
      expect(returned.href).toBe(reader); expect(returned.entryKey).toBe(departure.entryKey);
      expect(returned.timeOrigin).toBe(initial.timeOrigin); expect(returned.sources).toEqual(initial.sources);
      const back = events.slice(start).find(event => event.type === "pageshow" && event.href === reader && event.trusted && event.persisted);
      expect(back.sequence).toBeGreaterThan(readerSequence);
      readerSequence = back.sequence;
      const next = events.length;
      await page.goForward({ waitUntil: "commit", timeout: 5000 });
      await expect.poll(() => events.slice(next).some(event => event.type === "pageshow" && event.href === checkpoint && event.trusted && event.persisted), { timeout: 5000 }).toBe(true);
      const forward = await snapshot(page);
      expect(forward.href).toBe(checkpoint); expect(forward.entryKey).toBe(target.entryKey); expect(forward.timeOrigin).toBe(target.timeOrigin);
      const shown = events.slice(next).find(event => event.type === "pageshow" && event.href === checkpoint && event.trusted && event.persisted);
      expect(shown.sequence).toBeGreaterThan(targetSequence);
      targetSequence = shown.sequence;
      records.push({ label: "cached native cycle", cycle, back, returned, shown, forward,
        absoluteOffset: Math.abs(returned.top - departure.top) });
    }
    expect(external).toEqual([]);
    info.annotations.push({ type: "persisted-native-journey", description: JSON.stringify({ departure, initial, target, records, external }) });
  } finally {
    await info.attach("persisted-native-reader-observations", { body: Buffer.from(JSON.stringify({ runtime, events, records, external }, null, 2)), contentType: "application/json" });
  }
});
