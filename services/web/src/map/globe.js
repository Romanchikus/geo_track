import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

import { deviceFeatures } from "../live/batch.js";
import { areaCollection, areaLabel, boundsOf, createCoverage, ringCentroid } from "./areas.js";
import { draftCollection } from "./draft.js";

maplibregl.setWorkerUrl(workerUrl);

const EMPTY = { type: "FeatureCollection", features: [] };
const TOOLS = ["polygon", "radius", "square"];

const STYLE = {
  version: 8,
  projection: { type: "globe" },
  glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
  sources: {
    satellite: {
      type: "raster",
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      tileSize: 256,
      attribution: "Tiles © Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    },
  },
  layers: [{ id: "satellite", type: "raster", source: "satellite" }],
};

export function createGlobe(container, { onClick, onMove, onDown }) {
  const map = new maplibregl.Map({
    container,
    style: STYLE,
    center: [0, 20],
    zoom: 1.2,
    attributionControl: true,
  });
  const pending = { areas: EMPTY, draft: EMPTY, marks: EMPTY, devices: EMPTY, labels: [], fit: false };
  const coverage = createCoverage();
  let ready = false;
  let markers = [];

  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-left");
  const observer = new ResizeObserver(() => map.resize());
  observer.observe(container);
  map.on("error", (event) => {
    console.error("map error", event?.error?.message || event?.error || "unknown");
  });
  map.on("load", () => {
    if (map.getProjection()?.type !== "globe") map.setProjection({ type: "globe" });
    ready = true;
    publishAreas();
    publishDraft();
    publishDevices();
    map.resize();
  });
  map.on("click", (event) => {
    const point = lngLat(event);
    if (point) onClick(point, event.point);
  });
  map.on("mousemove", (event) => {
    const point = lngLat(event);
    if (point) onMove(point, event.point);
  });
  map.on("mousedown", (event) => {
    if (event.originalEvent?.button !== 0) return;
    const point = lngLat(event);
    if (!point || onDown?.(point, event.point) !== true || !map.dragPan.isEnabled()) return;
    event.preventDefault();
    map.dragPan.disable();
    const release = () => {
      window.removeEventListener("mouseup", release);
      map.dragPan.enable();
    };
    window.addEventListener("mouseup", release);
  });

  function publishAreas() {
    if (!showWhenReady(publishAreas)) return;
    ensureAreas(map);
    writeSource(map, "areas", pending.areas);
    syncMarkers(pending.labels);
    if (pending.fit) {
      pending.fit = false;
      fit(pending.labels.flatMap((area) => area.coordinates ?? []));
    }
    map.triggerRepaint();
  }

  function publishDevices() {
    if (!showWhenReady(publishDevices)) return;
    ensureDevices(map);
    writeSource(map, "devices", pending.devices);
    map.triggerRepaint();
  }

  function publishDraft() {
    if (!showWhenReady(publishDraft)) return;
    ensureDraft(map);
    writeSource(map, "draft", pending.draft);
    writeSource(map, "draft-marks", pending.marks);
    map.triggerRepaint();
  }

  function fit(pairs) {
    const bounds = boundsOf(pairs);
    if (!bounds) return;
    map.resize();
    map.fitBounds(bounds, { padding: framePadding(), maxZoom: 12, duration: 600 });
  }

  function showWhenReady(publish) {
    if (!ready) return false;
    if (map.isStyleLoaded()) return true;
    map.once("idle", publish);
    return false;
  }

  function framePadding() {
    const wide = container.clientWidth > 720;
    return { top: 48, right: wide ? 340 : 48, bottom: 48, left: 48 };
  }

  function syncMarkers(areas) {
    for (const marker of markers) marker.remove();
    markers = [];
    for (const area of areas) {
      if (!area.coordinates || area.coordinates.length < 3) continue;
      const element = document.createElement("div");
      element.className = "area-label";
      element.textContent = areaLabel(area);
      markers.push(
        new maplibregl.Marker({ element, anchor: "center" }).setLngLat(ringCentroid(area.coordinates)).addTo(map),
      );
    }
  }

  return {
    setAreas(areas, { fit: shouldFit = false, alerted = {} } = {}) {
      pending.labels = areas ?? [];
      pending.areas = areaCollection(pending.labels, alerted);
      pending.fit = pending.fit || shouldFit;
      publishAreas();
    },
    setDevices(devices, alerted = {}, areas = []) {
      pending.devices = deviceFeatures(devices, alerted, coverage.unknown(devices, areas, alerted));
      publishDevices();
    },
    setDraft(coordinates, vertexCount = 0) {
      const features = coordinates?.length ? draftCollection(coordinates, vertexCount).features : [];
      pending.marks = collectionOf(features.filter((feature) => feature.geometry.type === "Point"));
      pending.draft = collectionOf(features.filter((feature) => feature.geometry.type !== "Point"));
      publishDraft();
    },
    focus(area) {
      if (!ready || !area?.coordinates?.length) return;
      fit(area.coordinates);
    },
    pixelOf(pair) {
      if (!ready || !pair) return null;
      const projected = map.project(pair);
      return { x: projected.x, y: projected.y };
    },
    setTool(tool) {
      for (const name of TOOLS) container.classList.toggle(`tool-${name}`, name === tool);
      const handlers = [map.dragPan, map.dragRotate, map.doubleClickZoom, map.boxZoom];
      for (const handler of handlers) {
        if (tool) handler.disable();
        else handler.enable();
      }
    },
    destroy() {
      observer.disconnect();
      for (const marker of markers) marker.remove();
      markers = [];
      map.remove();
    },
  };
}

function lngLat(event) {
  if (!event.lngLat) return null;
  return [event.lngLat.lng, event.lngLat.lat];
}

function ensureDevices(map) {
  if (map.getSource("devices")) return;
  if (!map.hasImage("plane")) map.addImage("plane", planeImage(), { pixelRatio: 2 });
  if (!map.hasImage("flag")) map.addImage("flag", flagImage(), { pixelRatio: 2 });
  if (!map.hasImage("unknown")) map.addImage("unknown", unknownImage(), { pixelRatio: 2 });
  map.addSource("devices", geojson());
  map.addLayer({
    id: "devices",
    type: "symbol",
    source: "devices",
    layout: {
      "icon-image": "plane",
      "icon-size": 0.9,
      "icon-anchor": "center",
      "icon-rotate": ["get", "direction"],
      "icon-pitch-alignment": "viewport",
      "icon-rotation-alignment": "map",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  });
  map.addLayer({
    id: "device-ids",
    type: "symbol",
    source: "devices",
    layout: {
      "text-field": ["to-string", ["get", "id"]],
      "text-font": ["Open Sans Regular"],
      "text-size": 12,
      "text-offset": [0.9, 0],
      "text-anchor": "left",
      "text-allow-overlap": true,
      "text-ignore-placement": true,
    },
    paint: {
      "text-color": "#f4f7fb",
      "text-halo-color": "#12161c",
      "text-halo-width": 1.4,
    },
  });
  map.addLayer({
    id: "device-flags",
    type: "symbol",
    source: "devices",
    filter: ["==", ["get", "alert"], 1],
    layout: {
      "icon-image": "flag",
      "icon-size": 0.72,
      "icon-anchor": "bottom",
      "icon-offset": [0, -26],
      "icon-pitch-alignment": "viewport",
      "icon-rotation-alignment": "viewport",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  });
  map.addLayer({
    id: "device-unknown",
    type: "symbol",
    source: "devices",
    filter: ["==", ["get", "unknown"], 1],
    layout: {
      "icon-image": "unknown",
      "icon-size": 0.72,
      "icon-anchor": "center",
      "icon-offset": [0, -36],
      "icon-pitch-alignment": "viewport",
      "icon-rotation-alignment": "viewport",
      "icon-allow-overlap": true,
      "icon-ignore-placement": true,
    },
  });
}

function planeImage() {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, size, size);
  context.translate(size / 2, size / 2);
  context.lineJoin = "round";
  context.lineCap = "round";
  paintJet(context, 1.4, 2, "rgba(8, 12, 20, 0.4)");
  paintJet(context, 0, 0, null);
  context.beginPath();
  context.moveTo(0, -15);
  context.lineTo(1.5, -6);
  context.lineTo(-1.5, -6);
  context.closePath();
  context.fillStyle = "#ffb703";
  context.fill();
  return context.getImageData(0, 0, size, size);
}

function paintJet(context, x, y, fill) {
  context.save();
  context.translate(x, y);
  context.beginPath();
  context.moveTo(0, -22);
  context.quadraticCurveTo(3.4, -14, 3.2, -6);
  context.lineTo(20, 3);
  context.lineTo(20, 6.2);
  context.lineTo(3.5, 1.6);
  context.lineTo(3, 11);
  context.lineTo(9, 15.5);
  context.lineTo(9, 18);
  context.lineTo(0, 14.6);
  context.lineTo(-9, 18);
  context.lineTo(-9, 15.5);
  context.lineTo(-3, 11);
  context.lineTo(-3.5, 1.6);
  context.lineTo(-20, 6.2);
  context.lineTo(-20, 3);
  context.lineTo(-3.2, -6);
  context.quadraticCurveTo(-3.4, -14, 0, -22);
  context.closePath();
  if (fill) {
    context.fillStyle = fill;
    context.fill();
  } else {
    const body = context.createLinearGradient(-20, -22, 16, 18);
    body.addColorStop(0, "#f7fbff");
    body.addColorStop(0.42, "#d5e4f6");
    body.addColorStop(1, "#7ea6d4");
    context.fillStyle = body;
    context.fill();
    context.strokeStyle = "#152033";
    context.lineWidth = 2.2;
    context.stroke();
  }
  context.restore();
}

function flagImage() {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, size, size);
  context.translate(size / 2, size / 2);
  context.lineCap = "round";
  context.lineJoin = "round";
  context.strokeStyle = "#1a1208";
  context.lineWidth = 3;
  context.beginPath();
  context.moveTo(-12, 20);
  context.lineTo(-12, -20);
  context.stroke();
  context.beginPath();
  context.moveTo(-12, -20);
  context.quadraticCurveTo(4, -16, 18, -12);
  context.quadraticCurveTo(6, -6, 16, -1);
  context.quadraticCurveTo(2, 2, -12, 6);
  context.closePath();
  const cloth = context.createLinearGradient(-12, -20, 18, 6);
  cloth.addColorStop(0, "#ff5a6a");
  cloth.addColorStop(0.55, "#d7263d");
  cloth.addColorStop(1, "#8e1224");
  context.fillStyle = cloth;
  context.fill();
  context.lineWidth = 2;
  context.stroke();
  context.beginPath();
  context.arc(-12, -20, 2.4, 0, Math.PI * 2);
  context.fillStyle = "#ffb703";
  context.fill();
  return context.getImageData(0, 0, size, size);
}

function unknownImage() {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, size, size);
  context.translate(size / 2, size / 2);
  context.lineCap = "round";
  context.lineJoin = "round";
  context.beginPath();
  context.arc(0, 0, 18, 0, Math.PI * 2);
  context.fillStyle = "rgba(18, 22, 28, 0.28)";
  context.fill();
  context.beginPath();
  context.arc(0, -1, 16, 0, Math.PI * 2);
  const disc = context.createRadialGradient(-6, -10, 2, 0, -1, 16);
  disc.addColorStop(0, "#fff8e4");
  disc.addColorStop(0.48, "#f3c453");
  disc.addColorStop(1, "#b87416");
  context.fillStyle = disc;
  context.fill();
  context.lineWidth = 2.2;
  context.strokeStyle = "#1a1208";
  context.stroke();
  context.beginPath();
  context.arc(0, -1, 12.2, Math.PI * 1.15, Math.PI * 1.85);
  context.strokeStyle = "rgba(255, 250, 235, 0.7)";
  context.lineWidth = 1.4;
  context.stroke();
  context.strokeStyle = "#1a1208";
  context.lineWidth = 3.2;
  context.beginPath();
  context.arc(0, -7, 6.4, 0.65, Math.PI / 2, true);
  context.stroke();
  context.beginPath();
  context.moveTo(0, 0.2);
  context.lineTo(0, 5);
  context.stroke();
  context.beginPath();
  context.arc(0, 8.6, 1.7, 0, Math.PI * 2);
  context.fillStyle = "#1a1208";
  context.fill();
  return context.getImageData(0, 0, size, size);
}

