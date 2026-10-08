const test = require("node:test"), assert = require("node:assert/strict");
const { assessRoute, observeRoute } = require("../ui/generated-specs/history/observations");
const expected = "https://bijux.example/reader/";
const rows = urls => urls.map((url, index) => ({ elapsed: index * 750, url }));
test("history proof accepts the complete observed route window", () => {
  assert.deepEqual(assessRoute(rows([expected, expected, expected]), expected, 1500), { expectedURL: expected, samples: 3, duration: 1500 });
});
test("history proof rejects fragment resurrection even if the final route recovers", () => {
  assert.throws(() => assessRoute(rows([expected, expected + "#heading", expected]), expected, 1500), /changed during restoration/);
});
test("history proof rejects a wrong document destination", () => {
  assert.throws(() => assessRoute(rows([expected, "https://bijux.example/other/", expected]), expected, 1500), /changed during restoration/);
});
test("history proof rejects missing or single observations", () => {
  for (const observations of [[], rows([expected]), null]) assert.throws(() => assessRoute(observations, expected, 1500), /repeated actual/);
});
test("history proof rejects short observation coverage", () => {
  assert.throws(() => assessRoute(rows([expected, expected]), expected, 1500), /incomplete/);
});
test("history proof rejects an omitted start interval", () => {
  assert.throws(() => assessRoute([{elapsed: 1400,url:expected},{elapsed:1500,url:expected}], expected, 1500), /incomplete/);
});
test("history proof rejects duplicate or invalid elapsed times", () => {
  for (const elapsed of [0, -1, NaN]) assert.throws(() => assessRoute([{elapsed:0,url:expected},{elapsed,url:expected}], expected, 1500), /increasing/);
});
test("history proof rejects a missing positive stability contract", () => {
  for (const duration of [0, -1, NaN]) assert.throws(() => assessRoute(rows([expected,expected,expected]), expected, duration), /positive/);
});

test("history observation window includes a delayed first actual read", async () => {
  let reads = 0;
  const page = { evaluate: async () => {
    if (!reads++) await new Promise(resolve => setTimeout(resolve, 30));
    return { url: expected, scrollY: 0 };
  } };
  const observed = await observeRoute(page, expected, 40);
  assert(observed.duration >= 40);
  assert(observed.observations[0].elapsed >= 25);
});

test("failed history sampling retains the actual wrong-route observations", async () => {
  const page = { evaluate: async () => ({ url: expected + "#unexpected", scrollY: 0 }) };
  await assert.rejects(observeRoute(page, expected, 20), error => {
    assert.match(error.message, /changed during restoration/);
    assert(error.observations.length >= 2);
    assert(error.observations.every(observation => observation.url === expected + "#unexpected"));
    return true;
  });
});
