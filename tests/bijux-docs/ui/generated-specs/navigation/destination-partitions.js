"use strict";

const definitions = [
  { name: "root documents", depth: 0 },
  { name: "section destinations", depth: 1 },
  { name: "nested destinations", depth: 2 },
];

function partitionDestinations(destinations, owners = definitions) {
  const routes = destinations.map(destination => destination.route);
  if (!routes.length || new Set(routes).size !== routes.length)
    throw new Error("Authored destination routes must be nonempty and unique");
  if (new Set(owners.map(owner => owner.name)).size !== owners.length)
    throw new Error("Destination ownership names must be unique");
  const groups = owners.map(owner => ({
    ...owner,
    destinations: destinations.filter(destination => destination.ancestors.length === owner.depth),
  }));
  const claimed = groups.flatMap(group => group.destinations.map(destination => destination.route));
  if (groups.some(group => !group.destinations.length) ||
      claimed.length !== routes.length || new Set(claimed).size !== routes.length ||
      routes.some(route => !claimed.includes(route)))
    throw new Error("Destination ownership must cover the authored graph exactly once");
  if (groups.some(group => group.destinations.length > 10))
    throw new Error("Destination ownership needs finer semantic boundaries to keep journeys bounded");
  return groups;
}

module.exports = { definitions, partitionDestinations };
