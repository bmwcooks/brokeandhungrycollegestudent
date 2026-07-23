# AGENTS.md

## Cursor Cloud specific instructions

This repo is the **Sports Food Deals Tracker**: a Python data pipeline plus a static
vanilla HTML/CSS/JS frontend. There is no backend server, database, build step, or
test/lint framework. See `README.md` for the high-level architecture and
`.github/workflows/update-deals.yml` for the production automation/deploy flow.

Services:

- **Data pipeline** (`update_deals.py`): reads `promotions.json`, calls the public ESPN
  scoreboard API, and writes `public/active_deals.json`.
- **Frontend** (`public/index.html`): fetches `active_deals.json` and renders deal cards.

Non-obvious notes:

- Use `python3` (Python 3.12 is installed); there is no bare `python` on PATH, even
  though the CI workflow calls `python`.
- Run the pipeline from the repo root — it reads `./promotions.json` and writes
  `./public/active_deals.json` using relative paths: `python3 update_deals.py`.
- The frontend must be served over HTTP; opening `public/index.html` via `file://`
  breaks the `fetch('active_deals.json')` call. Serve it with
  `cd public && python3 -m http.server 8000` and open `http://localhost:8000/`.
- `public/active_deals.json` is a generated file that is also committed. Running the
  pipeline typically only changes its `last_updated` timestamp (and the deal set based
  on yesterday's live games), so `git checkout public/active_deals.json` to discard
  incidental regeneration diffs.
- Running the pipeline live requires outbound access to `site.api.espn.com`; if
  unreachable, the script logs the error and produces an empty deal list rather than
  crashing.
- No linter or test suite is configured. "Testing" means running the pipeline and
  visually verifying the served frontend.
