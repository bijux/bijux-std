"use strict";

function rgba(value) {
  const values = value.match(/[\d.]+/g)?.map(Number);
  if (!/^rgba?\(/.test(value) || !values || values.length < 3) {
    throw new Error(`Unsupported computed color: ${value}`);
  }
  return [...values.slice(0, 3), values[3] ?? 1];
}
function composite(foreground, background, opacity = 1) {
  const alpha = foreground[3] * opacity;
  return foreground.slice(0, 3).map((channel, index) =>
    channel * alpha + background[index] * (1 - alpha));
}
function luminance(color) {
  return color.slice(0, 3).map(channel => {
    const normalized = channel / 255;
    return normalized <= 0.04045 ? normalized / 12.92 :
      ((normalized + 0.055) / 1.055) ** 2.4;
  }).reduce((sum, channel, index) => sum + channel * [0.2126, 0.7152, 0.0722][index], 0);
}
function contrast(foreground, background) {
  const values = [luminance(foreground), luminance(background)].sort((a, b) => a - b);
  return (values[1] + 0.05) / (values[0] + 0.05);
}
function textThreshold(size, weight) {
  return size >= 24 || (size >= 56 / 3 && weight >= 700) ? 3 : 4.5;
}
module.exports = { rgba, composite, luminance, contrast, textThreshold };
