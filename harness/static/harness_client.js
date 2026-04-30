(function () {
  if (window.__ZERO_MOD_HARNESS__) {
    return;
  }

  window.__ZERO_MOD_HARNESS__ = {
    version: 1,
    events: [],
    snapshots: [],
    console: [],
    errors: []
  };

  const panel = document.createElement("div");
  panel.id = "__zero_mod_harness_panel";
  panel.textContent = "HARNESS idle";
  panel.style.position = "fixed";
  panel.style.top = "8px";
  panel.style.right = "8px";
  panel.style.zIndex = "2147483647";
  panel.style.padding = "6px 8px";
  panel.style.background = "#111";
  panel.style.color = "#fff";
  panel.style.font = "12px system-ui, sans-serif";
  panel.style.border = "1px solid #555";
  panel.style.borderRadius = "4px";

  window.addEventListener("DOMContentLoaded", () => {
    document.body.appendChild(panel);
  });
})();
