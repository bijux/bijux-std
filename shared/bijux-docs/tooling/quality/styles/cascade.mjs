/* Guard owned declaration exceptions; rendered cascade behavior has separate owners. */
import { createHash } from "node:crypto";
import { readFile, realpath, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { parseArgs } from "node:util";

const documentation = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const repository = path.resolve(documentation, "../..");
const digest = (bytes) => createHash("sha256").update(bytes).digest("hex");
const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
const strings = (value) => Array.isArray(value) && value.every((entry) => typeof entry === "string" && entry.length);
const identity = (entry) => JSON.stringify([entry.file, entry.conditions, entry.selectors, entry.property]);
const importantIdentity = (entry) => JSON.stringify([identity(entry), entry.value]);
const duplicateIdentity = (entry) => JSON.stringify([identity(entry), entry.values]);

async function regular(filename) {
  if (await realpath(filename) !== path.resolve(filename) || !(await stat(filename)).isFile()) {
    throw new Error(`${filename}: expected an owned regular file without linked path components`);
  }
  return readFile(filename);
}

async function parser(dependencies) {
  const source = path.join(documentation, "tooling/diagrams");
  for (const name of ["package.json", "package-lock.json"]) {
    const [expected, installed] = await Promise.all([regular(path.join(source, name)), regular(path.join(dependencies, name))]);
    if (!expected.equals(installed)) throw new Error(`${dependencies}/${name}: installed diagram manifest differs`);
  }
  const provenance = JSON.parse(await regular(path.join(source, "provenance.json")));
  const lock = JSON.parse(await regular(path.join(source, "package-lock.json")));
  const owned = provenance.bundled_packages.find((entry) => entry.name === "stylis");
  const pinned = lock.packages["node_modules/stylis"];
  if (!owned || owned.version !== pinned.version || owned.integrity !== pinned.integrity || owned.resolved !== pinned.resolved) {
    throw new Error("Stylis parser provenance differs from the exact diagram lock");
  }
  const installed = JSON.parse(await regular(path.join(dependencies, "node_modules/stylis/package.json")));
  if (installed.name !== "stylis" || installed.version !== pinned.version || installed.type !== "module") {
    throw new Error("Installed Stylis parser identity differs from the admitted module");
  }
  const files = provenance.bundled_inputs.filter((entry) => entry.path.startsWith("node_modules/stylis/"));
  if (!files.some((entry) => entry.path === "node_modules/stylis/index.js") || !files.some((entry) => entry.path === "node_modules/stylis/src/Parser.js")) {
    throw new Error("Stylis parser source provenance is incomplete");
  }
  for (const entry of files) {
    const bytes = await regular(path.join(dependencies, entry.path));
    if (bytes.length !== entry.bytes || digest(bytes) !== entry.sha256) throw new Error(`${entry.path}: changed admitted parser source`);
  }
  return { module: await import(pathToFileURL(path.join(dependencies, "node_modules/stylis/index.js"))), version: owned.version, files };
}

function policyRecords(policy) {
  if (!object(policy) || policy.schema !== 1 || Object.keys(policy).sort().join() !== "duplicate_fallbacks,important_exceptions,schema,styles") {
    throw new Error("Cascade policy: unknown or missing fields/schema");
  }
  if (!strings(policy.styles) || new Set(policy.styles).size !== policy.styles.length || policy.styles.some((name) => !/^\d\d-[a-z-]+\.css$/.test(name))) {
    throw new Error("Cascade policy: styles must be unique owned stylesheet names in import order");
  }
  for (const [field, valueField] of [["important_exceptions", "value"], ["duplicate_fallbacks", "values"]]) {
    if (!Array.isArray(policy[field])) throw new Error(`Cascade policy: ${field} must be a list`);
    const seen = new Set();
    for (const record of policy[field]) {
      const expected = ["file", "conditions", "selectors", "property", valueField, "owner", "reason", ...(field === "important_exceptions" ? ["necessity"] : [])];
      if (!object(record) || Object.keys(record).sort().join() !== expected.sort().join() || !policy.styles.includes(record.file) ||
          !strings(record.selectors) || !Array.isArray(record.conditions) || !record.conditions.every((entry) => typeof entry === "string" && entry.startsWith("@")) ||
          typeof record.property !== "string" || !record.property || record.owner !== "bijux-std" || typeof record.reason !== "string" || !record.reason.trim() ||
          (valueField === "value" ? typeof record.value !== "string" || !record.value || typeof record.necessity !== "string" || !record.necessity : !strings(record.values) || record.values.length !== 2)) {
        throw new Error(`Cascade policy: malformed ${field} record`);
      }
      const key = valueField === "value" ? importantIdentity(record) : duplicateIdentity(record);
      if (seen.has(key)) throw new Error(`Cascade policy: duplicate ${field} identity`);
      seen.add(key);
    }
  }
}

export async function qualify({ styles, policy: policyPath, dependencies }) {
  const policy = JSON.parse(await regular(policyPath));
  policyRecords(policy);
  const admitted = await parser(dependencies);
  const { compile, tokenize } = admitted.module;
  const decode = (value) => value.replace(/\\([0-9a-f]{1,6})(?:[ \t\r\n\f])?|\\([^\r\n\f])/gi, (_, hex, character) => {
    if (character) return character;
    const point = Number.parseInt(hex, 16);
    return !point || point > 0x10ffff || point >= 0xd800 && point <= 0xdfff ? "\uFFFD" : String.fromCodePoint(point);
  });
  const property = (value) => {
    const decoded = decode(value);
    return decoded.startsWith("--") ? decoded : decoded.toLowerCase();
  };
  const priority = (value) => {
    const tokens = tokenize(value).filter((token) => token.trim());
    return tokens.at(-2) === "!" && decode(tokens.at(-1) || "").toLowerCase() === "important";
  };
  const imports = compile((await regular(path.join(styles, "extra.css"))).toString());
  const names = [];
  for (const node of imports) {
    if (node.type === "comm") continue;
    const match = node.type === "@import" && /^@import url\("\.\/([a-z0-9-]+\.css)"\);$/.exec(node.value);
    if (!match) throw new Error(`extra.css:${node.line}:${node.column}: expected only canonical local stylesheet imports`);
    names.push(match[1]);
  }
  if (JSON.stringify(names) !== JSON.stringify(policy.styles)) throw new Error("extra.css: stylesheet import order differs from cascade policy");
  const declarations = [], duplicates = [], sourceFiles = {};
  function walk(nodes, file, conditions = [], selectors = []) {
    for (const node of nodes) {
      if (node.type === "decl") {
        declarations.push({ file, conditions, selectors, property: property(node.props), value: node.children, important: priority(node.children), line: node.line, column: node.column });
      } else if (Array.isArray(node.children)) {
        const nextConditions = node.type.startsWith("@") ? [...conditions, node.value] : conditions;
        const nextSelectors = node.type === "rule" ? node.props : selectors;
        if (node.type === "rule") {
          const seen = new Map();
          for (const declaration of node.children.filter((child) => child.type === "decl")) {
            const name = property(declaration.props), previous = seen.get(name);
            if (previous) duplicates.push({ file, conditions: nextConditions, selectors: nextSelectors, property: name, values: [previous.children, declaration.children], line: declaration.line, column: declaration.column, earlier_line: previous.line });
            seen.set(name, declaration);
          }
        }
        walk(node.children, file, nextConditions, nextSelectors);
      }
    }
  }
  for (const file of names) {
    const bytes = await regular(path.join(styles, file));
    sourceFiles[file] = digest(bytes);
    walk(compile(bytes.toString()), file);
  }
  const errors = [], diagnostics = [], usedImportant = new Set(), usedDuplicates = new Set();
  const important = new Map(policy.important_exceptions.map((record) => [importantIdentity(record), record]));
  const fallback = new Map(policy.duplicate_fallbacks.map((record) => [duplicateIdentity(record), record]));
  for (const declaration of declarations.filter((entry) => entry.important)) {
    const key = importantIdentity(declaration), exception = important.get(key);
    if (!exception) errors.push({ kind: "unreviewed_important", ...declaration });
    else if (usedImportant.has(key)) errors.push({ kind: "repeated_important_exception", ...declaration });
    else { usedImportant.add(key); diagnostics.push({ kind: "important_exception", ...declaration, reason: exception.reason, necessity: exception.necessity }); }
  }
  for (const duplicate of duplicates) {
    const key = duplicateIdentity(duplicate), exception = fallback.get(key);
    if (!exception) errors.push({ kind: "unintended_duplicate", ...duplicate });
    else if (usedDuplicates.has(key)) errors.push({ kind: "repeated_duplicate_fallback", ...duplicate });
    else { usedDuplicates.add(key); diagnostics.push({ kind: "viewport_fallback", ...duplicate, reason: exception.reason }); }
  }
  for (const [key, record] of important) if (!usedImportant.has(key)) errors.push({ kind: "stale_important_exception", ...record });
  for (const [key, record] of fallback) if (!usedDuplicates.has(key)) errors.push({ kind: "stale_duplicate_fallback", ...record });
  const hidden = declarations.filter((entry) => entry.file === "07-utilities.css" && !entry.conditions.length && JSON.stringify(entry.selectors) === JSON.stringify(['[hidden]:not([hidden="until-found"])']) && entry.property === "display");
  if (hidden.length !== 1 || hidden[0].value !== "none!important" || !hidden[0].important) errors.push({ kind: "semantic_hidden_invariant", file: "07-utilities.css", property: "display", expected: 'one unconditional [hidden]:not([hidden="until-found"]) display:none!important' });
  return { status: errors.length ? "failed" : "passed", source_files: sourceFiles, styles: names.length, declarations: declarations.length,
    important_declarations: declarations.filter((entry) => entry.important).length, duplicate_fallbacks: duplicates.length, parser: { name: "stylis", version: admitted.version, files: admitted.files }, errors, diagnostics,
    limits: ["Owned declaration policy only; no complete CSS validity, cross-rule selector competition or computed specificity proof", "Parser lines/columns are source end locations", "Existing integration necessity flags remain honest; computed order, token scopes, themes, responsive modes and manual/live qualification remain separate"] };
}

if (path.resolve(process.argv[1] || "") === fileURLToPath(import.meta.url)) {
  try {
    const { values } = parseArgs({ options: { "styles-dir": { type: "string", default: path.join(documentation, "styles") }, policy: { type: "string", default: path.join(documentation, "config/cascade-contract.json") }, dependencies: { type: "string", default: process.env.BIJUX_DIAGRAM_DEPENDENCIES || path.join(repository, "artifacts/website-security/dependencies/build") } } });
    const result = await qualify({ styles: path.resolve(values["styles-dir"]), policy: path.resolve(values.policy), dependencies: path.resolve(values.dependencies) });
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    if (result.errors.length) process.exitCode = 1;
  } catch (error) {
    process.stderr.write(`ERROR: ${error.message}\nPrepare the existing pinned runtime with make -f shared/bijux-docs/tooling/diagrams/Makefile diagrams-install; a read-only qualified build may be selected with BIJUX_DIAGRAM_DEPENDENCIES.\n`);
    process.exitCode = 1;
  }
}
