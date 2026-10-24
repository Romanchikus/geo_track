import { counterClockwise, signedArea } from "./draft.js";

const EPS = 1e-9;

export function unionRing(points) {
  const ring = openRing(points);
  if (ring.length < 3) return ring.map(copy);
  if (!hitsItself(ring)) return counterClockwise(ring);
  const outline = solidOutline(ring);
  if (!outline || outline.length < 3 || hitsItself(outline)) return counterClockwise(ring);
  return counterClockwise(outline);
}

function solidOutline(ring) {
  const pieces = nodeSegments(closedSegments(ring));
  const faces = walkFaces(pieces);
  const bounded = faces.filter((face) => signedArea(face) > EPS);
  if (!bounded.length) return null;
  return outerRing(boundaryEdges(bounded));
}

function openRing(points) {
  const ring = [];
  for (const point of points ?? []) {
    if (!point || point.length < 2) continue;
    const pair = [point[0], point[1]];
    if (ring.length && same(ring[ring.length - 1], pair)) continue;
    ring.push(pair);
  }
  if (ring.length > 1 && same(ring[0], ring[ring.length - 1])) ring.pop();
  return ring;
}

function closedSegments(ring) {
  const segments = [];
  for (let index = 0; index < ring.length; index += 1) {
    segments.push([ring[index], ring[(index + 1) % ring.length]]);
  }
  return segments;
}

function hitsItself(ring) {
  const segments = closedSegments(ring);
  for (let left = 0; left < segments.length; left += 1) {
    for (let right = left + 1; right < segments.length; right += 1) {
      if (Math.abs(left - right) === 1 || (left === 0 && right === segments.length - 1)) continue;
      if (crossings(segments[left][0], segments[left][1], segments[right][0], segments[right][1]).length) return true;
    }
  }
  return false;
}

function nodeSegments(segments) {
  const cuts = segments.map(() => []);
  for (let left = 0; left < segments.length; left += 1) {
    for (let right = left + 1; right < segments.length; right += 1) {
      const hits = crossings(segments[left][0], segments[left][1], segments[right][0], segments[right][1]);
      for (const hit of hits) {
        cuts[left].push({ t: hit.t, point: hit.point });
        cuts[right].push({ t: hit.u, point: hit.point });
      }
    }
  }
  const pieces = [];
  segments.forEach((segment, index) => {
    const ordered = cuts[index]
      .filter((cut) => cut.t > EPS && cut.t < 1 - EPS)
      .sort((a, b) => a.t - b.t);
    const chain = [segment[0]];
    for (const cut of ordered) {
      if (!same(chain[chain.length - 1], cut.point)) chain.push(cut.point);
    }
    if (!same(chain[chain.length - 1], segment[1])) chain.push(segment[1]);
    for (let step = 0; step < chain.length - 1; step += 1) {
      if (!same(chain[step], chain[step + 1])) pieces.push([chain[step], chain[step + 1]]);
    }
  });
  return pieces;
}

function crossings(start, end, otherStart, otherEnd) {
  const run = [end[0] - start[0], end[1] - start[1]];
  const other = [otherEnd[0] - otherStart[0], otherEnd[1] - otherStart[1]];
  const den = run[0] * other[1] - run[1] * other[0];
  const delta = [otherStart[0] - start[0], otherStart[1] - start[1]];
  if (Math.abs(den) <= EPS) {
    if (Math.abs(run[0] * delta[1] - run[1] * delta[0]) > EPS) return [];
    return overlapCuts(start, end, otherStart, otherEnd);
  }
  const t = (delta[0] * other[1] - delta[1] * other[0]) / den;
  const u = (delta[0] * run[1] - delta[1] * run[0]) / den;
  if (t <= EPS || t >= 1 - EPS || u <= EPS || u >= 1 - EPS) return [];
  return [{ t, u, point: snap([start[0] + run[0] * t, start[1] + run[1] * t]) }];
}

function overlapCuts(start, end, otherStart, otherEnd) {
  const axis = Math.abs(end[0] - start[0]) >= Math.abs(end[1] - start[1]) ? 0 : 1;
  const span = end[axis] - start[axis];
  if (Math.abs(span) <= EPS) return [];
  const t0 = (otherStart[axis] - start[axis]) / span;
  const t1 = (otherEnd[axis] - start[axis]) / span;
  const enter = Math.max(0, Math.min(t0, t1));
  const leave = Math.min(1, Math.max(t0, t1));
  if (leave - enter <= EPS) return [];
  const cuts = [];
  for (const t of [enter, leave]) {
    if (t <= EPS || t >= 1 - EPS) continue;
    const point = snap([start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t]);
    const u = parameterOn(otherStart, otherEnd, point, axis);
    cuts.push({ t, u, point });
  }
  return cuts;
}

