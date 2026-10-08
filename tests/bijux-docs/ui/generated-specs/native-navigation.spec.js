const fs = require("node:fs"), path = require("node:path");
const { test, expect } = require("@playwright/test");
const qualify = require("./native-navigation/qualification");
const root = path.resolve(process.env.BIJUX_GENERATED_ROOT || path.join(__dirname, "../../../../artifacts/bijux-docs/generated"));
const definitions = [
  { kind: "no-js-native", route: "/", width: 320 },
  { kind: "no-js-native", route: "/bijux-core/platform/details/leaf/", width: 768 },
  ...[320, 768, 1220].map(width => ({ kind: "js-preservation", route: "/", width })),
  { kind: "no-js-resize", route: "/", width: 767 },
  { kind: "no-js-pointer", route: "/", width: 320 },
  { kind: "no-js-desktop", route: "/", width: 1220 },
  { kind: "no-js-rtl", route: "/fixtures/rtl/", width: 320 },
  ...["delayed-native", "throw-before-native", "throw-mounted-native"].map(kind => ({ kind, route: "/", width: 320 })),
];
for (const definition of definitions) {
  test(`${definition.kind} at ${definition.width}px on ${definition.route}`, async ({ browser, browserName }, info) => {
    info.annotations.push({ type: "browser-version", description: browser.version() });
    const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json")));
    await qualify(browser, browserName, definition, info, expect, manifest);
  });
}
