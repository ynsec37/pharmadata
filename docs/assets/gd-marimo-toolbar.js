// Hide the Visualize and Explore buttons in marimo table toolbars so only
// Columns and Export remain at the top-right. The buttons live inside
// marimo-table's shadow DOM, which light-DOM CSS cannot reach, so we inject a
// <style> into each table's shadow root. Tables are rendered inside same-origin
// iframes (marimo shortcode mode="iframe"), so we also reach through
// iframe.contentDocument. Served site-wide via include_in_header in
// great-docs.yml.
(function () {
  "use strict";

  var CSS =
    "div.ml-auto button:not([data-testid]){display:none!important}";

  function injectIntoDoc(doc) {
    if (!doc) return;
    doc.querySelectorAll("marimo-table").forEach(function (table) {
      var root = table.shadowRoot;
      if (!root) return;
      if (root.querySelector('style[data-toolbar-hide]')) return;
      var style = doc.createElement("style");
      style.setAttribute("data-toolbar-hide", "");
      style.textContent = CSS;
      root.appendChild(style);
    });
  }

  function scan() {
    injectIntoDoc(document);
    document.querySelectorAll("iframe").forEach(function (iframe) {
      try {
        injectIntoDoc(iframe.contentDocument);
      } catch (_e) {
        /* cross-origin or not yet loaded; ignore */
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", scan);
  } else {
    scan();
  }
  window.addEventListener("load", scan);

  // Tables are created/recreated when the dataset changes; keep scanning.
  var attempts = 0;
  var iv = setInterval(function () {
    scan();
    if (++attempts > 240) clearInterval(iv);
  }, 500);
})();
