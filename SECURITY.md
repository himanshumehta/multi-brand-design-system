# Security policy

## Reporting a vulnerability

Email **mehta.august@gmail.com** with a description, the affected file or URL,
and steps to reproduce. Please do not open a public issue for an unfixed
vulnerability.

## Supported versions

Only `main` is supported. The live site at
<https://himanshumehta.github.io/multi-brand-design-system/> is deployed from
`main` by `.github/workflows/pages.yml`.

## What this project is

A static catalogue: 14 HTML pages, CSS and 524 lines of vanilla JavaScript
(`wc -l js/*.js`), served by GitHub Pages. There is no server code, no build step,
no accounts, no forms that submit anywhere, no cookies and no analytics. The
only third-party requests are Google Fonts stylesheets and font files.

## Threat model

| Input or asset | Risk | Control |
|---|---|---|
| `?theme=` and `?mode=` in a shared link | Attribute or markup injection, theme spoofing | `js/theme-init.js` applies a value only if it is in the `THEMES` registry (mode: `light` or `dark`); anything else falls through to storage, then the default. `MBDS.set()` applies the same allowlist. |
| `localStorage` (`mbds-theme`, `mbds-mode`) | Same, from a poisoned or stale value | Same allowlist; all storage access is wrapped in `try/catch`. |
| DOM writes from JavaScript | XSS through `innerHTML` | `js/` uses `textContent`, `createElement` and `replaceChildren` only. Trusted Types (`require-trusted-types-for 'script'`) makes any HTML sink throw. |
| Injected markup of any origin | Script execution, data exfiltration | Strict CSP `<meta>` on every page: `default-src 'none'`, scripts and styles from `'self'` only (plus the Google Fonts stylesheet host), fonts from `fonts.gstatic.com`, no `'unsafe-inline'`, `base-uri 'none'`, `form-action 'none'`, `object-src 'none'`. |
| Outbound requests | Leaking the page URL to Google | `referrer` is `no-referrer`. |
| CI and deployment | Supply-chain compromise of an action, token misuse | Workflow default `permissions: contents: read`; only `deploy` gets `pages: write` and `id-token: write`. Actions are pinned to commit SHAs; `actions/checkout` does not persist credentials. Dependabot proposes updates weekly with a 7-day cooldown. |
| Secrets | Committed credentials | gitleaks runs on every push and pull request. The site needs no secrets. |

### Enforced by automation

- `python3 sync-tokens.py` fails if any page lacks the CSP or referrer
  `<meta>`, if pages disagree on the policy, if the policy allows
  `'unsafe-inline'`, `'unsafe-eval'`, `'unsafe-hashes'`, `*` or scheme-wide sources (`data:`, `http:`, `https:`), or if a page contains
  something the policy would block (`style=""`, `on*=` handlers, inline
  `<script>`/`<style>`, `javascript:` URLs) or a `target="_blank"` link without
  `rel="noopener"`. Each rule has a test in `tests/test_sync_tokens.py`.
- `python3 scripts/check_pages.py` loads every page under every theme and mode
  and fails on any console error, including CSP violations, and on any web font
  that did not load. It feeds 7 hostile values through the URL, `localStorage`
  and `MBDS.set()` (21 cases) and fails if any of them is ever written to
  `data-theme` or `data-mode`, even briefly.
- CI runs both, plus `pip-audit` on `requirements-dev.txt`, semgrep
  (`p/default`) and bandit.

## Out of scope and known gaps

- **`frame-ancestors`, `X-Content-Type-Options`, HSTS.** These need HTTP
  response headers. GitHub Pages does not allow custom headers and browsers
  ignore `frame-ancestors` in a `<meta>` CSP, so the site can be framed. It has
  no state-changing actions, so clickjacking has nothing to target. Hosting
  behind a CDN that sets headers would close this.
- **Subresource Integrity for Google Fonts.** The Google Fonts CSS is generated
  per browser, so it cannot carry a stable hash. The CSP limits fonts to
  `fonts.gstatic.com` and stylesheets to `fonts.googleapis.com`; self-hosting
  the fonts would remove the dependency.
- **Scanner tooling.** `.github/requirements-ci.txt` pins semgrep, bandit and
  pip-audit for CI. They do not ship with the site and are not part of the
  dependency audit; semgrep's own dependency tree had open advisories when last
  checked.
- **The deployed artifact** is the whole repository (including `scripts/` and
  `tests/`). None of it is executable by a browser beyond the pages themselves.
