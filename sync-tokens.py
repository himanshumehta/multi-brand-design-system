#!/usr/bin/env python3
"""Validate every theme against the token contract, and lint components.

Usage:
    python3 sync-tokens.py            # validate; exit 1 on any problem
    python3 sync-tokens.py --json     # print all theme tokens as JSON
    python3 sync-tokens.py --table    # print a Markdown table of key tokens

Checks:
  1. Every theme file is @imported in themes/index.css and listed in the
     THEMES registry in js/theme-init.js, and every registration has a file.
  2. Each theme's light block defines every contract token; its dark block
     redefines every token in the colour group. No unknown tokens.
  3. Every var(--x) used in css/, js/ and the HTML pages is defined by the
     contract, by a derived token, or locally inside a component.
  4. No colour literals (#hex, rgb(), hsl(), oklch()) outside themes/.
  5. Every HTML page carries the same strict Content-Security-Policy <meta>
     (no 'unsafe-inline', 'unsafe-eval' or wildcard sources) and a referrer
     policy, and has nothing the CSP would block: no style="" attributes,
     on*= handlers, inline <script>/<style> blocks or javascript: URLs.
     target="_blank" links need rel="noopener".

Standard library only. Paths are relative to this file.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
THEMES = ROOT / "themes"
TABLE_TOKENS = ["--surface-0", "--text-1", "--color-primary", "--color-accent",
                "--font-display", "--radius-md", "--duration-base"]
UNSAFE_CSP_SOURCES = ("'unsafe-inline'", "'unsafe-eval'", "'unsafe-hashes'", "*", "data:", "http:", "https:")
COLOUR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\(")


def load_contract():
    text = (ROOT / "js" / "contract.js").read_text()
    groups = []
    for m in re.finditer(r'group:\s*"([^"]+)",\s*mode:\s*(true|false),\s*tokens:\s*\[(.*?)\]', text, re.S):
        groups.append({
            "group": m.group(1),
            "mode": m.group(2) == "true",
            "tokens": re.findall(r'"(--[a-z0-9-]+)"', m.group(3)),
        })
    if not groups:
        sys.exit("Could not parse js/contract.js")
    return groups


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def declarations(block):
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;]+);", block)}


def theme_blocks(theme_id, css):
    css = strip_comments(css)
    light, dark = {}, {}
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selector, body = m.group(1), m.group(2)
        if f'[data-theme="{theme_id}"]' not in selector:
            continue
        target = dark if 'data-mode="dark"' in selector else light
        target.update(declarations(body))
    return light, dark


def registry():
    """Return (@imported theme ids, {id: label} from THEMES in js/theme-init.js)."""
    css = strip_comments((THEMES / "index.css").read_text())
    imports = re.findall(r'@import\s+url\("([^"]+)\.css"\)', css)
    js = (ROOT / "js" / "theme-init.js").read_text()
    listed = dict(re.findall(r'\{\s*id:\s*"([a-z0-9-]+)",\s*label:\s*"([^"]+)"\s*\}', js))
    if not listed:
        sys.exit("Could not parse THEMES in js/theme-init.js")
    return imports, listed


def check_registry(errors):
    """Every theme file is registered and every registration has a file. Returns ids and labels."""
    imports, listed = registry()
    on_disk = sorted(p.stem for p in THEMES.glob("*.css") if p.stem != "index")
    files = [t for t in imports if t in on_disk] + [t for t in on_disk if t not in imports]
    for f in files:
        if f not in imports:
            errors.append(f"themes/{f}.css is not @imported in themes/index.css")
        if f not in listed:
            errors.append(f"themes/{f}.css is missing from THEMES in js/theme-init.js")
    for t in set(imports) | set(listed):
        if t not in files:
            errors.append(f"'{t}' is registered but themes/{t}.css does not exist")
    return files, listed


def check_themes(errors, files, listed, contract):
    """Each theme defines the full contract (colour group again for dark). Returns resolved tokens."""
    all_tokens = [t for g in contract for t in g["tokens"]]
    colour_tokens = [t for g in contract if g["mode"] for t in g["tokens"]]
    data = {}
    for theme_id in files:
        light, dark = theme_blocks(theme_id, (THEMES / f"{theme_id}.css").read_text())
        errors += [f"{theme_id}: light block is missing {t}" for t in all_tokens if t not in light]
        errors += [f"{theme_id}: dark block is missing {t}" for t in colour_tokens if t not in dark]
        errors += [f"{theme_id}: {t} is not in the contract" for t in sorted(set(light) | set(dark)) if t not in all_tokens]
        data[theme_id] = {
            "label": listed.get(theme_id, theme_id),
            "light": {t: light.get(t) for t in all_tokens},
            "dark": {t: dark.get(t, light.get(t)) for t in all_tokens},
        }
    return data


def lint_var_references(errors, sources, contract):
    """Every var(--x) resolves to a contract token or a property declared somewhere in the sources."""
    defined = {t for g in contract for t in g["tokens"]}
    for src in sources:
        defined |= set(re.findall(r"(--[a-z0-9-]+)\s*:", strip_comments(src.read_text())))
    for src in sources:
        for name in sorted(set(re.findall(r"var\((--[a-z0-9-]+)", src.read_text()))):
            if name not in defined:
                errors.append(f"{src.relative_to(ROOT)}: var({name}) is never defined")


def lint_colour_literals(errors):
    """Colour values belong only in themes/."""
    for src in sorted((ROOT / "css").glob("*.css")):
        for i, line in enumerate(strip_comments(src.read_text()).splitlines(), 1):
            if COLOUR_LITERAL.search(line):
                errors.append(f"{src.relative_to(ROOT)}:{i}: colour literal outside themes/: {line.strip()}")


def lint_csp_meta(errors, name, html, policies):
    """The CSP <meta> comes first (before anything it governs) and has no unsafe sources."""
    csp = re.search(r'<meta charset="utf-8">\s*<meta http-equiv="Content-Security-Policy" content="([^"]+)">', html)
    if not csp:
        errors.append(f"{name}: CSP <meta> missing or not directly after <meta charset>")
        return
    policies.setdefault(csp.group(1), []).append(name)
    errors += [f"{name}: CSP allows {weak}" for weak in UNSAFE_CSP_SOURCES if weak in re.split(r"[\s;]+", csp.group(1))]
    if '<meta name="referrer" content="no-referrer">' not in html:
        errors.append(f"{name}: referrer policy <meta> missing")


def lint_inline_content(errors, name, html):
    """Nothing the CSP would block: inline styles, handlers, scripts, javascript: URLs."""
    errors += [f"{name}: inline style attribute (use a class in css/utilities.css): {v}"
               for v in re.findall(r'\sstyle="([^"]*)"', html)]
    errors += [f"{name}: inline event handler {v}= (bind it in js/)"
               for v in re.findall(r"<[^>]*\s(on[a-z]+)=", html)]
    if re.search(r"<script(?![^>]*\ssrc=)[^>]*>", html) or re.search(r"<style[\s>]", html):
        errors.append(f"{name}: inline <script> or <style> block")
    if "javascript:" in html.lower():
        errors.append(f"{name}: javascript: URL")
    errors += [f"{name}: target=_blank without rel=noopener: {tag}"
               for tag in re.findall(r'<a\s[^>]*target="_blank"[^>]*>', html)
               if not re.search(r'rel="[^"]*\bnoopener\b', tag)]


def lint_page_policy(errors, pages):
    """Every page keeps the same strict CSP enforceable."""
    policies = {}
    for src in pages:
        html = src.read_text()
        lint_csp_meta(errors, src.name, html, policies)
        lint_inline_content(errors, src.name, html)
    if len(policies) > 1:
        errors.append("pages disagree on the CSP: " + "; ".join(f"{len(v)} page(s) use {k!r}" for k, v in policies.items()))


def print_table(data, files):
    print("| Token | " + " | ".join(f"{data[t]['label']} light | {data[t]['label']} dark" for t in files) + " |")
    print("|" + "---|" * (1 + 2 * len(files)))
    for k in TABLE_TOKENS:
        cells = []
        for t in files:
            cells += [data[t]["light"][k], data[t]["dark"][k]]
        print(f"| `{k}` | " + " | ".join(f"`{c}`" for c in cells) + " |")


def main():
    args = sys.argv[1:]
    errors = []
    contract = load_contract()
    pages = sorted(ROOT.glob("*.html"))
    sources = sorted((ROOT / "css").glob("*.css")) + sorted((ROOT / "js").glob("*.js")) + pages

    files, listed = check_registry(errors)
    data = check_themes(errors, files, listed, contract)
    lint_var_references(errors, sources, contract)
    lint_colour_literals(errors)
    lint_page_policy(errors, pages)

    if "--json" in args:
        print(json.dumps({"contract": contract, "themes": data}, indent=2))
    elif "--table" in args:
        print_table(data, files)

    if errors:
        print(f"FAIL: {len(errors)} problem(s)", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        sys.exit(1)
    n_tokens = sum(len(g["tokens"]) for g in contract)
    n_colour = sum(len(g["tokens"]) for g in contract if g["mode"])
    print(f"OK: {len(files)} themes x {n_tokens} tokens ({n_colour} per dark block); "
          f"{len(sources)} source files linted", file=sys.stderr)


if __name__ == "__main__":
    main()
