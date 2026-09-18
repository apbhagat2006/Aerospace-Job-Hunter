"""Native Windows launcher for the local Flightpath dashboard."""
import os
import threading
from pathlib import Path

from http.server import ThreadingHTTPServer

from app import Application, handler_for
from hunter import Store


APP_NAME = 'Flightpath'


def user_data_dir():
    """Return a stable, per-user directory that survives executable updates."""
    override = os.getenv('FLIGHTPATH_DATA_DIR') or os.getenv('AEROSPACE_DATA_DIR')
    if override:
        return Path(override).expanduser()
    local_app_data = os.getenv('LOCALAPPDATA')
    base = Path(local_app_data) if local_app_data else Path.home() / 'AppData' / 'Local'
    return base / APP_NAME / 'data'


class LocalDashboard:
    """Own the HTTP server and refresh scheduler for one desktop window."""

    def __init__(self, data_dir=None, interval=360, auto_refresh=True):
        self.app = Application(Store(Path(data_dir or user_data_dir()) / 'jobs.sqlite3'))
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.app))
        self.stop_event = threading.Event()
        self.interval = interval
        self.auto_refresh = auto_refresh
        self.server_thread = None
        self.scheduler_thread = None
        self._close_lock = threading.Lock()
        self._closed = False

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server.server_port}'

    def start(self):
        if self.server_thread and self.server_thread.is_alive():
            return
        self.server_thread = threading.Thread(target=self.server.serve_forever,
                                              name='flightpath-server', daemon=True)
        self.server_thread.start()
        if self.auto_refresh:
            self.scheduler_thread = threading.Thread(target=self._schedule,
                                                     name='flightpath-refresh', daemon=True)
            self.scheduler_thread.start()

    def _schedule(self):
        self.app.start_refresh()
        while not self.stop_event.wait(self.interval * 60):
            self.app.start_refresh()

    def close(self):
        """Stop accepting requests as soon as the desktop window closes."""
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            self.stop_event.set()
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread and self.server_thread is not threading.current_thread():
            self.server_thread.join(timeout=5)


def show_error(message):
    """Show startup failures even in a windowed executable with no terminal."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, str(message), f'{APP_NAME} could not start', 0x10)
    except Exception:
        pass


def main():
    dashboard = None
    try:
        import webview

        dashboard = LocalDashboard()
        dashboard.start()
        window = webview.create_window(
            f'{APP_NAME} · Aerospace Job Hunter',
            dashboard.url,
            width=1440,
            height=900,
            min_size=(960, 640),
            background_color='#08131b',
            text_select=True,
        )
        window.events.closed += dashboard.close
        webview.start(private_mode=False)
    except Exception as exc:
        show_error(exc)
    finally:
        if dashboard is not None:
            dashboard.close()


if __name__ == '__main__':
    main()
