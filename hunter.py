"""Local persistence and bounded, observable job collection."""
import asyncio
import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
from main import is_target_role

ROOT = Path(__file__).resolve().parent
STATUSES = ('discovered', 'saved', 'applied', 'interviewing', 'offer', 'rejected', 'withdrawn')
AUTOMATED_PROVIDERS = ('greenhouse', 'lever', 'workday', 'ashby', 'smartrecruiters')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def load_companies():
    companies = json.loads((ROOT / 'companies.json').read_text(encoding='utf-8'))
    names = set()
    for company in companies:
        if not isinstance(company, dict) or not company.get('name') or company['name'] in names:
            raise ValueError('Every company needs a unique, non-empty name.')
        names.add(company['name'])
        if company.get('provider', 'manual') not in (*AUTOMATED_PROVIDERS, 'manual'):
            raise ValueError(f"Unknown provider for {company['name']}.")
        url = company.get('careers_url', '')
        if not isinstance(url, str) or not url.startswith('https://'):
            raise ValueError(f"{company['name']} needs an HTTPS careers_url.")
    return companies


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, company TEXT NOT NULL, title TEXT NOT NULL,
                    location TEXT NOT NULL, url TEXT NOT NULL, first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'discovered', notes TEXT NOT NULL DEFAULT '',
                    updated_at TEXT NOT NULL, notified INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS sources (
                    company TEXT PRIMARY KEY, state TEXT, detail TEXT, checked_at TEXT);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def snapshot(self):
        with self.connect() as db:
            return {'jobs': [dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY first_seen DESC, company, title')],
                    'sources': [dict(r) for r in db.execute('SELECT * FROM sources ORDER BY company')]}

    def record(self, company, jobs=None, error=None):
        stamp = now()
        added = 0
        with self.connect() as db:
            if error is None:
                db.execute('UPDATE jobs SET active=0 WHERE company=?', (company,))
                for job in jobs:
                    if not is_target_role(job['title']):
                        continue
                    key = hashlib.sha256(f"{company}:{job['id']}".encode()).hexdigest()[:24]
                    result = db.execute('''INSERT OR IGNORE INTO jobs
                        (id,company,title,location,url,first_seen,last_seen,updated_at)
                        VALUES (?,?,?,?,?,?,?,?)''',
                        (key, company, job['title'], job['location'], job['url'], stamp, stamp, stamp))
                    added += result.rowcount
                    db.execute('UPDATE jobs SET title=?,location=?,url=?,last_seen=?,active=1 WHERE id=?',
                               (job['title'], job['location'], job['url'], stamp, key))
            db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?)',
                       (company, 'error' if error else 'ok', error or f'{len(jobs)} listings checked', stamp))
        return added

    def record_source(self, company, state, detail):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?)',
                       (company, state, detail, now()))

    def update(self, key, status, notes):
        if status not in STATUSES or not isinstance(notes, str) or len(notes) > 10000:
            raise ValueError('Choose a valid stage and keep notes under 10,000 characters.')
        with self.connect() as db:
            if not db.execute('UPDATE jobs SET status=?,notes=?,updated_at=? WHERE id=?',
                              (status, notes, now(), key)).rowcount:
                raise KeyError(key)


async def request(client, method, url, **kwargs):
    for attempt in range(3):
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code != 429 and exc.response.status_code < 500:
                raise
            if attempt == 2:
                raise
            await asyncio.sleep(2 ** attempt)


