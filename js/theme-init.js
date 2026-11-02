/*
 * Runs synchronously in <head>, before any stylesheet, so the first paint is
 * already in the right theme. Resolution order:
 *   ?theme=<id>&mode=<light|dark>  >  localStorage  >  prefers-color-scheme  >  neutral/light
 *
 * THEMES is the theme registry and the allowlist: a value from the URL or
 * from storage reaches the DOM only if it is one of these ids. Each id also
 * needs an @import in themes/index.css; sync-tokens.py fails if the two
 * lists disagree.
 */
(function () {
  var THEMES = [
    { id: "neutral", label: "Neutral" },
    { id: "bikencars", label: "Bikencars" },
    { id: "marquee", label: "Marquee" }
  ];
  var MODES = ["light", "dark"];
  var KEY_THEME = "mbds-theme";
  var KEY_MODE = "mbds-mode";

  var root = document.documentElement;

  function isTheme(v) { return THEMES.some(function (t) { return t.id === v; }); }
  function isMode(v) { return MODES.indexOf(v) > -1; }

  function read(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function write(key, value) {
    try { window.localStorage.setItem(key, value); return true; } catch (e) { return false; }
  }
  // First candidate that passes the allowlist, else null.
  function pick(candidates, valid) {
    for (var i = 0; i < candidates.length; i++) if (valid(candidates[i])) return candidates[i];
    return null;
  }

  var params = null;
  try { params = new URLSearchParams(window.location.search); } catch (e) { params = null; }

  var theme = pick([params && params.get("theme"), read(KEY_THEME)], isTheme) || THEMES[0].id;
  var mode = pick([params && params.get("mode"), read(KEY_MODE)], isMode);
  if (!mode) {
    var prefersDark = false;
    try { prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches; } catch (e) { prefersDark = false; }
    mode = prefersDark ? "dark" : "light";
  }

  root.setAttribute("data-theme", theme);
  root.setAttribute("data-mode", mode);

  window.MBDS = {
    themes: THEMES.map(function (t) { return { id: t.id, label: t.label }; }),
    modes: MODES.slice(),
    get: function () {
      return { theme: root.getAttribute("data-theme"), mode: root.getAttribute("data-mode") };
    },
    // Ignores any value outside the allowlist. Returns whether the choice was persisted.
    set: function (next) {
      if (next && isTheme(next.theme)) root.setAttribute("data-theme", next.theme);
      if (next && isMode(next.mode)) root.setAttribute("data-mode", next.mode);
      var current = this.get();
      var ok = write(KEY_THEME, current.theme) && write(KEY_MODE, current.mode);
      this.persisted = ok;
      document.dispatchEvent(new CustomEvent("mbds:themechange", { detail: current }));
      return ok;
    },
    persisted: true
  };
})();
