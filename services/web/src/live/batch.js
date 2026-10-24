export const POINT_BYTES = 20;

export function unpackPoints(buffer) {
  const view = new DataView(buffer);
  const count = Math.floor(view.byteLength / POINT_BYTES);
  const devices = new Map();
  for (let index = 0; index < count; index += 1) {
    const base = index * POINT_BYTES;
    devices.set(Number(view.getBigInt64(base, true)), {
      latitude: view.getFloat32(base + 8, true),
      longitude: view.getFloat32(base + 12, true),
      timestamp: view.getUint32(base + 16, true),
    });
  }
  return devices;
}

export function mergeDevices(current, updates) {
  const next = { ...current };
  for (const [id, point] of updates) {
    const previous = current[id];
    next[id] = {
      latitude: point.latitude,
      longitude: point.longitude,
      timestamp: point.timestamp,
      direction: directionFrom(previous, point),
    };
  }
  return next;
}

export function deviceFeatures(devices, alerted = {}, unknown = {}) {
  const features = [];
  for (const [id, point] of Object.entries(devices ?? {})) {
    if (!Number.isFinite(point?.longitude) || !Number.isFinite(point?.latitude)) continue;
    const alert = alerted[id] ? 1 : 0;
    features.push({
      type: "Feature",
      properties: {
        id: Number(id),
        direction: heading(point.direction),
        alert,
        unknown: alert ? 0 : unknown[id] ? 1 : 0,
      },
      geometry: { type: "Point", coordinates: [point.longitude, point.latitude] },
    });
  }
  return { type: "FeatureCollection", features };
}

export function arrivalsState(rows) {
  const devices = {};
  const polygons = {};
  for (const row of rows ?? []) {
    if (!Number.isInteger(row?.device_id) || !Number.isInteger(row?.polygon_id)) continue;
    devices[row.device_id] = true;
    polygons[row.polygon_id] = true;
  }
  return { devices, polygons };
}

function directionFrom(previous, point) {
  if (!previous || !moved(previous, point)) return heading(previous?.direction);
  const latitude1 = radians(previous.latitude);
  const latitude2 = radians(point.latitude);
  const delta = radians(point.longitude - previous.longitude);
  const y = Math.sin(delta) * Math.cos(latitude2);
  const x = Math.cos(latitude1) * Math.sin(latitude2) - Math.sin(latitude1) * Math.cos(latitude2) * Math.cos(delta);
  return heading((Math.atan2(y, x) * 180) / Math.PI);
}

function moved(previous, point) {
  return previous.latitude !== point.latitude || previous.longitude !== point.longitude;
}

function heading(direction) {
  if (!Number.isFinite(direction)) return 0;
  return (direction + 360) % 360;
}

function radians(degrees) {
  return (degrees * Math.PI) / 180;
}
