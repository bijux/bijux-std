"use strict";

function assessRoute(observations, expectedURL, minimumDuration) {
  if (!Array.isArray(observations) || observations.length < 2)
    throw new Error("History stability requires repeated actual route observations");
  if (!Number.isFinite(minimumDuration) || minimumDuration <= 0)
    throw new Error("History stability requires a positive observation window");
  let previous = -Infinity;
  for (const observation of observations) {
    if (!Number.isFinite(observation.elapsed) || observation.elapsed < 0 || observation.elapsed <= previous)
      throw new Error("History observations require increasing elapsed times");
    if (observation.url !== expectedURL)
      throw new Error(`Reader history changed during restoration: ${observation.url}; expected ${expectedURL}`);
    previous = observation.elapsed;
  }
  const duration = observations.at(-1).elapsed - observations[0].elapsed;
  if (duration < minimumDuration)
    throw new Error(`History observation window was incomplete: ${duration}ms`);
  return { expectedURL, samples: observations.length, duration };
}

async function observeRoute(page, expectedURL, duration = 1500) {
  const start = performance.now(), observations = [];
  do {
    const actual = await page.evaluate(() => ({ url: location.href, scrollY }));
    observations.push({ elapsed: performance.now() - start, ...actual });
    await new Promise(resolve => setTimeout(resolve, 20));
  } while (performance.now() - start - observations[0].elapsed < duration);
  const actual = await page.evaluate(() => ({ url: location.href, scrollY }));
  observations.push({ elapsed: performance.now() - start, ...actual });
  try {
    const assessment = assessRoute(observations, expectedURL, duration);
    return { ...assessment, observations };
  } catch (error) {
    error.observations = observations;
    throw error;
  }
}

module.exports = { assessRoute, observeRoute };