function parameterOn(start, end, point, axis) {
  const span = end[axis] - start[axis];
  if (Math.abs(span) <= EPS) return 0;
  return (point[axis] - start[axis]) / span;
}

function walkFaces(pieces) {
  const outgoing = new Map();
  const half = pieces.map((piece, index) => {
    const forward = { id: index * 2, from: key(piece[0]), to: key(piece[1]), point: piece[0], next: null };
    const back = { id: index * 2 + 1, from: key(piece[1]), to: key(piece[0]), point: piece[1], next: null };
    forward.twin = back;
    back.twin = forward;
    push(outgoing, forward);
    push(outgoing, back);
    return [forward, back];
  });
  for (const leaving of outgoing.values()) {
    leaving.sort((a, b) => angle(a) - angle(b));
    for (let index = 0; index < leaving.length; index += 1) {
      const incoming = leaving[index].twin;
      incoming.next = leaving[(index - 1 + leaving.length) % leaving.length];
    }
  }
  const seen = new Set();
  const faces = [];
  for (const pair of half) {
    for (const edge of pair) {
      if (seen.has(edge.id) || !edge.next) continue;
      const face = [];
      let cursor = edge;
      let guard = 0;
      while (cursor && !seen.has(cursor.id) && guard < half.length * 4) {
        seen.add(cursor.id);
        face.push(cursor.point);
        cursor = cursor.next;
        guard += 1;
        if (cursor === edge) break;
      }
      if (face.length >= 3) faces.push(dedupeFace(face));
    }
  }
  return faces;
}

function boundaryEdges(faces) {
  const count = new Map();
  for (const face of faces) {
    for (let index = 0; index < face.length; index += 1) {
      const start = face[index];
      const end = face[(index + 1) % face.length];
      if (same(start, end)) continue;
      const id = edgeKey(start, end);
      const row = count.get(id) ?? { start, end, n: 0 };
      row.n += 1;
      count.set(id, row);
    }
  }
  return [...count.values()].filter((edge) => edge.n === 1).map((edge) => [edge.start, edge.end]);
}

function outerRing(edges) {
  if (!edges.length) return null;
  const links = new Map();
  for (const [start, end] of edges) {
    pushLink(links, key(start), end);
    pushLink(links, key(end), start);
  }
  const unused = new Map(edges.map((edge) => [edgeKey(edge[0], edge[1]), edge]));
  const rings = [];
  for (const edge of edges) {
    const id = edgeKey(edge[0], edge[1]);
    if (!unused.has(id)) continue;
    const ring = [];
    let point = edge[0];
    let guard = 0;
    while (guard < edges.length + 2) {
      ring.push(point);
      const next = takeLink(links, point, unused);
      if (!next) break;
      point = next;
      guard += 1;
      if (same(point, ring[0])) break;
    }
    if (ring.length >= 3 && same(point, ring[0])) rings.push(ring);
  }
  rings.sort((left, right) => Math.abs(signedArea(right)) - Math.abs(signedArea(left)));
  return rings[0] ?? null;
}

function takeLink(links, point, unused) {
  const options = links.get(key(point)) ?? [];
  for (let index = 0; index < options.length; index += 1) {
    const candidate = options[index];
    const id = edgeKey(point, candidate);
    if (!unused.has(id)) continue;
    unused.delete(id);
    options.splice(index, 1);
    return candidate;
  }
  return null;
}

function push(outgoing, edge) {
  const list = outgoing.get(edge.from) ?? [];
  list.push(edge);
  outgoing.set(edge.from, list);
}

function pushLink(links, id, point) {
  const list = links.get(id) ?? [];
  list.push(point);
  links.set(id, list);
}

function angle(edge) {
  const [x, y] = edge.point;
  const [nx, ny] = edge.twin.point;
  return Math.atan2(ny - y, nx - x);
}

function dedupeFace(face) {
  const ring = [];
  for (const point of face) {
    if (!ring.length || !same(ring[ring.length - 1], point)) ring.push(point);
  }
  if (ring.length > 1 && same(ring[0], ring[ring.length - 1])) ring.pop();
  return ring;
}

function edgeKey(start, end) {
  const left = key(start);
  const right = key(end);
  return left < right ? `${left}|${right}` : `${right}|${left}`;
}

function key(point) {
  return `${point[0].toFixed(7)},${point[1].toFixed(7)}`;
}

function snap(point) {
  return [round(point[0]), round(point[1])];
}

function round(value) {
  return Math.round(value * 1e7) / 1e7;
}

function same(left, right) {
  return Math.abs(left[0] - right[0]) <= EPS && Math.abs(left[1] - right[1]) <= EPS;
}

function copy(point) {
  return [point[0], point[1]];
}
