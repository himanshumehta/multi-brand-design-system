/*
 * Runs synchronously in <head>, before any stylesheet, so the first paint is
 * already in the right theme. Resolution order:
 *   ?theme=<id>&mode=<light|dark>  >  localStorage  >  prefers-color-scheme  >  neutral/light
 */
(function () {
  var root = document.documentElement;
  var KEY_THEME = "mbds-theme";
  var KEY_MODE = "mbds-mode";

  function read(key) {
    try { return window.localStorage.getItem(key); } catch (e) { return null; }
  }
  function write(key, value) {
    try { window.localStorage.setItem(key, value); return true; } catch (e) { return false; }
  }

  var params = null;
  try { params = new URLSearchParams(window.location.search); } catch (e) { params = null; }

  var theme = (params && params.get("theme")) || read(KEY_THEME) || "neutral";
  if (!/^[a-z0-9-]+$/.test(theme)) theme = "neutral";

  var mode = (params && params.get("mode")) || read(KEY_MODE);
  if (mode !== "light" && mode !== "dark") {
    var prefersDark = false;
    try { prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches; } catch (e) { prefersDark = false; }
    mode = prefersDark ? "dark" : "light";
  }

  root.setAttribute("data-theme", theme);
  root.setAttribute("data-mode", mode);

  window.MBDS = {
    get: function () {
      return { theme: root.getAttribute("data-theme"), mode: root.getAttribute("data-mode") };
    },
    set: function (next) {
      if (next.theme) root.setAttribute("data-theme", next.theme);
      if (next.mode) root.setAttribute("data-mode", next.mode);
      var current = this.get();
      var ok = write(KEY_THEME, current.theme) && write(KEY_MODE, current.mode);
      this.persisted = ok;
      document.dispatchEvent(new CustomEvent("mbds:themechange", { detail: current }));
      return ok;
    },
    persisted: true
  };
})();
