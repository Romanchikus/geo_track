const MIN_PX = 6;
const MAX_POINTS = 256;

export function startStroke(point, pixel) {
  return {
    moved: false,
    points: [[point[0], point[1]]],
    pixels: [{ x: pixel.x, y: pixel.y }],
  };
}

export function pushStroke(stroke, point, pixel) {
  const last = stroke.pixels[stroke.pixels.length - 1];
  const dx = pixel.x - last.x;
  const dy = pixel.y - last.y;
  if (dx * dx + dy * dy < MIN_PX * MIN_PX) return;
  stroke.moved = true;
  stroke.points.push([point[0], point[1]]);
  stroke.pixels.push({ x: pixel.x, y: pixel.y });
}

export function strokeRing(stroke) {
  if (!stroke?.moved || stroke.points.length < 3) return null;
  const ring = simplifyStroke(stroke.points);
  return ring.length >= 3 ? ring : null;
}

export function simplifyStroke(points, limit = MAX_POINTS) {
  const unique = [];
  for (const point of points) {
    const pair = [point[0], point[1]];
    const last = unique[unique.length - 1];
    if (last && last[0] === pair[0] && last[1] === pair[1]) continue;
    unique.push(pair);
  }
  if (unique.length <= limit) return unique;
  const sampled = [];
  const step = (unique.length - 1) / (limit - 1);
  for (let index = 0; index < limit; index += 1) {
    const point = unique[Math.round(index * step)];
    const last = sampled[sampled.length - 1];
    if (last && last[0] === point[0] && last[1] === point[1]) continue;
    sampled.push(point);
  }
  return sampled;
}
