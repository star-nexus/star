(() => {
  "use strict";

  // Canonical STAR map-editor faction palette.
  // The v2 core predates this corrected Shu/Wu mapping, so keep this small
  // presentation bridge next to it until the legacy v1.5 assets are retired.
  const COLORS = {
    Wei: "#4f79ff",
    Shu: "#ff5f5f",
    Wu: "#46c878",
  };

  function recolorTitle(title) {
    const marker = title?.parentElement;
    if (!marker?.classList?.contains("formation-marker")) return;
    const faction = String(title.textContent || "").split(" ", 1)[0];
    const color = COLORS[faction];
    if (color) marker.setAttribute("fill", color);
  }

  function recolor(root = document) {
    if (root.matches?.("circle.formation-marker > title")) recolorTitle(root);
    root.querySelectorAll?.("circle.formation-marker > title").forEach(recolorTitle);
  }

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType === Node.ELEMENT_NODE) recolor(node);
      }
    }
  });

  recolor();
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
