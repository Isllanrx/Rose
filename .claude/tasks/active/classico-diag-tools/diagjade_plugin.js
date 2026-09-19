/**
 * @name Rose-DiagJade
 * @description Temporary read-only probe for the Rift Classic skin carousel (#68).
 * Install as %LOCALAPPDATA%\Rose\Pengu Loader\plugins\ROSE-DiagJade\index.js AFTER Rose starts
 * (Rose re-copies the Pengu folder on startup). Output lands in rose_*.log as [DiagJade]. Remove after use.
 */
(() => {
  const SOURCE = "DiagJade";
  let last = null;

  function send(message, data) {
    const payload = { type: "chroma-log", source: SOURCE, level: "info", message, data: { t: Date.now(), ...data } };
    try {
      if (window.__roseBridge) window.__roseBridge.send(payload);
    } catch (e) {
      console.warn("[DiagJade] send failed", e);
    }
  }

  function snapshot() {
    const pane = document.querySelector(".skins-pane");
    if (!pane) return null;
    const center = pane.querySelector(".skins-pane__skin-card--center-tile");
    return {
      title: (pane.querySelector(".skins-pane__skin-title")?.textContent || "").trim(),
      subtitle: (pane.querySelector(".skins-pane__sub-title")?.textContent || "").trim(),
      centerLocked: !!center?.querySelector(".skins-pane__locked-overlay"),
      selectedCardPresent: !!pane.querySelector(".skins-pane__skin-card--selected-skin"),
      cards: pane.querySelectorAll(".skins-pane__skin-card:not(.skins-pane__skin-card--placeholder)").length,
      leftDisabled: !!pane.querySelector(".skins-pane__arrow--left.skins-pane__arrow--disabled"),
      rightDisabled: !!pane.querySelector(".skins-pane__arrow--right.skins-pane__arrow--disabled"),
    };
  }

  function poll() {
    const s = snapshot();
    const key = JSON.stringify(s);
    if (key !== last) {
      last = key;
      send(s ? "pane" : "pane-absent", s || {});
    }
  }

  document.addEventListener(
    "click",
    (e) => {
      const el = e.target && e.target.closest && e.target.closest(
        ".skins-pane__arrow, .skins-pane__skin-card, .skins-pane__carousel-pip-square, .skins-pane__locked-icon"
      );
      if (!el) return;
      send("click", { cls: String(el.className).replace(/\s+/g, " ").trim(), before: snapshot()?.title || "" });
    },
    true
  );

  setInterval(poll, 100);
  console.log("[DiagJade] loaded");
})();
