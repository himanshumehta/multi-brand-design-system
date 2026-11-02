/*
 * Small, dependency-free behaviours for the catalogue demos. Each block only
 * activates when its markup is present on the page.
 */
(function () {
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function rootStyle() { return getComputedStyle(document.documentElement); }
  function onTheme(fn) { document.addEventListener("mbds:themechange", fn); }

  /* Tabs (roving focus, arrow keys) */
  $all("[role=tablist]").forEach(function (list) {
    var tabs = $all("[role=tab]", list);
    function select(tab, focus) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute("aria-selected", String(on));
        t.tabIndex = on ? 0 : -1;
        var panel = document.getElementById(t.getAttribute("aria-controls"));
        if (panel) panel.hidden = !on;
      });
      if (focus) tab.focus();
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { select(t); });
      t.addEventListener("keydown", function (e) {
        var d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (d) { e.preventDefault(); select(tabs[(i + d + tabs.length) % tabs.length], true); }
      });
    });
  });

  /* Segmented controls used as demos (not the theme switcher) */
  $all("[data-segmented]").forEach(function (group) {
    var items = $all(".segmented__item", group);
    items.forEach(function (b) {
      b.addEventListener("click", function () {
        items.forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      });
    });
  });

  /* Toasts */
  var region = null;
  function toast(message) {
    if (!region) {
      region = document.createElement("div");
      region.className = "toast-region";
      region.setAttribute("role", "status");
      region.setAttribute("aria-live", "polite");
      document.body.appendChild(region);
    }
    var t = document.createElement("div");
    t.className = "toast";
    var mark = document.createElement("span");
    mark.className = "toast__mark";
    var text = document.createElement("span");
    text.textContent = message;
    t.appendChild(mark); t.appendChild(text);
    region.appendChild(t);
    setTimeout(function () {
      t.classList.add("is-leaving");
      setTimeout(function () { t.remove(); }, 400);
    }, 3200);
  }
  $all("[data-toast]").forEach(function (b) {
    b.addEventListener("click", function () { toast(b.getAttribute("data-toast")); });
  });

  /* Demo forms never submit; the submit button's data-toast reports instead. */
  $all("form[data-demo-form]").forEach(function (f) {
    f.addEventListener("submit", function (e) { e.preventDefault(); });
  });

  /* Dialogs */
  $all("[data-open-dialog]").forEach(function (b) {
    var dlg = document.getElementById(b.getAttribute("data-open-dialog"));
    if (!dlg || typeof dlg.showModal !== "function") return;
    b.addEventListener("click", function () { dlg.showModal(); });
    dlg.addEventListener("click", function (e) { if (e.target === dlg) dlg.close("cancel"); });
    dlg.addEventListener("close", function () {
      var msg = dlg.returnValue === "confirm" ? dlg.getAttribute("data-confirm-toast") : null;
      if (msg) toast(msg);
    });
  });

  /* Busy buttons */
  $all("[data-busy-demo]").forEach(function (b) {
    b.addEventListener("click", function () {
      b.setAttribute("aria-busy", "true");
      setTimeout(function () { b.removeAttribute("aria-busy"); toast(b.getAttribute("data-busy-demo")); }, 1400);
    });
  });

  /* Sortable tables */
  $all("table[data-sortable]").forEach(function (table) {
    var heads = $all("thead th", table);
    heads.forEach(function (th, col) {
      var btn = th.querySelector(".th-sort");
      if (!btn) return;
      btn.addEventListener("click", function () {
        var dir = th.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
        heads.forEach(function (h) { h.removeAttribute("aria-sort"); });
        th.setAttribute("aria-sort", dir);
        var body = table.tBodies[0];
        var rows = Array.prototype.slice.call(body.rows);
        rows.sort(function (a, b) {
          var x = a.cells[col].getAttribute("data-value") || a.cells[col].textContent.trim();
          var y = b.cells[col].getAttribute("data-value") || b.cells[col].textContent.trim();
          var nx = parseFloat(x), ny = parseFloat(y);
          var cmp = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : x.localeCompare(y);
          return dir === "ascending" ? cmp : -cmp;
        });
        rows.forEach(function (r) { body.appendChild(r); });
      });
    });
  });

  /* Live token reference */
  var tokenHost = document.getElementById("token-table");
  if (tokenHost && window.TOKEN_CONTRACT) {
    function previewFor(name, group) {
      var span = document.createElement("span");
      span.className = "token-preview";
      if (group === "Colour") {
        if (name.indexOf("shadow") > -1) { span.className += " token-preview--shadow"; span.style.boxShadow = "var(" + name + ")"; }
        else span.style.background = "var(" + name + ")";
      } else if (group === "Space") {
        span.className += " token-preview--bar"; span.style.width = "var(" + name + ")";
      } else if (group === "Shape") {
        span.className += " token-preview--radius"; span.style.borderRadius = "var(" + name + ")";
      } else if (name.indexOf("--text-") === 0) {
        span.className += " token-preview--type"; span.style.fontSize = "var(" + name + ")"; span.textContent = "Ag";
      } else if (name.indexOf("--font-") === 0) {
        span.className += " token-preview--type"; span.style.fontFamily = "var(" + name + ")"; span.textContent = "Ag";
      } else {
        span.className += " token-preview--none";
      }
      return span;
    }
    function render() {
      var cs = rootStyle();
      tokenHost.innerHTML = "";
      var total = 0;
      window.TOKEN_CONTRACT.forEach(function (g) {
        var section = document.createElement("section");
        section.className = "doc-section";
        var h = document.createElement("h2");
        h.textContent = g.group;
        var p = document.createElement("p");
        p.className = "doc-desc";
        p.textContent = g.tokens.length + " tokens" + (g.mode ? ", redefined for dark mode" : ", shared by light and dark");
        var wrap = document.createElement("div");
        wrap.className = "table-wrap";
        var table = document.createElement("table");
        table.className = "table table--compact token-table";
        table.innerHTML = "<thead><tr><th scope=col>Token</th><th scope=col>Current value</th><th scope=col>Preview</th></tr></thead>";
        var tb = document.createElement("tbody");
        g.tokens.forEach(function (name) {
          total++;
          var tr = document.createElement("tr");
          var td1 = document.createElement("th"); td1.scope = "row";
          var c = document.createElement("code"); c.textContent = name; td1.appendChild(c);
          var td2 = document.createElement("td"); td2.className = "mono token-value";
          var v = cs.getPropertyValue(name).trim();
          td2.textContent = v || "(missing)";
          if (!v) td2.classList.add("is-missing");
          var td3 = document.createElement("td"); td3.appendChild(previewFor(name, g.group));
          tr.appendChild(td1); tr.appendChild(td2); tr.appendChild(td3);
          tb.appendChild(tr);
        });
        table.appendChild(tb); wrap.appendChild(table);
        section.appendChild(h); section.appendChild(p); section.appendChild(wrap);
        tokenHost.appendChild(section);
      });
      var count = document.getElementById("token-count");
      if (count) count.textContent = String(total);
    }
    render();
    onTheme(render);
  }

  /* Swatch values + contrast ratios (colour page) */
  function parseRGB(str) {
    var m = str.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/);
    if (m) return [+m[1], +m[2], +m[3]];
    m = str.match(/^#([0-9a-f]{6})$/i);
    if (m) return [parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16), parseInt(m[1].slice(4, 6), 16)];
    return null;
  }
  function lum(rgb) {
    var a = rgb.map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
  }
  function contrast(fg, bg) {
    var l1 = lum(fg), l2 = lum(bg);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  window.MBDS_contrast = function (fgToken, bgToken) {
    var cs = rootStyle();
    var fg = parseRGB(cs.getPropertyValue(fgToken).trim());
    var bg = parseRGB(cs.getPropertyValue(bgToken).trim());
    return fg && bg ? contrast(fg, bg) : null;
  };
  function paintColourData() {
    var cs = rootStyle();
    $all("[data-token-value]").forEach(function (n) {
      n.textContent = cs.getPropertyValue(n.getAttribute("data-token-value")).trim();
    });
    $all("[data-contrast]").forEach(function (n) {
      var pair = n.getAttribute("data-contrast").split("|");
      var r = window.MBDS_contrast(pair[0], pair[1]);
      if (r === null) { n.textContent = "n/a"; return; }
      var grade = r >= 7 ? "AAA" : r >= 4.5 ? "AA" : r >= 3 ? "AA large" : "Fails";
      n.textContent = r.toFixed(2) + ":1 " + grade;
      n.className = "badge " + (r >= 4.5 ? "badge--success" : r >= 3 ? "badge--warning" : "badge--danger");
    });
  }
  paintColourData();
  onTheme(paintColourData);

  /* Motion demos */
  $all("[data-motion-play]").forEach(function (b) {
    var host = document.getElementById(b.getAttribute("data-motion-play"));
    if (!host) return;
    b.addEventListener("click", function () {
      host.classList.toggle("is-played");
      b.textContent = host.classList.contains("is-played") ? "Reset" : "Play";
    });
  });

  /* Progress demo. aria-valuenow is the source of truth; the bar's initial
   * width comes from a utility class, later widths from the CSSOM (which a
   * CSP without 'unsafe-inline' still allows). */
  var PROGRESS_STEP = 30, PROGRESS_RESTART = 10;
  $all("[data-progress-demo]").forEach(function (b) {
    var track = document.querySelector(b.getAttribute("data-progress-demo"));
    var bar = track && track.querySelector(".progress__bar");
    if (!bar) return;
    b.addEventListener("click", function () {
      var w = parseInt(track.getAttribute("aria-valuenow"), 10) || 0;
      w = w >= 100 ? PROGRESS_RESTART : Math.min(100, w + PROGRESS_STEP);
      bar.style.width = w + "%";
      track.setAttribute("aria-valuenow", String(w));
    });
  });
})();

/* Theme matrix (theming page): one scoped clone per theme and mode. */
(function () {
  var host = document.getElementById("theme-matrix");
  var tpl = document.getElementById("matrix-sample");
  if (!host || !tpl) return;
  var raw = getComputedStyle(document.documentElement).getPropertyValue("--theme-list").trim().replace(/^["']|["']$/g, "");
  raw.split(",").forEach(function (pair) {
    var parts = pair.split(":");
    var id = (parts[0] || "").trim(), label = (parts[1] || id).trim();
    if (!id) return;
    ["light", "dark"].forEach(function (mode) {
      var cell = document.createElement("div");
      cell.className = "matrix__cell theme-scope";
      cell.setAttribute("data-theme", id);
      cell.setAttribute("data-mode", mode);
      cell.appendChild(tpl.content.cloneNode(true));
      cell.querySelector(".matrix__label").textContent = label + ", " + mode;
      host.appendChild(cell);
    });
  });
})();
