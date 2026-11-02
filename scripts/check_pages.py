#!/usr/bin/env python3
"""Load every page under every theme and mode in headless Chromium.

Fails on console errors, page errors, failed requests, an unknown theme,
empty contract tokens, missing tokens in the token table, or any element
whose font-family fell back to the browser default.

    pip install playwright && python3 -m playwright install chromium
    python3 scripts/check_pages.py                 # run the gate
    python3 scripts/check_pages.py --screenshots   # also write docs/*.png

Paths are relative to the repository root.
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGES = sorted(p.name for p in ROOT.glob("*.html"))

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
  const bodyBg = getComputedStyle(document.body).backgroundColor;
  const pair = (a, b) => window.MBDS_contrast ? window.MBDS_contrast(a, b) : null;
  return {
    theme: document.documentElement.dataset.theme,
    mode: document.documentElement.dataset.mode,
    tokens: tokens.length,
    empty,
    defaults: defaults.slice(0, 5),
    missingCells: document.querySelectorAll('.token-value.is-missing').length,
    bodyBg,
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


def theme_ids():
    css = (ROOT / "themes" / "index.css").read_text()
    listed = re.search(r'--theme-list:\s*"([^"]+)"', css).group(1)
    return [p.split(":")[0].strip() for p in listed.split(",")]


def main():
    shots = "--screenshots" in sys.argv
    themes = theme_ids()
    failures, runs, contrast = [], 0, {}
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception:
            # Fall back to an installed Google Chrome if Playwright's own build is missing.
            browser = pw.chromium.launch(channel="chrome")
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        problems = []
        page.on("console", lambda m: problems.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: problems.append(f"requestfailed: {r.url}"))
        for name in PAGES:
            for theme in themes:
                for mode in ("light", "dark"):
                    problems.clear()
                    url = (ROOT / name).as_uri() + f"?theme={theme}&mode={mode}"
                    page.goto(url, wait_until="networkidle")
                    page.evaluate("document.fonts.ready")
                    r = page.evaluate(PROBE)
                    runs += 1
                    tag = f"{name} [{theme}/{mode}]"
                    if r["theme"] != theme or r["mode"] != mode:
                        problems.append(f"theme fell back to {r['theme']}/{r['mode']}")
                    if r["empty"]:
                        problems.append(f"empty tokens: {r['empty']}")
                    if r["missingCells"]:
                        problems.append(f"{r['missingCells']} missing token cells")
                    if r["defaults"]:
                        problems.append(f"default font on: {r['defaults']}")
                    if r["bodyBg"] in ("rgba(0, 0, 0, 0)", "transparent"):
                        problems.append("body has no background")
                    if r["sidebarLinks"] < 10 or r["chips"] != len(themes):
                        problems.append(f"sidebar incomplete ({r['sidebarLinks']} links, {r['chips']} chips)")
                    for p in problems:
                        failures.append(f"{tag}: {p}")
                    contrast[(theme, mode)] = r["contrast"]
        # Interaction: the switcher changes the theme and persists across a reload.
        page.goto((ROOT / "buttons.html").as_uri(), wait_until="networkidle")
        page.click(f'.chip[data-theme-id="{themes[-1]}"]')
        page.click('.segmented__item[data-mode-id="dark"]')
        page.reload(wait_until="networkidle")
        state = page.evaluate("[document.documentElement.dataset.theme, document.documentElement.dataset.mode]")
        if state != [themes[-1], "dark"]:
            failures.append(f"switcher did not persist: got {state}")
        else:
            print(f"switcher persisted across reload: {state}")

        if shots:
            for i, theme in enumerate(themes):
                mode = "light" if i == 0 else "dark"
                page.goto((ROOT / "index.html").as_uri() + f"?theme={theme}&mode={mode}", wait_until="networkidle")
                page.evaluate("document.fonts.ready")
                page.wait_for_timeout(300)
                out = ROOT / "docs" / f"screenshot-{i + 1}.png"
                page.screenshot(path=str(out))
                print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
        browser.close()

    print(f"{runs} page loads: {len(PAGES)} pages x {len(themes)} themes x 2 modes")
    print("contrast (text-1/surface-0, text-2/surface-1, text-3/surface-1, on-primary/primary):")
    for (theme, mode), c in contrast.items():
        print(f"  {theme:>10} {mode:>5}: " + ", ".join(f"{v:.2f}" if v else "n/a" for v in c.values()))
    if failures:
        print(f"FAIL: {len(failures)} problem(s)")
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("OK: no console errors, no empty tokens, no default-font elements")


if __name__ == "__main__":
    main()
