"use strict";
const assert = require("node:assert/strict");
const test = require("node:test");
const { admitReadingResponse, hash } = require("../ui/generated-specs/drawer/destination-response.cjs");
const body = Buffer.from("<h1>Owned reading reference</h1>");
const expected = hash(body);
const url = "http://127.0.0.1:4173/reading/";
const modified = "Sun, 11 Oct 2026 16:54:56 GMT";
const representation = () => ({ url, status: 200, body, headers: { "content-type": "text/html", "last-modified": modified }, requestHeaders: {} });
const conditional = () => ({ url, status: 304, navigation: true, headers: {}, requestHeaders: { "if-modified-since": modified } });

test("actual HTML response establishes the exact owned representation and validator", () => {
  assert.deepEqual(admitReadingResponse(representation(), expected), { url, bodyHash: expected, modified, transportStatus: 200 });
});
test("conditional response retains the previously admitted exact representation", () => {
  const prior = admitReadingResponse(representation(), expected);
  assert.deepEqual(admitReadingResponse(conditional(), expected, prior), { ...prior, transportStatus: 304, validatorEvidence: "exposed-request-header" });
});
test("conditional response cannot invent a cached representation", () => {
  assert.throws(() => admitReadingResponse(conditional(), expected));
});
test("changed representation bytes and wrong content type cannot establish ownership", () => {
  assert.throws(() => admitReadingResponse({ ...representation(), body: Buffer.from("other page") }, expected));
  assert.throws(() => admitReadingResponse({ ...representation(), headers: { "content-type": "text/plain", "last-modified": modified } }, expected));
});
test("conditional URL, body and request validator must match the admitted representation", () => {
  const prior = admitReadingResponse(representation(), expected);
  for (const changed of [{ ...prior, url: url + "other" }, { ...prior, bodyHash: hash("other") }, { ...prior, modified: "Sat, 10 Oct 2026 16:54:56 GMT" }])
    assert.throws(() => admitReadingResponse(conditional(), expected, changed));
  assert.throws(() => admitReadingResponse({ ...conditional(), requestHeaders: {} }, expected, prior));
});
test("redirects, failed responses and malformed validators cannot certify a destination", () => {
  for (const status of [301, 302, 403, 404, 500]) assert.throws(() => admitReadingResponse({ ...representation(), status }, expected));
  assert.throws(() => admitReadingResponse({ ...representation(), headers: { "content-type": "text/html", "last-modified": "invalid" } }, expected));
});

test("Firefox internal cache validator remains bounded to the exact previously observed document", () => {
  const prior = admitReadingResponse(representation(), expected);
  const hidden = { ...conditional(), requestHeaders: {} };
  assert.deepEqual(admitReadingResponse(hidden, expected, prior, "firefox"),
    { ...prior, transportStatus: 304, validatorEvidence: "firefox-internal-header" });
  for (const browser of ["chromium", "webkit", undefined])
    assert.throws(() => admitReadingResponse(hidden, expected, prior, browser));
  assert.throws(() => admitReadingResponse(hidden, expected, undefined, "firefox"));
  assert.throws(() => admitReadingResponse({ ...hidden, url: url + "other" }, expected, prior, "firefox"));
  assert.throws(() => admitReadingResponse(hidden, hash("other"), prior, "firefox"));
});
test("Firefox cannot hide an exposed wrong validator or admit a non-document conditional response", () => {
  const prior = admitReadingResponse(representation(), expected);
  assert.throws(() => admitReadingResponse({ ...conditional(), requestHeaders: { "if-modified-since": "wrong" } }, expected, prior, "firefox"));
  for (const navigation of [false, undefined])
    assert.throws(() => admitReadingResponse({ ...conditional(), navigation, requestHeaders: {} }, expected, prior, "firefox"));
  assert.throws(() => admitReadingResponse({ ...conditional(), requestHeaders: {} }, expected, { ...prior, modified: "invalid" }, "firefox"));
});