async def collect(client, company):
    provider = company['provider']
    if provider == 'greenhouse':
        data = await request(client, 'GET', f"https://boards-api.greenhouse.io/v1/boards/{company['board']}/jobs")
        rows = data['jobs']
        jobs = [dict(id=str(j['id']), title=j['title'], location=(j.get('location') or {}).get('name') or 'Not specified', url=j['absolute_url']) for j in rows]
    elif provider == 'lever':
        rows, offset = [], 0
        while True:
            batch = await request(client, 'GET', f"https://api.lever.co/v0/postings/{company['board']}", params={'mode': 'json', 'skip': offset, 'limit': 100})
            if not isinstance(batch, list):
                raise ValueError('Unexpected job board response')
            rows.extend(batch)
            if len(batch) < 100:
                break
            offset += len(batch)
            if offset > 20000:
                raise ValueError('Pagination limit reached; results were not saved')
        jobs = [dict(id=str(j['id']), title=j['text'], location=(j.get('categories') or {}).get('location') or 'Not specified', url=j['hostedUrl']) for j in rows]
    elif provider == 'workday':
        host, tenant, site = (company[k] for k in ('host', 'tenant', 'site'))
        rows, paths, expected_total = [], set(), None
        for page in range(1000):
            data = await request(client, 'POST', f'https://{host}/wday/cxs/{tenant}/{site}/jobs',
                                 json={'appliedFacets': {}, 'limit': 20, 'offset': len(rows), 'searchText': ''})
            batch = data['jobPostings']
            if expected_total is None:
                expected_total = int(data['total'])
            total = expected_total
            if not batch and len(rows) < total:
                raise ValueError('Incomplete pagination; previous listings preserved')
            for job in batch:
                if job['externalPath'] in paths:
                    raise ValueError('Repeated page; previous listings preserved')
                paths.add(job['externalPath'])
            rows.extend(batch)
            if len(rows) >= total:
                break
        else:
            raise ValueError('Pagination limit reached')
        jobs = [dict(id=j['externalPath'], title=j['title'], location=j.get('locationsText') or 'Not specified', url=f"https://{host}/en-US/{site}{j['externalPath']}") for j in rows]
    elif provider == 'ashby':
        data = await request(client, 'GET', f"https://api.ashbyhq.com/posting-api/job-board/{company['board']}",
                             params={'includeCompensation': 'true'})
        rows = data['jobs']
        jobs = [dict(id=str(j.get('jobUrl') or j.get('applyUrl')), title=j['title'],
                     location=j.get('location') or 'Not specified',
                     url=j.get('jobUrl') or j['applyUrl']) for j in rows]
    elif provider == 'smartrecruiters':
        rows, offset = [], 0
        while True:
            data = await request(client, 'GET', f"https://api.smartrecruiters.com/v1/companies/{company['board']}/postings",
                                 params={'limit': 100, 'offset': offset})
            batch = data['content']
            rows.extend(batch)
            if len(rows) >= int(data.get('totalFound', len(rows))) or not batch:
                break
            offset += len(batch)
            if offset > 20000:
                raise ValueError('Pagination limit reached; results were not saved')
        jobs = [dict(id=str(j['id']), title=j['name'],
                     location=', '.join(str((j.get('location') or {}).get(k, '')).strip()
                                        for k in ('city', 'region', 'country')
                                        if str((j.get('location') or {}).get(k, '')).strip()) or 'Not specified',
                     url=j.get('ref') or f"https://jobs.smartrecruiters.com/{company['board']}/{j['id']}") for j in rows]
    elif provider == 'manual':
        return []
    else:
        raise ValueError(f'{provider} needs a verified adapter; check the company careers page manually')
    if any(not j['id'] or not isinstance(j['title'], str) or not j['url'].startswith('https://') for j in jobs):
        raise ValueError('Invalid listing data; previous listings preserved')
    return jobs


async def refresh(store, companies=None):
    if companies is None:
        companies = load_companies()
    enabled = [company for company in companies if company.get('enabled', True)]
    for company in enabled:
        if company.get('provider', 'manual') == 'manual':
            store.record_source(company['name'], 'manual', 'Official careers page — check manually')
    automated = [company for company in enabled if company.get('provider', 'manual') != 'manual']
    semaphore = asyncio.Semaphore(4)
    async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
        async def one(company):
            async with semaphore:
                if company.get('provider', 'manual') == 'manual':
                    store.record_source(company['name'], 'manual', 'Official careers page — check manually')
                    return 0
                try:
                    jobs = await asyncio.wait_for(collect(client, company), timeout=150)
                    return store.record(company['name'], jobs)
                except Exception as exc:
                    # No raw request URLs: errors should never expose credentials.
                    if isinstance(exc, httpx.HTTPStatusError):
                        detail = f'HTTP {exc.response.status_code}: board unavailable; verify the company route'
                    elif isinstance(exc, (KeyError, TypeError)):
                        detail = 'Unexpected listing format; previous listings preserved. This source needs review.'
                    elif isinstance(exc, asyncio.TimeoutError):
                        detail = 'Source exceeded the collection deadline; previous listings preserved.'
                    else:
                        detail = str(exc) or type(exc).__name__
                    store.record(company['name'], error=detail[:240])
                    return 0
        counts = await asyncio.gather(*(one(c) for c in automated))
        webhook = os.getenv('DISCORD_WEBHOOK_URL')
        notification_error = None
        if webhook:
            with store.connect() as db:
                pending = [dict(r) for r in db.execute('SELECT * FROM jobs WHERE notified=0 AND active=1')]
            for job in pending:
                try:
                    response = await client.post(webhook, json={'content': f"New internship at {job['company']}\n{job['title']}\n{job['location']}\n{job['url']}"[:1900], 'allowed_mentions': {'parse': []}})
                    response.raise_for_status()
                    with store.connect() as db:
                        db.execute('UPDATE jobs SET notified=1 WHERE id=?', (job['id'],))
                    await asyncio.sleep(.5)
                except httpx.HTTPError:
                    notification_error = 'Discord delivery failed. Unsent alerts will retry on the next refresh.'
                    break
        return {'added': sum(counts), 'notification_error': notification_error}
