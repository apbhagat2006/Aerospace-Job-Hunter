# Flightpath · Aerospace Job Hunter

A local internship discovery dashboard and application tracker. No account, cloud database, Node installation, or Discord configuration required.

## Start here

Install **Python 3.11 or newer**, open a terminal in this folder, and run:

```sh
python -m venv .venv
```

Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

macOS / Linux:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

On Windows, `start.ps1` also creates the environment, installs requirements, and starts the app. Run it from PowerShell if your local script policy allows it.

The app opens **http://127.0.0.1:8765**. Keep the terminal open: it checks jobs on startup and every six hours while running. Closing the browser does not stop it; Ctrl+C in the terminal does. Your computer must be awake and online to collect new jobs. Saved listings remain available offline.

## What you can do

- Search titles, companies, and locations, and filter by company or application stage.
- Save jobs and track **saved → applied → interviewing → offer**, plus rejected and withdrawn.
- Keep private notes for deadlines, contacts, and next steps.
- Open original postings to apply; changing a stage does not submit an application.
- Keep tracked jobs even after they disappear from the source board.
- Inspect source health: failures never masquerade as successful empty results or close existing listings.
- Search a directory of 300+ aerospace employers across 17 sectors, including startups, suppliers, NASA contractors, MRO firms, and international companies.
- Export tracked applications to CSV from the sidebar.
- Open a company people search on LinkedIn from each job detail panel.

“First found” is when this installation discovered a job, **not its publication date**. Results include worldwide technical internships and co-ops; matching uses title keywords, not degree, citizenship, location, or eligibility checks. Review the actual posting. The tracker always retains closed jobs; Discover hides them unless Include closed is checked.

## Data and settings

Your data lives in `data/jobs.sqlite3`, excluded from Git. To back up or transfer everything, stop the app and copy this file. CSV is an export for external use, not a full database backup or an import format. No Supabase account is needed.

```sh
python app.py --port 8766 --interval 120
python app.py --no-refresh
python app.py --data-dir /path/to/private/folder
python main.py
```

`--interval` is in minutes (minimum 5). `--no-refresh` disables startup/scheduled checks but keeps manual refresh. `--no-browser` prevents opening a browser. `python main.py` runs one collection using the same database as the dashboard. Run one collector at a time; do not run the CLI alongside dashboard refreshes. `AEROSPACE_DATA_DIR` also overrides the storage folder. The server binds only to this computer; it is not a public web server.

Edit `companies.json` to maintain sources; changes are loaded each refresh. Use `"enabled": false` to skip a company. Every entry needs a unique `name`, a `category`, an HTTPS `careers_url`, and a `provider`. Greenhouse, Lever, Ashby, and SmartRecruiters need a `board`; Workday needs `host`, `tenant`, and `site`. Use `"provider": "manual"` when no stable public feed is available. Keep company names stable because they form part of job identity. Changing a name creates separate history.

## Source coverage and limitations

The active collector supports **Greenhouse, Lever, Workday, Ashby, and SmartRecruiters**, with bounded concurrency, transient-error retries, response validation, and pagination. The Company directory includes 300+ employers even when their hiring platforms do not expose a stable public feed. Those entries open the official careers page and are labeled manual; they do not produce automatic listings until a reliable adapter is added. The catalog is intentionally broad, but companies, career pages, and internship programs change continuously, so it cannot be a permanent claim of literal completeness.

Failed automatic sources preserve their previous listings. A successful source can legitimately have no matching internships. Workday collection has a 150-second per-company deadline; if it cannot finish, prior data is preserved. The directory covers US and international employers, but the automatic title filter does not determine citizenship, work authorization, degree year, security-clearance eligibility, or whether a company currently has an internship open.

The original `main.py` provider helpers remain for compatibility, but both entry points use the new collector in `hunter.py`. Its contracts follow [Greenhouse's Job Board API](https://docs.greenhouse.io/job-board.html), [Lever's Postings API](https://github.com/lever/postings-api), and the public Ashby and SmartRecruiters job-board responses. Workday and some other career-site endpoints can change without notice.

The LinkedIn shortcut is **not an automatic connection integration**. It opens people search and does not read your account or identify connections inside this app. LinkedIn API access is restricted; see [LinkedIn API access](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access). A future connection feature would need approved access or an explicit user-provided contacts import.

## Optional Discord alerts

Set `DISCORD_WEBHOOK_URL` in the environment before starting the app or CLI. Treat it like a password; do not commit it. No alerts are sent without it. On the first enabled run, all currently open, previously unnotified matches are eligible for alerts, including jobs collected before Discord was configured.

Alerts are marked delivered **only after a successful response**. Failed deliveries remain pending and retry at the next refresh. Delivery is at least once: an ambiguous network failure or a crash after Discord accepts a message can cause a duplicate. Allowed mentions are disabled.

The GitHub Actions scraper keeps separate history through Actions cache and runs every 12 hours. Cache eviction can reset that history and cause repeat alerts. The cloud run does not synchronize with your local dashboard. Existing `seen_jobs.json` and Supabase IDs are not migrated: the new database needs complete listings, so its first collection treats matches as newly discovered. Keep old files for reference.

## Development and checks

```sh
python -m unittest discover -s tests -v
```

Tests use temporary databases, mocked job boards and Discord, and a local HTTP server. They cover persistence, deduplication, status validation, source failures, pagination, notification retries, exports, and local request protections. CI runs on Windows and Linux with Python 3.11 and 3.14.

Files: `app.py` serves the local UI and schedules checks; `hunter.py` owns collection and SQLite storage; `companies.json` defines sources; `static/` contains the browser interface. There is no build step.
