const HIT_PX = 14;

export function nearestVertex(coordinates, pixel, project, radius = HIT_PX) {
  if (!pixel || !coordinates?.length) return -1;
  let best = -1;
  let bestDistance = radius * radius;
  coordinates.forEach((point, index) => {
    const projected = project(point);
    if (!projected) return;
    const dx = projected.x - pixel.x;
    const dy = projected.y - pixel.y;
    const distance = dx * dx + dy * dy;
    if (distance <= bestDistance) {
      best = index;
      bestDistance = distance;
    }
  });
  return best;
}

export function moveVertex(coordinates, index, point) {
  return coordinates.map((pair, item) => (item === index ? [point[0], point[1]] : [pair[0], pair[1]]));
}
