export function loadPatch(speedKmh, batchSize) {
  const body = {};
  const speed = Number(speedKmh);
  const size = Number(batchSize);
  if (filled(speedKmh) && Number.isFinite(speed) && speed > 0) body.speed_kmh = speed;
  if (filled(batchSize) && Number.isInteger(size) && size > 0) body.telemetry_batch_max_size = size;
  return body;
}

function filled(value) {
  return value !== "" && value != null;
}
