"use strict";
const { test } = require("./helpers/document");
const { destinations, authoredDestinationCoverage } = require("./navigation/destinations");
const { partitionDestinations } = require("./navigation/destination-partitions");

// Each graph owner gets a bounded test while the suite retains every authored route.
for (const group of partitionDestinations(destinations)) {
  test(`authored ${group.name} retain navigation semantics and reader focus`, async ({ page }, info) => {
    await authoredDestinationCoverage(page, info, group.destinations);
  });
}
