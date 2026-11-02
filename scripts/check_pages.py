#!/usr/bin/env python3
"""Load every page under every theme and mode in headless Chromium.

Fails on console errors (Content-Security-Policy violations included),
page errors, failed requests, an unknown theme, empty contract tokens,
missing tokens in the token table, any element whose font-family fell back
to the browser default, a hostile ?theme= / ?mode= / localStorage value that
reaches the DOM, or a broken switcher, dialog, form or progress demo.

    pip install -r requirements-dev.txt && python3 -m playwright install chromium
    python3 scripts/check_pages.py                  # serve the repo on 127.0.0.1 and run the gate
    python3 scripts/check_pages.py --base-url URL   # check an already-running server instead
    python3 scripts/check_pages.py --screenshots    # also write docs/screenshot-*.png

Paths are relative to the repository root.
"""
import argparse
import functools
import http.server
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGES = sorted(p.name for p in ROOT.glob("*.html"))
MODES = ("light", "dark")
VIEWPORT = {"width": 1440, "height": 900}
MIN_SIDEBAR_LINKS = 14  # one link per page in the catalogue nav
CSP_MARKER = "Content Security Policy"

# Values an attacker could put in a shared link or a poisoned localStorage.
HOSTILE_VALUES = [
    '"><img src=x onerror=alert(1)>',
    "neutral\" data-x=\"1",
    "<script>alert(1)</script>",
    "__proto__",
    "constructor",
    "NEUTRAL",
    "x" * 2048,
]

# Records every data-theme / data-mode value the document ever holds, so a
# hostile value is caught even if later code would have repaired it.
RECORD_THEME_HISTORY = """
window.__themeHistory = [];
new MutationObserver(records => {
  for (const r of records) {
    if (r.target !== document.documentElement) continue;
    window.__themeHistory.push(r.attributeName + '=' + r.target.getAttribute(r.attributeName));
  }
}).observe(document, { subtree: true, attributes: true, attributeFilter: ['data-theme', 'data-mode'] });
"""

