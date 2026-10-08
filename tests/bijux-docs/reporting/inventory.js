"use strict";
const fs = require("node:fs"), path = require("node:path"), cp = require("node:child_process");
function main(argv) {
  if (argv.length !== 4 || argv[0] !== "--config" || argv[2] !== "--output") throw new Error("Usage: inventory.js --config CONFIG --output ARTIFACT.json");
  if (process.env.BIJUX_UI_BROWSER_ENGINE || process.env.BIJUX_UI_PROJECTS) throw new Error("Canonical inventory must be produced before shard selection");
  const configPath = path.resolve(argv[1]), output = path.resolve(argv[3]);
  const config = require(configPath);
  const contract = config.reporter.find(entry => String(entry[0]).endsWith("strict-reporter.js"))?.[1];
  if (!contract || contract.assignedShard) throw new Error("Inventory requires a canonical strict reporter contract");
  fs.mkdirSync(path.dirname(output), { recursive: true });
  const contractPath = output + ".contract.json";
  fs.writeFileSync(contractPath, JSON.stringify(contract, null, 2) + "\n");
  const result = cp.spawnSync(process.execPath, [require.resolve("@playwright/test/cli"), "test", "--config", configPath, "--list", "--reporter", path.join(__dirname, "inventory-reporter.js")], { stdio: "inherit", env: { ...process.env, BIJUX_UI_SUITE_CONTRACT: contractPath, BIJUX_UI_INVENTORY: output } });
  if (result.error) throw result.error;
  return result.status ?? 1;
}
if (require.main === module) { try { process.exitCode = main(process.argv.slice(2)); } catch (error) { console.error(error.message); process.exitCode = 1; } }
module.exports = { main };
