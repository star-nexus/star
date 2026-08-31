(() => {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const HEX_SIZE = 28;
  const SQRT3 = Math.sqrt(3);
  const MAX_MAP_SIZE = 101;
  const STORAGE_KEY = "star-map-editor-v2";
  const LEGACY_STORAGE_KEY = "star-map-editor-v1.5";

  const TERRAIN = {
    ".": { name: "Plain", color: "#90ee90", movement: 1 },
    "~": { name: "Water", color: "#87cefa", movement: 999 },
    "F": { name: "Forest", color: "#228b22", movement: 2 },
    "H": { name: "Hill", color: "#a0522d", movement: 2 },
    "M": { name: "Mountain", color: "#8b4513", movement: 3 },
    "C": { name: "Urban", color: "#a9a9a9", movement: 2 },
  };

  // Keep these aligned with STAR's established UI convention.
  const FACTIONS = {
    wei: { label: "Wei", color: "#4f79ff" },
    shu: { label: "Shu", color: "#46c878" },
    wu: { label: "Wu", color: "#ff5f5f" },
  };

  const UNIT_TYPES = {
    infantry: { label: "Infantry", short: "I" },
    archer: { label: "Archer", short: "A" },
    cavalry: { label: "Cavalry", short: "C" },
  };

  const state = {
    id: "untitled",
    name: "Untitled Map",
    width: 15,
    height: 15,
    terrain: new Map(),
    // Internal representation is always [col, row, type].
    formations: { wei: [], shu: [], wu: [] },
    unitMix: null,
    tool: { kind: "terrain", value: "." },
    selectedFaction: "wei",
    selectedUnitType: "infantry",
    mode: "edit",
    referenceImage: null,
    referenceImageUrl: null,
    undo: [],
    redo: [],
    strokeActive: false,
    strokeTouched: new Set(),
    spaceDown: false,
    panActive: false,
    panPointerId: null,
    panLastX: 0,
    panLastY: 0,
    view: { zoom: 1, cx: 0, cy: 0, bounds: null },
  };

  const $ = (id) => document.getElementById(id);
  const els = {
    svg: $("mapSvg"),
    viewport: $("mapViewport"),
    palette: $("terrainPalette"),
    cursorInfo: $("cursorInfo"),
    mapId: $("mapId"),
    mapName: $("mapName"),
    mapWidth: $("mapWidth"),
    mapHeight: $("mapHeight"),
    showCoords: $("showCoords"),
    showFormations: $("showFormations"),
    showGrid: $("showGrid"),
    validationSummary: $("validationSummary"),
    validationList: $("validationList"),
    mapStats: $("mapStats"),
    imageControls: $("imageControls"),
    imageOpacity: $("imageOpacity"),
    showReference: $("showReference"),
    imageFileInput: $("imageFileInput"),
    jsonFileInput: $("jsonFileInput"),
    sampleCanvas: $("sampleCanvas"),
    zoomLabel: $("zoomLabel"),
  };

  function key(col, row) { return `${col},${row}`; }
  function halfW() { return Math.floor(state.width / 2); }
  function halfH() { return Math.floor(state.height / 2); }
  function cols() { return Array.from({ length: state.width }, (_, i) => i - halfW()); }
  function rowsNorthFirst() { return Array.from({ length: state.height }, (_, i) => halfH() - i); }
  function inBounds(col, row) {
    return col >= -halfW() && col <= state.width - halfW() - 1 &&
      row <= halfH() && row >= halfH() - state.height + 1;
  }

  function hexToPixel(col, row, size = HEX_SIZE) {
    return {
      x: size * 1.5 * col,
      y: -size * SQRT3 * (row + 0.5 * (col & 1)),
    };
  }

  function hexCorners(col, row, size = HEX_SIZE) {
    const c = hexToPixel(col, row, size);
    const points = [];
    for (let i = 0; i < 6; i++) {
      const a = (Math.PI / 180) * (60 * i);
      points.push([c.x + size * Math.cos(a), c.y + size * Math.sin(a)]);
    }
    return points;
  }

  function hexNeighbors(col, row) {
    const dirs = col % 2 === 0
      ? [[1,-1],[0,-1],[-1,-1],[-1,0],[0,1],[1,0]]
      : [[1,0],[0,-1],[-1,0],[-1,1],[0,1],[1,1]];
    return dirs.map(([dc, dr]) => [col + dc, row + dr]);
  }

  function offsetToAxial(col, row) {
    return [col, row - (col - (col & 1)) / 2];
  }

  function hexDistance(a, b) {
    const [q1, r1] = offsetToAxial(a[0], a[1]);
    const [q2, r2] = offsetToAxial(b[0], b[1]);
    const s1 = -q1 - r1;
    const s2 = -q2 - r2;
    return (Math.abs(q1-q2) + Math.abs(r1-r2) + Math.abs(s1-s2)) / 2;
  }

  function mapBounds() {
    // Correct for both even/odd column vertical offsets. At v2's 101x101
    // ceiling this one-time 6-corners-per-cell pass is still cheap and avoids
    // subtle clipping at the south edge.
    const all = [];
    for (const row of rowsNorthFirst()) {
      for (const col of cols()) all.push(...hexCorners(col, row));
    }
    const xs = all.map((p) => p[0]);
    const ys = all.map((p) => p[1]);
    const margin = HEX_SIZE * 1.25;
    return {
      minX: Math.min(...xs) - margin,
      maxX: Math.max(...xs) + margin,
      minY: Math.min(...ys) - margin,
      maxY: Math.max(...ys) + margin,
    };
  }

  function resetView() {
    const b = mapBounds();
    state.view.bounds = b;
    state.view.zoom = 1;
    state.view.cx = (b.minX + b.maxX) / 2;
    state.view.cy = (b.minY + b.maxY) / 2;
    applyViewBox();
  }

  function applyViewBox() {
    const b = state.view.bounds || mapBounds();
    state.view.bounds = b;
    const fullW = b.maxX - b.minX;
    const fullH = b.maxY - b.minY;
    const w = fullW / state.view.zoom;
    const h = fullH / state.view.zoom;
    const minCx = b.minX + w / 2;
    const maxCx = b.maxX - w / 2;
    const minCy = b.minY + h / 2;
    const maxCy = b.maxY - h / 2;
    state.view.cx = minCx > maxCx ? (b.minX + b.maxX) / 2 : Math.min(maxCx, Math.max(minCx, state.view.cx));
    state.view.cy = minCy > maxCy ? (b.minY + b.maxY) / 2 : Math.min(maxCy, Math.max(minCy, state.view.cy));
    els.svg.setAttribute("viewBox", `${state.view.cx - w / 2} ${state.view.cy - h / 2} ${w} ${h}`);
    if (els.zoomLabel) els.zoomLabel.textContent = `${Math.round(state.view.zoom * 100)}%`;
  }

  function setZoom(nextZoom, anchor = null) {
    const oldZoom = state.view.zoom;
    const next = Math.min(12, Math.max(1, nextZoom));
    if (next === oldZoom) return;
    if (anchor) {
      const ratio = oldZoom / next;
      state.view.cx = anchor.x + (state.view.cx - anchor.x) * ratio;
      state.view.cy = anchor.y + (state.view.cy - anchor.y) * ratio;
    }
    const crossedCoordinateThreshold = state.width * state.height > 3000 &&
      els.showCoords.checked && ((oldZoom < 2 && next >= 2) || (oldZoom >= 2 && next < 2));
    state.view.zoom = next;
    if (crossedCoordinateThreshold) render();
    else applyViewBox();
  }

  function clientToWorld(clientX, clientY) {
    const rect = els.svg.getBoundingClientRect();
    const vb = els.svg.viewBox.baseVal;
    return {
      x: vb.x + ((clientX - rect.left) / Math.max(1, rect.width)) * vb.width,
      y: vb.y + ((clientY - rect.top) / Math.max(1, rect.height)) * vb.height,
    };
  }

  function initializeTerrain(fill = ".") {
    state.terrain.clear();
    for (const row of rowsNorthFirst()) {
      for (const col of cols()) state.terrain.set(key(col, row), fill);
    }
  }

  function snapshot() {
    return {
      id: state.id,
      name: state.name,
      width: state.width,
      height: state.height,
      terrain: Array.from(state.terrain.entries()),
      formations: JSON.parse(JSON.stringify(state.formations)),
      unitMix: state.unitMix == null ? null : JSON.parse(JSON.stringify(state.unitMix)),
    };
  }

  function restore(snap) {
    state.id = snap.id;
    state.name = snap.name;
    state.width = snap.width;
    state.height = snap.height;
    state.terrain = new Map(snap.terrain);
    state.formations = JSON.parse(JSON.stringify(snap.formations));
    state.unitMix = snap.unitMix == null ? null : JSON.parse(JSON.stringify(snap.unitMix));
    syncInputs();
    render({ fit: true });
  }

  function checkpoint() {
    state.undo.push(snapshot());
    if (state.undo.length > 100) state.undo.shift();
    state.redo.length = 0;
    updateHistoryButtons();
  }

  function undo() {
    if (!state.undo.length) return;
    state.redo.push(snapshot());
    restore(state.undo.pop());
    updateHistoryButtons();
  }

  function redo() {
    if (!state.redo.length) return;
    state.undo.push(snapshot());
    restore(state.redo.pop());
    updateHistoryButtons();
  }

  function updateHistoryButtons() {
    $("undoBtn").disabled = state.undo.length === 0;
    $("redoBtn").disabled = state.redo.length === 0;
  }

  function syncInputs() {
    els.mapId.value = state.id;
    els.mapName.value = state.name;
    els.mapWidth.value = state.width;
    els.mapHeight.value = state.height;
  }

  function buildPalette() {
    els.palette.innerHTML = "";
    for (const [char, info] of Object.entries(TERRAIN)) {
      const btn = document.createElement("button");
      btn.dataset.terrain = char;
      btn.innerHTML = `<span class="swatch" style="background:${info.color}"></span><span>${info.name}</span><code>${char}</code>`;
      btn.addEventListener("click", () => selectTerrain(char));
      els.palette.appendChild(btn);
    }
    selectTerrain(".");
  }

  function updateBrushButtons() {
    document.querySelectorAll("[data-terrain]").forEach((b) => {
      b.classList.toggle("active", state.tool.kind === "terrain" && b.dataset.terrain === state.tool.value);
    });
    document.querySelectorAll("[data-faction]").forEach((b) => {
      b.classList.toggle("active", state.tool.kind === "unit" && b.dataset.faction === state.selectedFaction);
    });
    document.querySelectorAll("[data-unit-type]").forEach((b) => {
      b.classList.toggle("active", state.tool.kind === "unit" && b.dataset.unitType === state.selectedUnitType);
    });
    const erase = $("eraseUnitBtn");
    if (erase) erase.classList.toggle("active", state.tool.kind === "unit-erase");
  }

  function selectTerrain(char) {
    state.tool = { kind: "terrain", value: char };
    updateBrushButtons();
  }

  function selectFaction(faction) {
    state.selectedFaction = faction;
    state.tool = { kind: "unit" };
    updateBrushButtons();
  }

  function selectUnitType(type) {
    state.selectedUnitType = type;
    state.tool = { kind: "unit" };
    updateBrushButtons();
  }

  function selectUnitErase() {
    state.tool = { kind: "unit-erase" };
    updateBrushButtons();
  }

  function render({ fit = false } = {}) {
    const oldView = { ...state.view };
    const bounds = mapBounds();
    state.view.bounds = bounds;
    els.svg.innerHTML = "";
    els.svg.classList.toggle("preview-mode", state.mode === "preview");
    els.svg.classList.toggle("no-grid", !els.showGrid.checked);

    if (state.referenceImageUrl && els.showReference.checked) {
      const image = document.createElementNS(SVG_NS, "image");
      image.setAttribute("href", state.referenceImageUrl);
      image.setAttribute("x", bounds.minX);
      image.setAttribute("y", bounds.minY);
      image.setAttribute("width", bounds.maxX - bounds.minX);
      image.setAttribute("height", bounds.maxY - bounds.minY);
      image.setAttribute("preserveAspectRatio", "xMidYMid slice");
      image.setAttribute("opacity", String(Number(els.imageOpacity.value) / 100));
      image.setAttribute("class", "reference-image");
      els.svg.appendChild(image);
    }

    const terrainGroup = document.createElementNS(SVG_NS, "g");
    terrainGroup.id = "terrainLayer";
    els.svg.appendChild(terrainGroup);

    const showCoordinateText = els.showCoords.checked && state.mode !== "preview" &&
      (state.width * state.height <= 3000 || state.view.zoom >= 2);

    for (const row of rowsNorthFirst()) {
      for (const col of cols()) {
        const char = state.terrain.get(key(col, row)) || ".";
        const poly = document.createElementNS(SVG_NS, "polygon");
        poly.setAttribute("points", hexCorners(col, row).map((p) => p.join(",")).join(" "));
        poly.setAttribute("fill", TERRAIN[char].color);
        poly.setAttribute("class", "hex-cell hex-outline");
        poly.dataset.col = col;
        poly.dataset.row = row;
        poly.addEventListener("pointerdown", onHexPointerDown);
        poly.addEventListener("pointerenter", onHexPointerEnter);
        poly.addEventListener("pointerup", endStroke);
        poly.addEventListener("pointermove", () => {
          els.cursorInfo.textContent = `col=${col} row=${row} · ${TERRAIN[state.terrain.get(key(col, row)) || "."].name}`;
        });
        terrainGroup.appendChild(poly);

        if (showCoordinateText) {
          const c = hexToPixel(col, row);
          const text = document.createElementNS(SVG_NS, "text");
          text.setAttribute("x", c.x);
          text.setAttribute("y", c.y + 1);
          text.setAttribute("class", "hex-coordinate");
          text.textContent = `${col},${row}`;
          terrainGroup.appendChild(text);
        }
      }
    }

    if (els.showFormations.checked) renderFormations();

    if (fit || !oldView.bounds) {
      resetView();
    } else {
      state.view.zoom = oldView.zoom;
      state.view.cx = oldView.cx;
      state.view.cy = oldView.cy;
      applyViewBox();
    }
    updateStats();
    validate(false);
  }

  function slotAt(col, row) {
    for (const faction of Object.keys(FACTIONS)) {
      const index = state.formations[faction].findIndex(([c, r]) => c === col && r === row);
      if (index >= 0) return { faction, index, slot: state.formations[faction][index] };
    }
    return null;
  }

  function appendFormationMarker(group, faction, col, row, unitType) {
    const c = hexToPixel(col, row);
    const cellKey = key(col, row);
    const circle = document.createElementNS(SVG_NS, "circle");
    circle.setAttribute("cx", c.x);
    circle.setAttribute("cy", c.y);
    circle.setAttribute("r", HEX_SIZE * 0.34);
    circle.setAttribute("fill", FACTIONS[faction].color);
    circle.setAttribute("class", "formation-marker");
    circle.dataset.cell = cellKey;
    group.appendChild(circle);

    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", c.x);
    text.setAttribute("y", c.y + 1);
    text.setAttribute("class", "formation-label");
    text.dataset.cell = cellKey;
    text.textContent = UNIT_TYPES[unitType]?.short || "I";
    group.appendChild(text);

    const title = document.createElementNS(SVG_NS, "title");
    title.textContent = `${FACTIONS[faction].label} ${UNIT_TYPES[unitType]?.label || unitType} @ (${col},${row})`;
    circle.appendChild(title);
  }

  function slotAt(col, row) {
    for (const faction of Object.keys(FACTIONS)) {
      const index = state.formations[faction].findIndex(([c, r]) => c === col && r === row);
      if (index >= 0) return { faction, index, slot: state.formations[faction][index] };
    }
    return null;
  }

  function refreshFormationMarker(col, row) {
    if (!els.showFormations.checked) return;
    const group = els.svg.querySelector("#formationLayer");
    if (!group) return;
    const cellKey = key(col, row);
    group.querySelectorAll(`[data-cell="${cellKey}"]`).forEach((node) => node.remove());
    const found = slotAt(col, row);
    if (found) appendFormationMarker(group, found.faction, col, row, found.slot[2] || "infantry");
  }

  function renderFormations() {
    const group = document.createElementNS(SVG_NS, "g");
    group.id = "formationLayer";
    els.svg.appendChild(group);
    for (const [faction, cells] of Object.entries(state.formations)) {
      for (const [col, row, unitType = "infantry"] of cells) {
        if (!inBounds(col, row)) continue;
        appendFormationMarker(group, faction, col, row, unitType);
      }
    }
  }

  function shouldPan(evt) {
    return evt.button === 1 || state.spaceDown;
  }

  function onHexPointerDown(evt) {
    if (shouldPan(evt)) return;
    if (state.mode !== "edit" || evt.button !== 0) return;
    evt.preventDefault();
    state.strokeActive = true;
    state.strokeTouched.clear();
    checkpoint();
    applyTool(Number(evt.currentTarget.dataset.col), Number(evt.currentTarget.dataset.row));
  }

  function onHexPointerEnter(evt) {
    if (!state.strokeActive || state.mode !== "edit") return;
    applyTool(Number(evt.currentTarget.dataset.col), Number(evt.currentTarget.dataset.row), false);
  }

  function endStroke() {
    if (!state.strokeActive) return;
    state.strokeActive = false;
    state.strokeTouched.clear();
    updateStats();
    validate(false);
  }

  function removeSlotAt(col, row) {
    for (const faction of Object.keys(FACTIONS)) {
      state.formations[faction] = state.formations[faction].filter(([c, r]) => c !== col || r !== row);
    }
  }

  function applyTool(col, row, rerender = true) {
    const cellKey = key(col, row);
    if (state.strokeTouched.has(cellKey)) return;
    state.strokeTouched.add(cellKey);

    if (state.tool.kind === "terrain") {
      state.terrain.set(cellKey, state.tool.value);
      const poly = els.svg.querySelector(`polygon[data-col="${col}"][data-row="${row}"]`);
      if (poly) poly.setAttribute("fill", TERRAIN[state.tool.value].color);
    } else if (state.tool.kind === "unit-erase") {
      removeSlotAt(col, row);
      refreshFormationMarker(col, row);
    } else if (state.tool.kind === "unit") {
      removeSlotAt(col, row);
      state.formations[state.selectedFaction].push([col, row, state.selectedUnitType]);
      refreshFormationMarker(col, row);
    }

    if (rerender) {
      updateStats();
      validate(false);
    }
  }

  function unitMixForFaction(unitMix, faction) {
    if (unitMix == null) return null;
    if (Array.isArray(unitMix)) return unitMix;
    if (typeof unitMix === "object") return unitMix[faction] || null;
    return null;
  }

  function mixTemplate(counts) {
    if (!Array.isArray(counts) || counts.length !== 3) return [];
    const values = ["infantry", "archer", "cavalry"];
    const out = [];
    for (let i = 0; i < 3; i++) {
      const n = Math.max(0, Number(counts[i]) || 0);
      for (let j = 0; j < n; j++) out.push(values[i]);
    }
    return out;
  }

  function normalizeFormationCells(cells, unitMix, faction) {
    const template = mixTemplate(unitMixForFaction(unitMix, faction));
    let cursor = 0;
    return (cells || []).map((cell) => {
      const col = Number(cell?.col ?? cell?.[0]);
      const row = Number(cell?.row ?? cell?.[1]);
      const explicit = String(cell?.type ?? cell?.[2] ?? "").trim().toLowerCase();
      let type;
      if (explicit) {
        if (!UNIT_TYPES[explicit]) throw new Error(`Unknown unit type '${explicit}' at (${col},${row}).`);
        type = explicit;
      } else {
        type = template.length ? template[cursor % template.length] : "infantry";
        cursor += 1;
      }
      return [col, row, type];
    });
  }

  function mapToDocument() {
    const doc = {
      id: state.id.trim() || "untitled",
      name: state.name.trim() || "Untitled Map",
      width: state.width,
      height: state.height,
      coordinate_system: "centered",
      terrain: rowsNorthFirst().map((row) => cols().map((col) => state.terrain.get(key(col, row)) || ".").join("")),
      formations: Object.fromEntries(Object.entries(state.formations).map(([faction, cells]) => [
        faction,
        cells.map(([col, row, type = "infantry"]) => [col, row, type]),
      ])),
    };
    // Preserve imported mix metadata for round trips. Explicit v2 slot types are authoritative.
    if (state.unitMix != null) doc.unit_mix = JSON.parse(JSON.stringify(state.unitMix));
    return doc;
  }

  function loadDocument(doc, { checkpointBefore = true } = {}) {
    if (!doc || !Number.isInteger(Number(doc.width)) || !Number.isInteger(Number(doc.height)) || !Array.isArray(doc.terrain)) {
      throw new Error("Invalid STAR map JSON: width, height and terrain are required.");
    }
    const width = Number(doc.width);
    const height = Number(doc.height);
    if (!validSize(width) || !validSize(height)) {
      throw new Error(`Map dimensions must be odd numbers between 5 and ${MAX_MAP_SIZE}.`);
    }
    if (doc.terrain.length !== height || doc.terrain.some((row) => typeof row !== "string" || row.length !== width)) {
      throw new Error("Terrain dimensions do not match width/height.");
    }
    if (checkpointBefore) checkpoint();
    state.width = width;
    state.height = height;
    state.id = String(doc.id || "untitled");
    state.name = String(doc.name || state.id);
    state.unitMix = Array.isArray(doc.unit_mix) || (doc.unit_mix && typeof doc.unit_mix === "object")
      ? JSON.parse(JSON.stringify(doc.unit_mix))
      : null;
    state.terrain = new Map();
    const parsedRows = rowsNorthFirst();
    const parsedCols = cols();
    for (let i = 0; i < height; i++) {
      for (let j = 0; j < width; j++) {
        const char = doc.terrain[i][j];
        if (!TERRAIN[char]) throw new Error(`Unknown terrain '${char}' at row ${i}, col ${j}.`);
        state.terrain.set(key(parsedCols[j], parsedRows[i]), char);
      }
    }
    state.formations = { wei: [], shu: [], wu: [] };
    for (const faction of Object.keys(FACTIONS)) {
      state.formations[faction] = normalizeFormationCells(doc.formations?.[faction] || [], state.unitMix, faction);
    }
    syncInputs();
    render({ fit: true });
  }

  function downloadJson() {
    state.id = els.mapId.value.trim() || "untitled";
    state.name = els.mapName.value.trim() || state.id;
    const doc = mapToDocument();
    const blob = new Blob([JSON.stringify(doc, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${doc.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function saveLocal() {
    state.id = els.mapId.value.trim() || "untitled";
    state.name = els.mapName.value.trim() || state.id;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(mapToDocument()));
    flash($("saveLocalBtn"), "Saved");
  }

  function loadLocal() {
    const raw = localStorage.getItem(STORAGE_KEY) || localStorage.getItem(LEGACY_STORAGE_KEY);
    if (!raw) return alert("No locally saved STAR map was found.");
    try { loadDocument(JSON.parse(raw)); }
    catch (err) { alert(err.message); }
  }

  function flash(btn, text) {
    const original = btn.textContent;
    btn.textContent = text;
    setTimeout(() => { btn.textContent = original; }, 900);
  }

  function resizeMap() {
    const width = Number(els.mapWidth.value);
    const height = Number(els.mapHeight.value);
    if (!validSize(width) || !validSize(height)) {
      alert(`Use odd map dimensions between 5 and ${MAX_MAP_SIZE}.`);
      return;
    }

    checkpoint();
    const previousTerrain = new Map(state.terrain);
    const previousFormations = JSON.parse(JSON.stringify(state.formations));
    state.width = width;
    state.height = height;
    state.id = els.mapId.value.trim() || "untitled";
    state.name = els.mapName.value.trim() || state.id;
    initializeTerrain(".");
    for (const [cellKey, char] of previousTerrain) {
      const [col, row] = cellKey.split(",").map(Number);
      if (inBounds(col, row)) state.terrain.set(cellKey, char);
    }
    state.formations = { wei: [], shu: [], wu: [] };
    for (const faction of Object.keys(FACTIONS)) {
      state.formations[faction] = previousFormations[faction].filter(([c, r]) => inBounds(c, r));
    }
    render({ fit: true });
  }

  function validSize(n) {
    return Number.isInteger(n) && n >= 5 && n <= MAX_MAP_SIZE && n % 2 === 1;
  }

  function terrainFromRgb(r, g, b) {
    const mx = Math.max(r, g, b);
    const mn = Math.min(r, g, b);
    const sat = mx === 0 ? 0 : (mx - mn) / mx;
    if (b > r + 25 && b > g + 10) return "~";
    if (g > r + 15 && g > b + 15 && g < 140) return "F";
    if (mx < 70) return "M";
    if (r > 80 && r < 180 && g > 60 && g < 140 && b < g && sat > 0.2) return "H";
    if (mx > 160 && sat < 0.25) return "C";
    return ".";
  }

  function pointInPolygon(x, y, points) {
    let inside = false;
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
      const [xi, yi] = points[i];
      const [xj, yj] = points[j];
      const intersects = ((yi > y) !== (yj > y)) &&
        (x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-12) + xi);
      if (intersects) inside = !inside;
    }
    return inside;
  }

  function generateFromImage() {
    if (!state.referenceImage) return;
    checkpoint();
    const image = state.referenceImage;
    const canvas = els.sampleCanvas;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    const maxDim = 1200;
    const scaleDown = Math.min(1, maxDim / Math.max(image.naturalWidth, image.naturalHeight));
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scaleDown));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scaleDown));
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);

    const bounds = mapBounds();
    const gridW = bounds.maxX - bounds.minX;
    const gridH = bounds.maxY - bounds.minY;
    const marginX = canvas.width * 0.04;
    const marginY = canvas.height * 0.04;
    const usableW = canvas.width - 2 * marginX;
    const usableH = canvas.height - 2 * marginY;
    const scale = Math.min(usableW / gridW, usableH / gridH);
    const drawnW = gridW * scale;
    const drawnH = gridH * scale;
    const originX = (canvas.width - drawnW) / 2;
    const originY = (canvas.height - drawnH) / 2;
    const worldToImage = (x, y) => [originX + (x - bounds.minX) * scale, originY + (y - bounds.minY) * scale];
    const sampleStep = Math.max(2, Math.round(HEX_SIZE * scale / 6));

    for (const row of rowsNorthFirst()) {
      for (const col of cols()) {
        const polygon = hexCorners(col, row).map(([x, y]) => worldToImage(x, y));
        const xs = polygon.map((p) => p[0]);
        const ys = polygon.map((p) => p[1]);
        const votes = new Map();
        for (let x = Math.floor(Math.min(...xs)); x <= Math.ceil(Math.max(...xs)); x += sampleStep) {
          for (let y = Math.floor(Math.min(...ys)); y <= Math.ceil(Math.max(...ys)); y += sampleStep) {
            if (x < 0 || y < 0 || x >= canvas.width || y >= canvas.height || !pointInPolygon(x + 0.5, y + 0.5, polygon)) continue;
            const idx = (y * canvas.width + x) * 4;
            const char = terrainFromRgb(pixels.data[idx], pixels.data[idx+1], pixels.data[idx+2]);
            votes.set(char, (votes.get(char) || 0) + 1);
          }
        }
        let best = ".";
        let bestCount = -1;
        for (const [char, count] of votes.entries()) {
          if (count > bestCount) { best = char; bestCount = count; }
        }
        state.terrain.set(key(col, row), best);
      }
    }
    render();
  }

  function importReferenceImage(file) {
    if (!file) return;
    if (state.referenceImageUrl) URL.revokeObjectURL(state.referenceImageUrl);
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      state.referenceImage = image;
      state.referenceImageUrl = url;
      els.imageControls.classList.remove("disabled");
      render();
    };
    image.onerror = () => { URL.revokeObjectURL(url); alert("Could not load image."); };
    image.src = url;
  }

  function clearReferenceImage() {
    if (state.referenceImageUrl) URL.revokeObjectURL(state.referenceImageUrl);
    state.referenceImage = null;
    state.referenceImageUrl = null;
    els.imageFileInput.value = "";
    els.imageControls.classList.add("disabled");
    render();
  }

  function shortestPathDistance(starts, targets) {
    const targetSet = new Set(targets.map(([c, r]) => key(c, r)));
    const queue = [];
    const dist = new Map();
    for (const [c, r] of starts) {
      const k = key(c, r);
      queue.push([c, r]);
      dist.set(k, 0);
    }
    let head = 0;
    while (head < queue.length) {
      const [c, r] = queue[head++];
      const d = dist.get(key(c, r));
      if (targetSet.has(key(c, r))) return d;
      for (const [nc, nr] of hexNeighbors(c, r)) {
        const nk = key(nc, nr);
        if (!inBounds(nc, nr) || dist.has(nk) || state.terrain.get(nk) === "~") continue;
        dist.set(nk, d + 1);
        queue.push([nc, nr]);
      }
    }
    return null;
  }

  function formationCenter(cells) {
    if (!cells.length) return null;
    const avgC = cells.reduce((s, c) => s + c[0], 0) / cells.length;
    const avgR = cells.reduce((s, c) => s + c[1], 0) / cells.length;
    return cells.reduce((best, cell) => {
      const score = Math.abs(cell[0] - avgC) + Math.abs(cell[1] - avgR);
      return !best || score < best.score ? { cell, score } : best;
    }, null).cell;
  }

  function validate(showAlert = false) {
    const items = [];
    const push = (level, text) => items.push({ level, text });
    const expectedCells = state.width * state.height;
    push(state.terrain.size === expectedCells ? "ok" : "error", `${state.terrain.size}/${expectedCells} map cells defined.`);

    const occupiedSpawn = new Map();
    for (const [faction, cells] of Object.entries(state.formations)) {
      if (!cells.length) push("warn", `${FACTIONS[faction].label} has no unit slots.`);
      else push("ok", `${FACTIONS[faction].label} has ${cells.length} unit slots.`);
      for (const [c, r, type] of cells) {
        if (!inBounds(c, r)) push("error", `${FACTIONS[faction].label} unit (${c},${r}) is off-map.`);
        else if (state.terrain.get(key(c, r)) === "~") push("error", `${FACTIONS[faction].label} unit (${c},${r}) is on water.`);
        if (!UNIT_TYPES[type]) push("error", `${FACTIONS[faction].label} unit (${c},${r}) has unknown type '${type}'.`);
        const k = key(c, r);
        if (occupiedSpawn.has(k) && occupiedSpawn.get(k) !== faction) push("error", `Formation overlap at (${c},${r}).`);
        occupiedSpawn.set(k, faction);
      }
    }

    const active = Object.entries(state.formations).filter(([, cells]) => cells.length > 0);
    for (let i = 0; i < active.length; i++) {
      for (let j = i + 1; j < active.length; j++) {
        const [fa, a] = active[i];
        const [fb, b] = active[j];
        const distance = shortestPathDistance(a, b);
        if (distance === null) push("error", `${FACTIONS[fa].label} cannot reach ${FACTIONS[fb].label} without crossing water.`);
        else push("ok", `${FACTIONS[fa].label} ↔ ${FACTIONS[fb].label} passable route: ${distance} hex steps.`);
        const ca = formationCenter(a);
        const cb = formationCenter(b);
        if (ca && cb) {
          const geometric = hexDistance(ca, cb);
          if (geometric <= 3) push("warn", `${FACTIONS[fa].label} and ${FACTIONS[fb].label} formations start only ${geometric} hexes apart.`);
        }
      }
    }

    const errors = items.filter((x) => x.level === "error").length;
    const warnings = items.filter((x) => x.level === "warn").length;
    els.validationSummary.textContent = errors ? `${errors} error(s), ${warnings} warning(s)` : warnings ? `Valid with ${warnings} warning(s)` : "Map is valid";
    els.validationSummary.style.borderColor = errors ? "var(--danger)" : warnings ? "var(--warn)" : "var(--ok)";
    els.validationList.innerHTML = items.map((item) => `<div class="validation-item ${item.level}">${item.level === "ok" ? "✓" : item.level === "warn" ? "⚠" : "✕"} ${item.text}</div>`).join("");
    if (showAlert && errors) alert("Validation found blocking errors. See the Validation panel.");
    return { errors, warnings, items };
  }

  function countTypes(cells) {
    const counts = { infantry: 0, archer: 0, cavalry: 0 };
    for (const [, , type = "infantry"] of cells) counts[type] = (counts[type] || 0) + 1;
    return counts;
  }

  function updateStats() {
    const counts = Object.fromEntries(Object.keys(TERRAIN).map((c) => [c, 0]));
    for (const char of state.terrain.values()) counts[char] = (counts[char] || 0) + 1;
    const rows = [
      ["Cells", state.width * state.height],
      ["Passable", state.width * state.height - counts["~"]],
      ["Water", counts["~"]],
    ];
    for (const faction of Object.keys(FACTIONS)) {
      const t = countTypes(state.formations[faction]);
      rows.push([`${FACTIONS[faction].label} units`, state.formations[faction].length]);
      rows.push([`↳ I / A / C`, `${t.infantry} / ${t.archer} / ${t.cavalry}`]);
    }
    els.mapStats.innerHTML = rows.map(([k, v]) => `<span>${k}</span><strong>${v}</strong>`).join("");
  }

  function startPan(evt) {
    if (!shouldPan(evt)) return;
    evt.preventDefault();
    state.panActive = true;
    state.panPointerId = evt.pointerId;
    state.panLastX = evt.clientX;
    state.panLastY = evt.clientY;
    els.svg.setPointerCapture?.(evt.pointerId);
    els.svg.classList.add("panning");
  }

  function movePan(evt) {
    if (!state.panActive || evt.pointerId !== state.panPointerId) return;
    const rect = els.svg.getBoundingClientRect();
    const vb = els.svg.viewBox.baseVal;
    const dx = evt.clientX - state.panLastX;
    const dy = evt.clientY - state.panLastY;
    state.view.cx -= dx * (vb.width / Math.max(1, rect.width));
    state.view.cy -= dy * (vb.height / Math.max(1, rect.height));
    state.panLastX = evt.clientX;
    state.panLastY = evt.clientY;
    applyViewBox();
  }

  function endPan(evt) {
    if (!state.panActive) return;
    if (evt && evt.pointerId != null && state.panPointerId != null && evt.pointerId !== state.panPointerId) return;
    state.panActive = false;
    state.panPointerId = null;
    els.svg.classList.remove("panning");
  }

  function wireEvents() {
    document.querySelectorAll("[data-faction]").forEach((b) => b.addEventListener("click", () => selectFaction(b.dataset.faction)));
    document.querySelectorAll("[data-unit-type]").forEach((b) => b.addEventListener("click", () => selectUnitType(b.dataset.unitType)));
    $("eraseUnitBtn").addEventListener("click", selectUnitErase);
    $("undoBtn").addEventListener("click", undo);
    $("redoBtn").addEventListener("click", redo);
    $("applySizeBtn").addEventListener("click", resizeMap);
    $("exportJsonBtn").addEventListener("click", () => { validate(false); downloadJson(); });
    $("saveLocalBtn").addEventListener("click", saveLocal);
    $("loadLocalBtn").addEventListener("click", loadLocal);
    $("importJsonBtn").addEventListener("click", () => els.jsonFileInput.click());
    els.jsonFileInput.addEventListener("change", async () => {
      const file = els.jsonFileInput.files?.[0];
      if (!file) return;
      try { loadDocument(JSON.parse(await file.text())); }
      catch (err) { alert(err.message); }
      els.jsonFileInput.value = "";
    });

    $("imageImportBtn").addEventListener("click", () => els.imageFileInput.click());
    els.imageFileInput.addEventListener("change", () => importReferenceImage(els.imageFileInput.files?.[0]));
    $("generateFromImageBtn").addEventListener("click", generateFromImage);
    $("clearImageBtn").addEventListener("click", clearReferenceImage);
    els.imageOpacity.addEventListener("input", render);
    els.showReference.addEventListener("change", render);

    els.showCoords.addEventListener("change", render);
    els.showFormations.addEventListener("change", render);
    els.showGrid.addEventListener("change", render);
    $("editModeBtn").addEventListener("click", () => setMode("edit"));
    $("previewModeBtn").addEventListener("click", () => setMode("preview"));
    $("validateBtn").addEventListener("click", () => validate(true));
    $("zoomOutBtn").addEventListener("click", () => setZoom(state.view.zoom / 1.35));
    $("zoomInBtn").addEventListener("click", () => setZoom(state.view.zoom * 1.35));
    $("zoomFitBtn").addEventListener("click", resetView);

    els.mapId.addEventListener("input", () => { state.id = els.mapId.value; });
    els.mapName.addEventListener("input", () => { state.name = els.mapName.value; });

    $("newMapBtn").addEventListener("click", () => $("newMapDialog").showModal());
    $("confirmNewMap").addEventListener("click", () => {
      state.undo.length = 0;
      state.redo.length = 0;
      state.width = 15;
      state.height = 15;
      state.id = "untitled";
      state.name = "Untitled Map";
      state.unitMix = null;
      state.formations = { wei: [], shu: [], wu: [] };
      initializeTerrain(".");
      syncInputs();
      updateHistoryButtons();
      render({ fit: true });
    });

    els.svg.addEventListener("wheel", (evt) => {
      evt.preventDefault();
      const anchor = clientToWorld(evt.clientX, evt.clientY);
      const factor = evt.deltaY < 0 ? 1.18 : 1 / 1.18;
      setZoom(state.view.zoom * factor, anchor);
    }, { passive: false });
    els.svg.addEventListener("pointerdown", startPan, true);
    els.svg.addEventListener("pointermove", movePan, true);
    els.svg.addEventListener("pointerup", endPan, true);
    els.svg.addEventListener("pointercancel", endPan, true);
    window.addEventListener("pointerup", (evt) => { endStroke(); endPan(evt); });

    document.addEventListener("keydown", (evt) => {
      const mod = evt.ctrlKey || evt.metaKey;
      if (evt.code === "Space" && !isTypingTarget(evt.target)) {
        state.spaceDown = true;
        els.svg.classList.add("pan-ready");
        evt.preventDefault();
      }
      if (mod && evt.key.toLowerCase() === "z" && !evt.shiftKey) { evt.preventDefault(); undo(); }
      if (mod && (evt.key.toLowerCase() === "y" || (evt.key.toLowerCase() === "z" && evt.shiftKey))) { evt.preventDefault(); redo(); }
    });
    document.addEventListener("keyup", (evt) => {
      if (evt.code === "Space") {
        state.spaceDown = false;
        els.svg.classList.remove("pan-ready");
        endPan(evt);
      }
    });
  }

  function isTypingTarget(target) {
    const tag = target?.tagName?.toLowerCase();
    return tag === "input" || tag === "textarea" || target?.isContentEditable;
  }

  function setMode(mode) {
    state.mode = mode;
    $("editModeBtn").classList.toggle("active", mode === "edit");
    $("previewModeBtn").classList.toggle("active", mode === "preview");
    render();
  }

  function boot() {
    buildPalette();
    initializeTerrain(".");
    wireEvents();
    syncInputs();
    updateHistoryButtons();
    updateBrushButtons();
    render({ fit: true });
  }

  boot();
})();
