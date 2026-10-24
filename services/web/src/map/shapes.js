const EARTH_RADIUS_M = 6378137;
const MIN_SIZE_M = 50;

export function distanceM(start, end) {
  const lat1 = toRad(start[1]);
  const lat2 = toRad(end[1]);
  const dLat = toRad(end[1] - start[1]);
  const dLon = toRad(end[0] - start[0]);
  const chord = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.atan2(Math.sqrt(chord), Math.sqrt(1 - chord));
}

export function circleRing(center, edge, steps = 64) {
  const radius = distanceM(center, edge);
  if (radius < MIN_SIZE_M) return null;
  const ring = [];
  for (let index = 0; index < steps; index += 1) {
    ring.push(destination(center[0], center[1], (index / steps) * Math.PI * 2, radius));
  }
  ring.reverse();
  return ring;
}

export function squareRing(center, edge) {
  const half = distanceM(center, edge);
  if (half < MIN_SIZE_M) return null;
  const north = destination(center[0], center[1], 0, half);
  const south = destination(center[0], center[1], Math.PI, half);
  const east = destination(center[0], center[1], Math.PI / 2, half);
  const west = destination(center[0], center[1], (3 * Math.PI) / 2, half);
  return [
    [west[0], north[1]],
    [west[0], south[1]],
    [east[0], south[1]],
    [east[0], north[1]],
  ];
}

export function formatKm(meters) {
  if (!Number.isFinite(meters)) return "";
  if (meters < 1000) return `${Math.round(meters)} m`;
  return `${(meters / 1000).toFixed(1)} km`;
}

function destination(lon, lat, bearing, distance) {
  const angular = distance / EARTH_RADIUS_M;
  const lat1 = toRad(lat);
  const lon1 = toRad(lon);
  const lat2 = Math.asin(Math.sin(lat1) * Math.cos(angular) + Math.cos(lat1) * Math.sin(angular) * Math.cos(bearing));
  const lon2 = lon1 + Math.atan2(
    Math.sin(bearing) * Math.sin(angular) * Math.cos(lat1),
    Math.cos(angular) - Math.sin(lat1) * Math.sin(lat2),
  );
  return [wrapLon(toDeg(lon2)), toDeg(lat2)];
}

function toRad(degrees) {
  return (degrees * Math.PI) / 180;
}

function toDeg(radians) {
  return (radians * 180) / Math.PI;
}

function wrapLon(lon) {
  let value = lon;
  while (value > 180) value -= 360;
  while (value < -180) value += 360;
  return value;
}