function ensureAreas(map) {
  if (map.getSource("areas")) return;
  const line = ["case", ["==", ["get", "alert"], 1], "#e07070", "#9db7ff"];
  const fill = ["case", ["==", ["get", "alert"], 1], "#ffb4b4", "#9db7ff"];
  addPolygonLayers(map, "areas", line, fill);
}

function ensureDraft(map) {
  if (map.getSource("draft")) return;
  addPolygonLayers(map, "draft", "#ffe7a3", "#f0d48a");
  map.addSource("draft-marks", geojson());
  map.addLayer({
    id: "draft-points",
    type: "circle",
    source: "draft-marks",
    paint: {
      "circle-radius": 5,
      "circle-color": "#ffe7a3",
      "circle-stroke-width": 2,
      "circle-stroke-color": "#1a1208",
    },
  });
}

function addPolygonLayers(map, id, line, fill = line) {
  map.addSource(id, geojson());
  map.addLayer({
    id: `${id}-fill`,
    type: "fill",
    source: id,
    paint: { "fill-color": fill, "fill-opacity": 0.45 },
  });
  map.addLayer({
    id: `${id}-casing`,
    type: "line",
    source: id,
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#1a1208", "line-width": 6 },
  });
  map.addLayer({
    id: `${id}-line`,
    type: "line",
    source: id,
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": line, "line-width": 3 },
  });
}

function geojson() {
  return { type: "geojson", data: EMPTY, tolerance: 0 };
}

function collectionOf(features) {
  return { type: "FeatureCollection", features };
}

function writeSource(map, id, data) {
  const source = map.getSource(id);
  if (source) source.setData(data);
}
