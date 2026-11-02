"""Each sync-tokens.py rule fails on a minimal violation and passes on the real tree.

    python3 -m unittest discover -s tests -v

Every test copies the site into a temporary directory, breaks one thing and
runs the linter there, so the working tree is never modified.
"""
import contextlib
import io
import re
import runpy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ["sync-tokens.py", "css", "js", "themes"]


class SyncTokensTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for name in SITE:
            src = ROOT / name
            (shutil.copytree if src.is_dir() else shutil.copy)(src, self.root / name)
        for page in ROOT.glob("*.html"):
            shutil.copy(page, self.root / page.name)

    def tearDown(self):
        self._tmp.cleanup()

    def lint(self):
        """Run the copied linter; return (exit code, stderr)."""
        err = io.StringIO()
        argv = sys.argv
        sys.argv = ["sync-tokens.py"]
        code = 0
        try:
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(self.root / "sync-tokens.py"), run_name="__main__")
        except SystemExit as e:
            code = e.code if isinstance(e.code, int) else 1
        finally:
            sys.argv = argv
        return code, err.getvalue()

    def edit(self, rel, old, new, count=1):
        path = self.root / rel
        text = path.read_text()
        self.assertIn(old, text, f"fixture drifted: {old!r} not in {rel}")
        path.write_text(text.replace(old, new, count))

    def assertFails(self, message):
        code, err = self.lint()
        self.assertEqual(code, 1, err)
        self.assertIn(message, err)

    def test_real_tree_passes(self):
        code, err = self.lint()
        self.assertEqual(code, 0, err)
        self.assertRegex(err, r"OK: 3 themes x 63 tokens \(23 per dark block\)")

    # Contract and registry
    def test_missing_light_token(self):
        text = (self.root / "themes/marquee.css").read_text()
        (self.root / "themes/marquee.css").write_text(re.sub(r"\n\s*--radius-md:[^;]+;", "", text, count=1))
        self.assertFails("marquee: light block is missing --radius-md")

    def test_missing_dark_colour_token(self):
        text = (self.root / "themes/neutral.css").read_text()
        selector = '[data-theme="neutral"][data-mode="dark"] {'
        light, dark = text.split(selector, 1)
        dark = re.sub(r"\n\s*--color-accent:[^;]+;", "", dark, count=1)
        (self.root / "themes/neutral.css").write_text(light + selector + dark)
        self.assertFails("neutral: dark block is missing --color-accent")

    def test_unknown_token(self):
        self.edit("themes/bikencars.css", "--radius-md:", "--radius-medium: 1px;\n  --radius-md:")
        self.assertFails("bikencars: --radius-medium is not in the contract")

    def test_theme_file_not_registered(self):
        shutil.copy(self.root / "themes/neutral.css", self.root / "themes/acme.css")
        self.assertFails("themes/acme.css is not @imported in themes/index.css")

    def test_registered_theme_without_file(self):
        self.edit("js/theme-init.js", '{ id: "marquee", label: "Marquee" }',
                  '{ id: "marquee", label: "Marquee" },\n    { id: "ghost", label: "Ghost" }')
        self.assertFails("'ghost' is registered but themes/ghost.css does not exist")

    def test_import_missing_from_allowlist(self):
        self.edit("js/theme-init.js", ',\n    { id: "marquee", label: "Marquee" }', "")
        self.assertFails("themes/marquee.css is missing from THEMES in js/theme-init.js")

    # Component lint
    def test_undefined_var(self):
        self.edit("css/components.css", "var(--text-1)", "var(--text-one)")
        self.assertFails("var(--text-one) is never defined")

    def test_colour_literal_in_components(self):
        self.edit("css/components.css", "var(--color-primary)", "#ff0000")
        self.assertFails("colour literal outside themes/")

    # Page policy (CSP enforceability)
    def test_inline_style_attribute(self):
        self.edit("index.html", '<main class="main"', '<main style="color:red" class="main"')
        self.assertFails("index.html: inline style attribute")

    def test_inline_event_handler(self):
        self.edit("buttons.html", "<button ", '<button onclick="go()" ')
        self.assertFails("buttons.html: inline event handler onclick=")

    def test_inline_script_block(self):
        self.edit("cards.html", "</body>", "<script>alert(1)</script></body>")
        self.assertFails("cards.html: inline <script> or <style> block")

    def test_csp_missing(self):
        text = (self.root / "tables.html").read_text()
        (self.root / "tables.html").write_text(re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]+>\n', "", text))
        self.assertFails("tables.html: CSP <meta> missing")

    def test_csp_unsafe_inline(self):
        self.edit("forms.html", "script-src 'self'", "script-src 'self' 'unsafe-inline'")
        self.assertFails("forms.html: CSP allows 'unsafe-inline'")
        _, err = self.lint()
        self.assertIn("pages disagree on the CSP", err)

    def test_referrer_policy_missing(self):
        self.edit("motion.html", '<meta name="referrer" content="no-referrer">\n', "")
        self.assertFails("motion.html: referrer policy <meta> missing")

    def test_target_blank_without_noopener(self):
        self.edit("index.html", "</main>", '<a href="https://example.com" target="_blank">x</a></main>')
        self.assertFails("index.html: target=_blank without rel=noopener")


if __name__ == "__main__":
    unittest.main()
