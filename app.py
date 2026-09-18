"""Run with python app.py. Binds only to the local computer."""
import argparse
import asyncio
import csv
import io
import json
import os
import secrets
import sqlite3
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from hunter import ROOT, Store, load_companies, now, refresh


class Application:
    def __init__(self, store):
        self.store = store
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.state = {'running': False, 'last_finished': None, 'added': 0, 'error': None}

    def start_refresh(self):
        with self.lock:
            if self.state['running']:
                return False
            self.state.update(running=True, error=None)
        threading.Thread(target=self._refresh, daemon=True).start()
        return True

    def _refresh(self):
        try:
            result = asyncio.run(refresh(self.store))
            with self.lock:
                self.state.update(added=result['added'], error=result['notification_error'])
        except Exception:
            with self.lock:
                self.state['error'] = 'Refresh could not complete. Check companies.json and your network, then retry.'
        finally:
            with self.lock:
                self.state.update(running=False, last_finished=now())


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def valid_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def send(self, status, body, mime='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {'error': 'Local access only'})
            path = urlsplit(self.path).path
            if path == '/api/state':
                with app.lock:
                    state = dict(app.state)
                catalog = [{k: c.get(k) for k in ('name', 'category', 'careers_url', 'provider', 'location')}
                           for c in load_companies() if c.get('enabled', True)]
                return self.send(200, {**app.store.snapshot(), 'catalog': catalog,
                                       'refresh': state, 'token': app.token})
            if path == '/api/export':
                stream = io.StringIO(newline='')
                fields = ['company', 'title', 'location', 'url', 'status', 'notes', 'first_seen', 'last_seen', 'active']
                writer = csv.DictWriter(stream, fields, extrasaction='ignore')
                writer.writeheader()
                for job in app.store.snapshot()['jobs']:
                    if job['status'] != 'discovered':
                        # Prevent spreadsheet formulas in imported remote text and notes.
                        writer.writerow({k: "'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v for k, v in job.items()})
                return self.send(200, stream.getvalue().encode('utf-8-sig'), 'text/csv; charset=utf-8')
            assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                      '/style.css': ('style.css', 'text/css'), '/directory.css': ('directory.css', 'text/css')}
            if path in assets:
                name, mime = assets[path]
                return self.send(200, (ROOT / 'static' / name).read_bytes(), mime + '; charset=utf-8')
            self.send(404, {'error': 'Not found'})

        def do_POST(self):
            if not self.valid_host() or self.headers.get('X-App-Token') != app.token:
                return self.send(403, {'error': 'Reload the dashboard and try again.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 0 or length > 65536:
                    raise ValueError('Request is too large')
                body = json.loads(self.rfile.read(length) or '{}')
                if not isinstance(body, dict):
                    raise ValueError('Expected an object')
                if self.path == '/api/refresh':
                    return self.send(202, {'started': app.start_refresh()})
                if self.path.startswith('/api/jobs/'):
                    app.store.update(self.path.split('/')[-1], body.get('status'), body.get('notes', ''))
                    return self.send(200, {'saved': True})
                self.send(404, {'error': 'Not found'})
            except (ValueError, TypeError):
                self.send(400, {'error': 'Invalid data. Choose a valid stage and keep notes under 10,000 characters.'})
            except KeyError:
                self.send(404, {'error': 'Job not found'})
            except sqlite3.Error:
                self.send(500, {'error': 'Could not save to the local database. Please retry.'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description='Aerospace internship dashboard')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--interval', type=float, default=360, help='Refresh interval in minutes (minimum 5)')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--no-refresh', action='store_true', help='Disable startup and scheduled refresh; manual refresh remains available')
    parser.add_argument('--data-dir', type=Path, default=Path(os.getenv('AEROSPACE_DATA_DIR', str(ROOT / 'data'))))
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 5 <= args.interval <= 525600:
        parser.error('Use a port from 1–65535 and an interval from 5–525600 minutes.')
    app = Application(Store(args.data_dir / 'jobs.sqlite3'))
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(app))
    except OSError as exc:
        parser.exit(1, f'Cannot open dashboard: {exc}. Try --port 8766.\n')
    stop = threading.Event()
    if not args.no_refresh:
        def schedule():
            app.start_refresh()
            while not stop.wait(args.interval * 60):
                app.start_refresh()
        threading.Thread(target=schedule, daemon=True).start()
    url = f'http://127.0.0.1:{args.port}'
    print(f'Aerospace Job Hunter: {url}\nData: {app.store.path}\nKeep this window open for updates. Press Ctrl+C to stop.', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


if __name__ == '__main__':
    main()
