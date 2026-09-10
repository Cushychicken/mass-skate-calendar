# Mass Skate Calendar

A daily, static calendar of public skating and stick-and-puck sessions near Medford, Massachusetts.

Sources currently include:

- LoConte Rink, Medford
- Viglirolo Rink / Belmont Sports Complex, Belmont
- Warrior Ice Arena, Boston
- Stoneham Arena, Stoneham
- Cronin Rink, Revere

## How it works

The scheduled GitHub Action runs the Python scrapers every morning, writes normalized data to `docs/data/events.json`, commits changed data, and deploys `docs/` to GitHub Pages. Each rink is isolated: a broken source retains previously collected future events and is marked stale on the page.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m scraper.daily
python -m http.server --directory docs 8000
```

Open <http://localhost:8000>.

## Deployment

In repository settings, set **Pages → Source** to **GitHub Actions**, then run **Refresh rink schedules** once from the Actions tab. It will subsequently run daily at 10:17 UTC.

Schedules are scraped from third-party sites for personal convenience. Always verify a session with the rink before traveling.
