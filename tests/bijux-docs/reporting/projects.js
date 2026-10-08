"use strict";
const originals = new WeakMap();
function unsharded(config) { return originals.get(config) || config; }
function configureProjects(config, env = process.env) {
  const canonical = unsharded(config), projects = canonical.projects;
  const engine = env.BIJUX_UI_BROWSER_ENGINE, names = env.BIJUX_UI_PROJECTS;
  if ((Object.hasOwn(env, "BIJUX_UI_BROWSER_ENGINE") && !engine) || (Object.hasOwn(env, "BIJUX_UI_PROJECTS") && !names)) throw new Error("Explicit project selection must not be empty");
  if (engine && names) throw new Error("Choose browser engine or exact projects, not both");
  if (engine && !["chromium", "firefox", "webkit"].includes(engine)) throw new Error("Unknown browser engine");
  const requested = names?.split(",").map(name => name.trim());
  if (requested && (requested.some(name => !name) || new Set(requested).size !== requested.length || requested.some(name => !projects.some(project => project.name === name)))) throw new Error("Unknown, empty or duplicate project selection");
  const selected = projects.filter(project => engine ? project.use.browserName === engine : requested ? requested.includes(project.name) : true);
  if (!selected.length) throw new Error("Project selection must execute cases");
  const shard = Boolean(engine || names);
  const junit = config.reporter.find(entry => Array.isArray(entry) && entry[0] === "junit")?.[1]?.outputFile;
  const result = { ...config, projects: selected, reporter: config.reporter.map(entry => Array.isArray(entry) && String(entry[0]).endsWith("strict-reporter.js") ? [entry[0], { ...entry[1],
    canonicalProjects: projects.map(project => ({ name: project.name, engine: project.use.browserName, count: project.metadata?.required_case_count })),
    requiredProjects: selected.map(project => project.name), assignedShard: shard, junitFile: junit,
  }] : entry) };
  originals.set(result, canonical);
  return result;
}
module.exports = { configureProjects, unsharded };
