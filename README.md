# Flightpath · Aerospace Job Hunter

A local internship discovery dashboard and application tracker. No account, cloud database, Node installation, or Discord configuration required.

## Install on Windows

1. Download **Flightpath.exe** from the [latest release](https://github.com/apbhagat2006/Aerospace-Job-Hunter/releases/latest).
2. Move it somewhere permanent, such as your Applications folder.
3. Double-click it. There is no installer, terminal, Python setup, account, or browser tab.

Flightpath opens in its own window and checks jobs on startup and every six hours while it is open. **Closing the Flightpath window stops the local server and job checks immediately.** Open the same executable whenever you want to use it again. Your computer must be awake and online to collect new jobs; saved listings remain available offline.

The executable can be used like any other Windows app:

- While it is open, right-click its taskbar icon and choose **Pin to taskbar**.
- Right-click `Flightpath.exe` and choose **Pin to Start**.
- To make a desktop shortcut, right-click the executable and choose **Show more options → Send to → Desktop (create shortcut)**.

Download the executable only from this repository's Releases page. Release builds are produced by the repository's Windows build workflow from the tagged source.

## macOS, Linux, and development use

The ready-to-run executable is currently built for Windows. To run from source, install **Python 3.11 or newer** and create an environment:

```sh
python -m venv .venv
```

Windows development:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

macOS / Linux:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

The source-mode server opens **http://127.0.0.1:8765** in the default browser and runs until stopped with Ctrl+C. `start.ps1` is retained as a Windows developer convenience.

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

The Windows app stores its database at `%LOCALAPPDATA%\Flightpath\data\jobs.sqlite3`, separate from the executable so upgrades do not erase saved jobs, application stages, or notes. To back up or transfer everything, close Flightpath and copy this file. Source-mode data lives in `data/jobs.sqlite3`. CSV is an export for external use, not a full database backup or an import format. No Supabase account is needed.

```sh
python app.py --port 8766 --interval 120
python app.py --no-refresh
python app.py --data-dir /path/to/private/folder
python main.py
```

`--interval` is in minutes (minimum 5). `--no-refresh` disables startup/scheduled checks but keeps manual refresh. `--no-browser` prevents opening a browser. `python main.py` runs one collection using the same database as the source-mode dashboard. Run one collector at a time; do not run the CLI alongside dashboard refreshes. `AEROSPACE_DATA_DIR` overrides the source-mode storage folder. `FLIGHTPATH_DATA_DIR` overrides the Windows app storage folder. The server binds only to this computer; it is not a public web server.

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

To build the Windows executable on Windows:

```powershell
python -m pip install -r requirements-build.txt
python tools/build_windows.py
```

The result is `dist/Flightpath.exe`. PyInstaller bundles the Python runtime, company catalog, web interface, and native pywebview host into the windowed executable. The same build runs automatically for version tags and attaches `Flightpath.exe` to the matching GitHub release.

Files: `desktop.py` owns the native window and its server lifetime; `app.py` serves the local UI and supports browser-based development; `hunter.py` owns collection and SQLite storage; `companies.json` defines sources; `static/` contains the interface; `tools/build_windows.py` creates the Windows icon and executable.
