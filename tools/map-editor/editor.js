(() => {
  "use strict";

  const SVG_NS = "http://www.w3.org/2000/svg";
  const HEX_SIZE = 28;
  const SQRT3 = Math.sqrt(3);
  const STORAGE_KEY = "star-map-editor-v1.5";
  const EXPECTED_FORMATION_CELLS = 5;

  const TERRAIN = {
    ".": { name: "Plain", color: "#90ee90", movement: 1 },
    "~": { name: "Water", color: "#87cefa", movement: 999 },
    "F": { name: "Forest", color: "#228b22", movement: 2 },
    "H": { name: "Hill", color: "#a0522d", movement: 2 },
    "M": { name: "Mountain", color: "#8b4513", movement: 3 },
    "C": { name: "Urban", color: "#a9a9a9", movement: 2 },
  };

  const FACTIONS = {
    wei: { label: "Wei", color: "#4f79ff" },
    shu: { label: "Shu", color: "#ff5f5f" },
    wu: { label: "Wu", color: "#46c878" },
  };

  const state = {
    id: "untitled",
    name: "Untitled Map",
    width: 15,
    height: 15,
    terrain: new Map(),
    formations: { wei: [], shu: [], wu: [] },
    tool: { kind: "terrain", value: "." },
    mode: "edit",
    referenceImage: null,
    referenceImageUrl: null,
    undo: [],
    redo: [],
    strokeActive: false,
    strokeTouched: new Set(),
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
    };
  }

  function restore(snap) {
    state.id = snap.id;
    state.name = snap.name;
    state.width = snap.width;
    state.height = snap.height;
    state.terrain = new Map(snap.terrain);
    state.formations = JSON.parse(JSON.stringify(snap.formations));
    syncInputs();
    render();
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

  function selectTerrain(char) {
    state.tool = { kind: "terrain", value: char };
    document.querySelectorAll("[data-terrain]").forEach((b) => b.classList.toggle("active", b.dataset.terrain === char));
    document.querySelectorAll("[data-faction]").forEach((b) => b.classList.remove("active"));
  }

  function selectFormation(value) {
    state.tool = { kind: "formation", value };
    document.querySelectorAll("[data-faction]").forEach((b) => b.classList.toggle("active", b.dataset.faction === value));
    document.querySelectorAll("[data-terrain]").forEach((b) => b.classList.remove("active"));
  }

  function mapBounds() {
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

  function render() {
    const bounds = mapBounds();
    const vbW = bounds.maxX - bounds.minX;
    const vbH = bounds.maxY - bounds.minY;
    els.svg.setAttribute("viewBox", `${bounds.minX} ${bounds.minY} ${vbW} ${vbH}`);
    els.svg.innerHTML = "";
    els.svg.classList.toggle("preview-mode", state.mode === "preview");
    els.svg.classList.toggle("no-grid", !els.showGrid.checked);

    if (state.referenceImageUrl && els.showReference.checked) {
      const image = document.createElementNS(SVG_NS, "image");
      image.setAttribute("href", state.referenceImageUrl);
      image.setAttribute("x", bounds.minX);
      image.setAttribute("y", bounds.minY);
      image.setAttribute("width", vbW);
      image.setAttribute("height", vbH);
      image.setAttribute("preserveAspectRatio", "xMidYMid slice");
      image.setAttribute("opacity", String(Number(els.imageOpacity.value) / 100));
      image.setAttribute("class", "reference-image");
      els.svg.appendChild(image);
    }

    const terrainGroup = document.createElementNS(SVG_NS, "g");
    terrainGroup.id = "terrainLayer";
    els.svg.appendChild(terrainGroup);

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
          els.cursorInfo.textContent = `col=${col} row=${row} · ${TERRAIN[char].name}`;
        });
        terrainGroup.appendChild(poly);

        if (els.showCoords.checked && state.mode !== "preview") {
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
    updateStats();
    validate(false);
  }

  function renderFormations() {
    const group = document.createElementNS(SVG_NS, "g");
    group.id = "formationLayer";
    els.svg.appendChild(group);
    for (const [faction, cells] of Object.entries(state.formations)) {
      for (const [col, row] of cells) {
        if (!inBounds(col, row)) continue;
        const c = hexToPixel(col, row);
        const circle = document.createElementNS(SVG_NS, "circle");
        circle.setAttribute("cx", c.x);
        circle.setAttribute("cy", c.y);
        circle.setAttribute("r", HEX_SIZE * 0.33);
        circle.setAttribute("fill", FACTIONS[faction].color);
        circle.setAttribute("class", "formation-marker");
        group.appendChild(circle);
        const text = document.createElementNS(SVG_NS, "text");
        text.setAttribute("x", c.x);
        text.setAttribute("y", c.y + 1);
        text.setAttribute("class", "formation-label");
        text.textContent = faction[0].toUpperCase();
        group.appendChild(text);
      }
    }
  }

  function onHexPointerDown(evt) {
    if (state.mode !== "edit") return;
    evt.preventDefault();
    state.strokeActive = true;
    state.strokeTouched.clear();
    checkpoint();
    applyTool(Number(evt.currentTarget.dataset.col), Number(evt.currentTarget.dataset.row));
  }

  function onHexPointerEnter(evt) {
    if (!state.strokeActive || state.mode !== "edit") return;
    if (state.tool.kind === "terrain") {
      applyTool(Number(evt.currentTarget.dataset.col), Number(evt.currentTarget.dataset.row), false);
    }
  }

  function endStroke() {
    if (!state.strokeActive) return;
    state.strokeActive = false;
    state.strokeTouched.clear();
    render();
  }

  window.addEventListener("pointerup", endStroke);

  function applyTool(col, row, rerender = true) {
    const cellKey = key(col, row);
    if (state.strokeTouched.has(cellKey)) return;
    state.strokeTouched.add(cellKey);

    if (state.tool.kind === "terrain") {
      state.terrain.set(cellKey, state.tool.value);
      const poly = els.svg.querySelector(`polygon[data-col="${col}"][data-row="${row}"]`);
      if (poly) poly.setAttribute("fill", TERRAIN[state.tool.value].color);
    } else {
      const target = state.tool.value;
      if (target === "erase") {
        for (const faction of Object.keys(FACTIONS)) {
          state.formations[faction] = state.formations[faction].filter(([c,r]) => c !== col || r !== row);
        }
      } else {
        const cells = state.formations[target];
        const exists = cells.some(([c,r]) => c === col && r === row);
        if (exists) {
          state.formations[target] = cells.filter(([c,r]) => c !== col || r !== row);
        } else {
          for (const faction of Object.keys(FACTIONS)) {
            state.formations[faction] = state.formations[faction].filter(([c,r]) => c !== col || r !== row);
          }
          state.formations[target].push([col, row]);
        }
      }
    }
    if (rerender) render();
  }

  function mapToDocument() {
    return {
      id: state.id.trim() || "untitled",
      name: state.name.trim() || "Untitled Map",
      width: state.width,
      height: state.height,
      coordinate_system: "centered",
      terrain: rowsNorthFirst().map((row) => cols().map((col) => state.terrain.get(key(col, row)) || ".").join("")),
      formations: Object.fromEntries(Object.entries(state.formations).map(([f, cells]) => [f, cells.map(([c,r]) => [c,r])])),
    };
  }

  function loadDocument(doc, { checkpointBefore = true } = {}) {
    if (!doc || !Number.isInteger(Number(doc.width)) || !Number.isInteger(Number(doc.height)) || !Array.isArray(doc.terrain)) {
      throw new Error("Invalid STAR map JSON: width, height and terrain are required.");
    }
    const width = Number(doc.width);
    const height = Number(doc.height);
    if (doc.terrain.length !== height || doc.terrain.some((row) => typeof row !== "string" || row.length !== width)) {
      throw new Error("Terrain dimensions do not match width/height.");
    }
    if (checkpointBefore) checkpoint();
    state.width = width;
    state.height = height;
    state.id = String(doc.id || "untitled");
    state.name = String(doc.name || state.id);
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
      const cells = doc.formations?.[faction] || [];
      state.formations[faction] = cells.map((cell) => [Number(cell[0]), Number(cell[1])]);
    }
    syncInputs();
    render();
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
    const raw = localStorage.getItem(STORAGE_KEY);
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
      alert("Use odd map dimensions between 5 and 51.");
      return;
    }
    checkpoint();
    state.width = width;
    state.height = height;
    state.id = els.mapId.value.trim() || "untitled";
    state.name = els.mapName.value.trim() || state.id;
    initializeTerrain(".");
    state.formations = { wei: [], shu: [], wu: [] };
    render();
  }

  function validSize(n) { return Number.isInteger(n) && n >= 5 && n <= 51 && n % 2 === 1; }

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
      const intersects = ((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-12) + xi);
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
    const targetSet = new Set(targets.map(([c,r]) => key(c,r)));
    const queue = [];
    const dist = new Map();
    for (const [c,r] of starts) {
      const k = key(c,r);
      queue.push([c,r]);
      dist.set(k, 0);
    }
    let head = 0;
    while (head < queue.length) {
      const [c,r] = queue[head++];
      const d = dist.get(key(c,r));
      if (targetSet.has(key(c,r))) return d;
      for (const [nc,nr] of hexNeighbors(c,r)) {
        const nk = key(nc,nr);
        if (!inBounds(nc,nr) || dist.has(nk) || state.terrain.get(nk) === "~") continue;
        dist.set(nk, d + 1);
        queue.push([nc,nr]);
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
      if (!cells.length) push("warn", `${FACTIONS[faction].label} has no formation cells.`);
      else if (cells.length === EXPECTED_FORMATION_CELLS) push("ok", `${FACTIONS[faction].label} has ${cells.length} formation cells.`);
      else push("warn", `${FACTIONS[faction].label} has ${cells.length} formation cells; current STAR default uses ${EXPECTED_FORMATION_CELLS}.`);

      for (const [c,r] of cells) {
        if (!inBounds(c,r)) push("error", `${FACTIONS[faction].label} formation (${c},${r}) is off-map.`);
        else if (state.terrain.get(key(c,r)) === "~") push("error", `${FACTIONS[faction].label} formation (${c},${r}) is on water.`);
        const k = key(c,r);
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

  function updateStats() {
    const counts = Object.fromEntries(Object.keys(TERRAIN).map((c) => [c, 0]));
    for (const char of state.terrain.values()) counts[char] = (counts[char] || 0) + 1;
    const rows = [
      ["Cells", state.width * state.height],
      ["Passable", state.width * state.height - counts["~"]],
      ["Water", counts["~"]],
      ["Forest", counts["F"]],
      ["Hill", counts["H"]],
      ["Mountain", counts["M"]],
      ["Urban", counts["C"]],
      ["Wei spawns", state.formations.wei.length],
      ["Shu spawns", state.formations.shu.length],
      ["Wu spawns", state.formations.wu.length],
    ];
    els.mapStats.innerHTML = rows.map(([k,v]) => `<span>${k}</span><strong>${v}</strong>`).join("");
  }

  function wireEvents() {
    document.querySelectorAll("[data-faction]").forEach((b) => b.addEventListener("click", () => selectFormation(b.dataset.faction)));
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
      state.formations = { wei: [], shu: [], wu: [] };
      initializeTerrain(".");
      syncInputs();
      updateHistoryButtons();
      render();
    });

    document.addEventListener("keydown", (evt) => {
      const mod = evt.ctrlKey || evt.metaKey;
      if (mod && evt.key.toLowerCase() === "z" && !evt.shiftKey) { evt.preventDefault(); undo(); }
      if (mod && (evt.key.toLowerCase() === "y" || (evt.key.toLowerCase() === "z" && evt.shiftKey))) { evt.preventDefault(); redo(); }
    });
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
    render();
  }

  boot();
})();
