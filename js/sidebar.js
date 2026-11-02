/*
 * Injects the catalogue sidebar: wordmark, theme + mode switcher, page links,
 * and the mobile menu button. Themes are discovered from --theme-list
 * (themes/index.css), so adding a theme needs no JavaScript change.
 */
(function () {
  var NAV = [
    { title: "Foundations", links: [
      ["index.html", "Overview"],
      ["tokens.html", "Token reference"],
      ["colors.html", "Colour"],
      ["typography.html", "Typography"],
      ["spacing.html", "Space and shape"],
      ["motion.html", "Motion"],
      ["theming.html", "Theming"]
    ] },
    { title: "Components", links: [
      ["buttons.html", "Buttons"],
      ["forms.html", "Forms"],
      ["cards.html", "Cards"],
      ["tables.html", "Tables"],
      ["navigation.html", "Navigation"],
      ["feedback.html", "Feedback and overlays"]
    ] },
    { title: "Formats", links: [
      ["slides.html", "Slides and social"]
    ] }
  ];

  function themeList() {
    var raw = getComputedStyle(document.documentElement).getPropertyValue("--theme-list") || "";
    raw = raw.trim().replace(/^["']|["']$/g, "");
    var list = raw.split(",").map(function (pair) {
      var parts = pair.split(":");
      return { id: (parts[0] || "").trim(), label: (parts[1] || parts[0] || "").trim() };
    }).filter(function (t) { return t.id; });
    return list.length ? list : [{ id: "neutral", label: "Neutral" }];
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === "text") node.textContent = attrs[k];
      else node.setAttribute(k, attrs[k]);
    });
    (children || []).forEach(function (c) { node.appendChild(c); });
    return node;
  }

  function build() {
    var themes = themeList();
    var state = window.MBDS.get();

    // Unknown theme id (stale storage or bad URL param): fall back quietly.
    if (!themes.some(function (t) { return t.id === state.theme; })) {
      window.MBDS.set({ theme: themes[0].id });
      state = window.MBDS.get();
    }

    var nav = document.querySelector("nav.sidebar");
    if (!nav) {
      nav = el("nav", { "class": "sidebar", "aria-label": "Catalogue" });
      document.body.insertBefore(nav, document.body.firstChild);
    }
    nav.id = "sidebar";
    nav.innerHTML = "";

    var mark = el("a", { "class": "wordmark", href: "index.html" }, [
      el("span", { "class": "wordmark__top", text: "Multi-brand" }),
      el("span", { "class": "wordmark__bottom", text: "design system" })
    ]);
    nav.appendChild(mark);

    // Theme switcher. Each chip carries its own data-theme, so its swatch is
    // painted by that theme's tokens, not the page's.
    var chips = el("div", { "class": "switcher__themes", role: "radiogroup", "aria-label": "Theme" });
    themes.forEach(function (t) {
      var swatch = el("span", { "class": "chip__swatch theme-scope", "data-theme": t.id, "data-mode": state.mode, "aria-hidden": "true" }, [
        el("span", { "class": "chip__band chip__band--surface" }),
        el("span", { "class": "chip__band chip__band--primary" }),
        el("span", { "class": "chip__band chip__band--accent" }),
        el("span", { "class": "chip__glyph", text: "Aa" })
      ]);
      var chip = el("button", {
        type: "button", "class": "chip", role: "radio",
        "data-theme-id": t.id, "aria-checked": String(t.id === state.theme)
      }, [swatch, el("span", { "class": "chip__label", text: t.label })]);
      chip.addEventListener("click", function () { window.MBDS.set({ theme: t.id }); sync(); });
      chips.appendChild(chip);
    });

    var modes = el("div", { "class": "segmented switcher__mode", role: "radiogroup", "aria-label": "Colour mode" });
    ["light", "dark"].forEach(function (m) {
      var b = el("button", { type: "button", "class": "segmented__item", role: "radio", "data-mode-id": m, "aria-checked": String(m === state.mode), text: m === "light" ? "Light" : "Dark" });
      b.addEventListener("click", function () { window.MBDS.set({ mode: m }); sync(); });
      modes.appendChild(b);
    });

    nav.appendChild(el("div", { "class": "switcher" }, [
      el("p", { "class": "switcher__label", id: "switcher-label", text: "Theme" }),
      chips,
      modes
    ]));

    var current = (window.location.pathname.split("/").pop() || "index.html");
    NAV.forEach(function (group) {
      var list = el("ul", { "class": "navlist" });
      group.links.forEach(function (l) {
        var a = el("a", { href: l[0], "class": "navlist__link", text: l[1] });
        if (l[0] === current) a.setAttribute("aria-current", "page");
        list.appendChild(el("li", {}, [a]));
      });
      nav.appendChild(el("div", { "class": "navgroup" }, [
        el("p", { "class": "navgroup__title", text: group.title }), list
      ]));
    });

    // Without storage, carry the choice across pages in the query string.
    nav.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest("a.navlist__link, a.wordmark");
      if (!a || window.MBDS.persisted) return;
      var s = window.MBDS.get();
      a.setAttribute("href", a.getAttribute("href").split("?")[0] + "?theme=" + s.theme + "&mode=" + s.mode);
    });

    // Mobile menu
    var btn = el("button", { type: "button", "class": "menu-btn", "aria-controls": "sidebar", "aria-expanded": "false", "aria-label": "Open navigation" }, [
      el("span", { "class": "menu-btn__bar" }), el("span", { "class": "menu-btn__bar" }), el("span", { "class": "menu-btn__bar" })
    ]);
    btn.addEventListener("click", function () {
      var open = nav.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", String(open));
      btn.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("is-open")) btn.click();
    });
    document.body.appendChild(btn);

    function sync() {
      var s = window.MBDS.get();
      nav.querySelectorAll(".chip").forEach(function (c) {
        c.setAttribute("aria-checked", String(c.getAttribute("data-theme-id") === s.theme));
      });
      nav.querySelectorAll(".chip__swatch").forEach(function (sw) { sw.setAttribute("data-mode", s.mode); });
      nav.querySelectorAll(".segmented__item").forEach(function (b) {
        b.setAttribute("aria-checked", String(b.getAttribute("data-mode-id") === s.mode));
      });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", build);
  else build();
})();
