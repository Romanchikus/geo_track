const EMPTY = { type: "FeatureCollection", features: [] };

export function draftCollection(coordinates, vertexCount = 0) {
  if (!coordinates?.length) return EMPTY;
  const features = [];
  for (const pair of coordinates.slice(0, vertexCount)) {
    features.push(feature("Point", [pair[0], pair[1]]));
  }
  if (coordinates.length >= 2) {
    const line = coordinates.length >= 3 ? closedRing(coordinates) : coordinates.map(copy);
    features.push(feature("LineString", line));
  }
  if (coordinates.length >= 3) {
    features.push(feature("Polygon", [closedRing(coordinates)]));
  }
  return { type: "FeatureCollection", features };
}

export function closedRing(coordinates) {
  const ring = counterClockwise(coordinates);
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] !== last[0] || first[1] !== last[1]) ring.push([first[0], first[1]]);
  return ring;
}

export function counterClockwise(coordinates) {
  const ring = coordinates.map(copy);
  if (ring.length >= 3 && signedArea(ring) < 0) ring.reverse();
  return ring;
}

export function signedArea(coordinates) {
  let sum = 0;
  for (let index = 0; index < coordinates.length; index += 1) {
    const [x1, y1] = coordinates[index];
    const [x2, y2] = coordinates[(index + 1) % coordinates.length];
    sum += x1 * y2 - x2 * y1;
  }
  return sum / 2;
}

function feature(type, coordinates) {
  return { type: "Feature", properties: {}, geometry: { type, coordinates } };
}

function copy(pair) {
  return [pair[0], pair[1]];
}
