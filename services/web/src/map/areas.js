import { closedRing } from "./draft.js";

export function areaLabel(area) {
  return `Area ${area.polygon_id}`;
}

export function areaCollection(areas, alerted = {}) {
  return {
    type: "FeatureCollection",
    features: (areas ?? [])
      .filter((area) => area.coordinates?.length >= 3)
      .map((area) => ({
        type: "Feature",
        properties: {
          label: areaLabel(area),
          polygon_id: area.polygon_id,
          alert: alerted[area.polygon_id] ? 1 : 0,
        },
        geometry: { type: "Polygon", coordinates: [closedRing(area.coordinates)] },
      })),
  };
}

export function ringContains(coordinates, point) {
  if (!coordinates || coordinates.length < 3 || !point) return false;
  const [x, y] = point;
  let inside = false;
  for (let index = 0, previous = coordinates.length - 1; index < coordinates.length; previous = index, index += 1) {
    const [x1, y1] = coordinates[previous];
    const [x2, y2] = coordinates[index];
    if (y1 > y === y2 > y) continue;
    const xHit = ((x2 - x1) * (y - y1)) / (y2 - y1) + x1;
    if (x < xHit) inside = !inside;
  }
  return inside;
}

export function unconfirmedDevices(devices, areas, alerted = {}) {
  return createCoverage().unknown(devices, areas, alerted);
}

export function createCoverage() {
  let signature = "";
  let prepared = [];
  const located = new Map();

  return {
    unknown(devices, areas, alerted = {}) {
      const next = areaSignature(areas);
      if (next !== signature) {
        signature = next;
        prepared = prepareAreas(areas);
        located.clear();
      }
      if (!prepared.length) return {};
      const unknown = {};
      const seen = new Set();
      for (const [id, point] of Object.entries(devices ?? {})) {
        seen.add(id);
        if (alerted[id]) continue;
        const lon = point?.longitude;
        const lat = point?.latitude;
        if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
        let hit = located.get(id);
        if (!hit || hit.lon !== lon || hit.lat !== lat) {
          hit = { lon, lat, inside: pointInside(prepared, Number(id), lon, lat) };
          located.set(id, hit);
        }
        if (hit.inside) unknown[id] = true;
      }
      if (located.size > seen.size) {
        for (const id of located.keys()) {
          if (!seen.has(id)) located.delete(id);
        }
      }
      return unknown;
    },
  };
}

function prepareAreas(areas) {
  const prepared = [];
  for (const area of areas ?? []) {
    const ring = area.coordinates;
    if (!ring || ring.length < 3) continue;
    let west = Infinity;
    let south = Infinity;
    let east = -Infinity;
    let north = -Infinity;
    for (const [lon, lat] of ring) {
      if (lon < west) west = lon;
      if (lon > east) east = lon;
      if (lat < south) south = lat;
      if (lat > north) north = lat;
    }
    const subscribed = new Set((area.devices ?? []).map((device) => Number(device.device_id)));
    prepared.push({ ring, west, south, east, north, subscribed });
  }
  return prepared;
}

function pointInside(prepared, deviceId, lon, lat) {
  for (const area of prepared) {
    if (!area.subscribed.has(deviceId)) continue;
    if (lon < area.west || lon > area.east || lat < area.south || lat > area.north) continue;
    if (ringContains(area.ring, [lon, lat])) return true;
  }
  return false;
}

function areaSignature(areas) {
  if (!areas?.length) return "";
  let hash = areas.length;
  for (const area of areas) {
    hash = (hash * 31 + Number(area.polygon_id || 0)) | 0;
    const ring = area.coordinates;
    if (!ring) continue;
    hash = (hash * 31 + ring.length) | 0;
    for (const device of area.devices ?? []) {
      hash = (hash * 33 + Number(device.device_id)) | 0;
    }
    for (const [lon, lat] of ring) {
      hash = (hash * 33 + Math.round(lon * 1e5) + Math.round(lat * 1e5)) | 0;
    }
  }
  return String(hash);
}

export function ringCentroid(coordinates) {
  let twice = 0;
  let cx = 0;
  let cy = 0;
  for (let index = 0; index < coordinates.length; index += 1) {
    const [x1, y1] = coordinates[index];
    const [x2, y2] = coordinates[(index + 1) % coordinates.length];
    const cross = x1 * y2 - x2 * y1;
    twice += cross;
    cx += (x1 + x2) * cross;
    cy += (y1 + y2) * cross;
  }
  if (Math.abs(twice) < 1e-12) {
    const lon = coordinates.reduce((sum, pair) => sum + pair[0], 0) / coordinates.length;
    const lat = coordinates.reduce((sum, pair) => sum + pair[1], 0) / coordinates.length;
    return [lon, lat];
  }
  return [cx / (3 * twice), cy / (3 * twice)];
}

export function boundsOf(pairs) {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const [lon, lat] of pairs) {
    west = Math.min(west, lon);
    east = Math.max(east, lon);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  }
  if (!Number.isFinite(west)) return null;
  if (east - west < 0.02) {
    west -= 0.02;
    east += 0.02;
  }
  if (north - south < 0.02) {
    south -= 0.02;
    north += 0.02;
  }
  return [
    [west, south],
    [east, north],
  ];
}