PROBE = """
() => {
  const cs = getComputedStyle(document.documentElement);
  const tokens = (window.TOKEN_CONTRACT || []).flatMap(g => g.tokens);
  const empty = tokens.filter(t => !cs.getPropertyValue(t).trim());
  const defaults = [];
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('svg, template, script, style')) continue;
    const f = getComputedStyle(el).fontFamily.toLowerCase();
    if (f === 'times' || f === '"times new roman"' || f === 'serif') defaults.push(el.tagName + '.' + el.className);
  }
  const pair = (a, b) => window.MBDS_contrast ? window.MBDS_contrast(a, b) : null;
  return {
    theme: document.documentElement.dataset.theme,
    mode: document.documentElement.dataset.mode,
    empty,
    defaults: defaults.slice(0, 5),
    missingCells: document.querySelectorAll('.token-value.is-missing').length,
    bodyBg: getComputedStyle(document.body).backgroundColor,
    sidebarLinks: document.querySelectorAll('.navlist__link').length,
    chips: document.querySelectorAll('.chip').length,
    contrast: {
      text1: pair('--text-1', '--surface-0'),
      text2: pair('--text-2', '--surface-1'),
      text3: pair('--text-3', '--surface-1'),
      onPrimary: pair('--text-on-primary', '--color-primary'),
    },
  };
}
"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002 - signature fixed by the base class
        pass


@contextmanager
def serve(directory):
    """Serve `directory` on an ephemeral 127.0.0.1 port, the way GitHub Pages serves it."""
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()


class Session:
    """One browser page plus the console/network problems seen since the last reset."""

    def __init__(self, page):
        self.page = page
        self.problems = []
        self.csp_violations = 0
        page.on("console", self._on_console)
        page.on("pageerror", lambda e: self.problems.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: self.problems.append(f"requestfailed: {r.url}"))
        page.on("dialog", self._on_dialog)
        page.add_init_script(RECORD_THEME_HISTORY)

    def _on_console(self, msg):
        if CSP_MARKER in msg.text:
            self.csp_violations += 1
            self.problems.append(f"csp violation: {msg.text}")
        elif msg.type == "error":
            self.problems.append(f"console.error: {msg.text}")

    def _on_dialog(self, dialog):
        self.problems.append(f"unexpected JS dialog: {dialog.message}")
        dialog.dismiss()

    def load(self, url):
        self.page.goto(url, wait_until="networkidle")
        self.page.evaluate("document.fonts.ready")

    def drain(self, tag, failures):
        failures += [f"{tag}: {p}" for p in self.problems]
        self.problems.clear()


def registered_themes(s, base):
    s.load(base + "index.html")
    return s.page.evaluate("window.MBDS.themes.map(t => t.id)")


def check_matrix(s, base, themes, failures):
    """Every page x theme x mode: tokens resolve, fonts load, sidebar renders, no console noise."""
    runs, contrast = 0, {}
    for name in PAGES:
        for theme in themes:
            for mode in MODES:
                s.load(f"{base}{name}?theme={theme}&mode={mode}")
                r = s.page.evaluate(PROBE)
                runs += 1
                if r["theme"] != theme or r["mode"] != mode:
                    s.problems.append(f"theme fell back to {r['theme']}/{r['mode']}")
                if r["empty"]:
                    s.problems.append(f"empty tokens: {r['empty']}")
                if r["missingCells"]:
                    s.problems.append(f"{r['missingCells']} missing token cells")
                if r["defaults"]:
                    s.problems.append(f"default font on: {r['defaults']}")
                if r["bodyBg"] in ("rgba(0, 0, 0, 0)", "transparent"):
                    s.problems.append("body has no background")
                if r["sidebarLinks"] < MIN_SIDEBAR_LINKS or r["chips"] != len(themes):
                    s.problems.append(f"sidebar incomplete ({r['sidebarLinks']} links, {r['chips']} chips)")
                s.drain(f"{name} [{theme}/{mode}]", failures)
                contrast[(theme, mode)] = r["contrast"]
    return runs, contrast


def check_hostile_inputs(s, base, themes, failures):
    """Untrusted theme/mode values from the URL or storage never reach the DOM."""
    state = "[document.documentElement.dataset.theme, document.documentElement.dataset.mode]"
    injected = "document.querySelectorAll('img[src=x], [data-x], body script:not([src])').length"
    checks = 0
    for value in HOSTILE_VALUES:
        for source in ("url", "storage"):
            s.page.evaluate("localStorage.clear()")
            if source == "url":
                s.page.goto(base + "index.html?" + urlencode({"theme": value, "mode": value}), wait_until="networkidle")
            else:
                s.page.evaluate("v => { localStorage.setItem('mbds-theme', v); localStorage.setItem('mbds-mode', v); }", value)
                s.page.reload(wait_until="networkidle")
            theme, mode = s.page.evaluate(state)
            stored = s.page.evaluate("localStorage.getItem('mbds-theme')")
            allowed = {f"data-theme={t}" for t in themes} | {f"data-mode={m}" for m in MODES}
            seen = set(s.page.evaluate("window.__themeHistory"))
            tag = f"hostile {source} value {value[:40]!r}"
            if theme not in themes or mode not in MODES:
                s.problems.append(f"reached the DOM as {theme!r}/{mode!r}")
            if seen - allowed:
                s.problems.append(f"briefly reached the DOM: {sorted(v[:60] for v in seen - allowed)}")
            if s.page.evaluate(injected):
                s.problems.append("injected markup found in the document")
            if source == "url" and stored not in (None, *themes):
                s.problems.append(f"persisted to storage as {stored!r}")
            s.drain(tag, failures)
            checks += 1
    # The public API applies the same allowlist.
    for value in HOSTILE_VALUES:
        s.page.evaluate("v => window.MBDS.set({ theme: v, mode: v })", value)
        theme, mode = s.page.evaluate(state)
        if theme not in themes or mode not in MODES:
            s.problems.append(f"MBDS.set accepted {value[:40]!r}")
        checks += 1
    s.drain("MBDS.set", failures)
    s.page.evaluate("localStorage.clear()")
    return checks


def check_interactions(s, base, themes, failures):
    """The switcher persists across reloads; dialog, demo form and progress demo work under the CSP."""
    s.load(base + "buttons.html")
    s.page.click(f'.chip[data-theme-id="{themes[-1]}"]')
    s.page.click('.segmented__item[data-mode-id="dark"]')
    s.page.reload(wait_until="networkidle")
    state = s.page.evaluate("[document.documentElement.dataset.theme, document.documentElement.dataset.mode]")
    if state != [themes[-1], "dark"]:
        s.problems.append(f"switcher did not persist: got {state}")
    s.drain("switcher", failures)

    s.load(base + "forms.html")
    s.page.click("form[data-demo-form] button[type=submit]")
    s.page.wait_for_selector(".toast", timeout=2000)
    if not s.page.url.startswith(base + "forms.html"):
        s.problems.append(f"demo form navigated to {s.page.url}")
    s.drain("demo form submit", failures)

    s.load(base + "feedback.html")
    s.page.click('[data-open-dialog="delete-dialog"]')
    s.page.click('#delete-dialog button[value="confirm"]')
    s.page.wait_for_selector(".toast", timeout=2000)
    s.page.click('[data-progress-demo="#up-progress"]')
    now = s.page.get_attribute("#up-progress", "aria-valuenow")
    width = s.page.evaluate("document.querySelector('#up-progress .progress__bar').style.width")
    if (now, width) != ("70", "70%"):
        s.problems.append(f"progress demo advanced to {now}/{width}, expected 70/70%")
    s.drain("dialog + progress", failures)
    s.page.evaluate("localStorage.clear()")


def take_screenshots(s, base, themes):
    for i, theme in enumerate(themes):
        mode = "light" if i == 0 else "dark"
        s.load(f"{base}index.html?theme={theme}&mode={mode}")
        s.page.wait_for_timeout(300)
        out = ROOT / "docs" / f"screenshot-{i + 1}.png"
        s.page.screenshot(path=str(out))
        print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")


def launch(pw):
    try:
        return pw.chromium.launch()
    except Exception:
        # Fall back to an installed Google Chrome if Playwright's own build is missing.
        return pw.chromium.launch(channel="chrome")


def run(base, shots):
    failures = []
    with sync_playwright() as pw:
        browser = launch(pw)
        s = Session(browser.new_context(viewport=VIEWPORT).new_page())
        themes = registered_themes(s, base)
        s.drain("index.html", failures)
        runs, contrast = check_matrix(s, base, themes, failures)
        hostile = check_hostile_inputs(s, base, themes, failures)
        check_interactions(s, base, themes, failures)
        if shots:
            take_screenshots(s, base, themes)
        csp = s.csp_violations
        browser.close()

    print(f"{runs} page loads: {len(PAGES)} pages x {len(themes)} themes x {len(MODES)} modes")
    print(f"{hostile} hostile theme/mode inputs checked; switcher, dialog, form and progress demos checked")
    print(f"{csp} Content-Security-Policy violations")
    print("contrast (text-1/surface-0, text-2/surface-1, text-3/surface-1, on-primary/primary):")
    for (theme, mode), c in contrast.items():
        print(f"  {theme:>10} {mode:>5}: " + ", ".join(f"{v:.2f}" if v else "n/a" for v in c.values()))
    if failures:
        print(f"FAIL: {len(failures)} problem(s)")
        for f in failures:
            print("  - " + f)
        return 1
    print("OK: no console errors, no CSP violations, no empty tokens, no default-font elements")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base-url", help="check this server (e.g. http://localhost:8000/) instead of serving the repo")
    ap.add_argument("--screenshots", action="store_true", help="also regenerate docs/screenshot-*.png")
    args = ap.parse_args()
    if args.base_url:
        sys.exit(run(args.base_url.rstrip("/") + "/", args.screenshots))
    with serve(ROOT) as base:
        sys.exit(run(base, args.screenshots))


if __name__ == "__main__":
    main()
