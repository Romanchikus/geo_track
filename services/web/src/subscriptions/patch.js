export function subscriptionPatch(area, next) {
  const body = {};
  if (!sameRing(area.coordinates ?? [], next.coordinates ?? [])) body.coordinates = copyRing(next.coordinates);
  const scope = deviceScope(area.devices ?? [], next);
  if (scope) Object.assign(body, scope);
  return body;
}

function deviceScope(devices, next) {
  if (next.mode === "all") return { mode: "all" };
  if (next.mode === "percent") return { mode: "percent", percent: next.percent };
  if (next.mode !== "ids") return null;
  const deviceIds = next.deviceIds ?? [];
  const current = devices.map((device) => device.device_id);
  if (sameIds(current, deviceIds)) return null;
  return { device_ids: deviceIds };
}

function sameRing(left, right) {
  if (left.length !== right.length) return false;
  return left.every((pair, index) => pair[0] === right[index][0] && pair[1] === right[index][1]);
}

function sameIds(left, right) {
  if (left.length !== right.length) return false;
  return left.every((id, index) => id === right[index]);
}

function copyRing(coordinates) {
  return coordinates.map((pair) => [pair[0], pair[1]]);
}
