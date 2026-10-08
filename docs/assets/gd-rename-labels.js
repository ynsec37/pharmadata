// Rename great-docs' auto-generated Reference sidebar group "Constants" to
// "Datasets". The package classifies module-level `Final[DataFrame]` datasets as
// constants and hardcodes that English label (core.py:8733) with no config
// toggle, so we rewrite the rendered sidebar text. Each category title is a
// <span class="menu-text">, matched by its exact text so other groups are left
// alone. Served from docs/assets/ (great-docs resolves source paths relative to
// docs/); great-docs ships it to _site/assets/, and it is wired site-wide via
// include_in_header in great-docs.yml.
(function () {
  "use strict";

  var RENAME = { Constants: "Datasets" };

  function apply() {
    document.querySelectorAll(".menu-text").forEach(function (el) {
      var text = (el.textContent || "").trim();
      if (Object.prototype.hasOwnProperty.call(RENAME, text)) {
        el.textContent = RENAME[text];
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }
  // The sidebar is server-rendered, but re-run after load in case a widget
  // (sidebar-filter) rebuilds it and reintroduces the original label.
  window.addEventListener("load", apply);
})();
