"""Loopback HTTP file server for access-routing tests.

Modes: ranges (206 + Accept-Ranges), no-range (ignores Range, returns 200 full body)
and etag_changes (ETag changes after the first request, so If-Match fails with 412).
log entries: (method, range_header_or_None, status, bytes_sent).
"""
from __future__ import annotations

import itertools
import re
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@contextmanager
def serve(files: dict[str, bytes], *, ranges: bool = True, etag_changes: bool = False):
    log: list[tuple[str, str | None, int, int]] = []
    lock = threading.Lock()
    counter = itertools.count()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _etag(self) -> str:
            return f'"v{next(counter)}"' if etag_changes else '"fixed"'

        def _record(self, method, rng, status, sent):
            with lock:
                log.append((method, rng, status, sent))

        def do_HEAD(self):
            data = files.get(self.path.lstrip("/"))
            if data is None:
                self.send_error(404)
                self._record("HEAD", None, 404, 0)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            if ranges:
                self.send_header("Accept-Ranges", "bytes")
            self.send_header("ETag", self._etag())
            self.end_headers()
            self._record("HEAD", None, 200, 0)

        def do_GET(self):
            data = files.get(self.path.lstrip("/"))
            header = self.headers.get("Range")
            if data is None:
                self.send_error(404)
                self._record("GET", header, 404, 0)
                return
            etag = self._etag()
            if_match = self.headers.get("If-Match")
            if if_match is not None and etag_changes and if_match != etag:
                self.send_error(412)
                self._record("GET", header, 412, 0)
                return
            start, end, status = 0, len(data) - 1, 200
            if header and ranges:
                first, last = re.fullmatch(r"bytes=(\d*)-(\d*)", header).groups()
                if first == "":
                    start = max(0, len(data) - int(last))
                else:
                    start, end = int(first), min(int(last) if last else len(data) - 1, len(data) - 1)
                status = 206
            body = data[start : end + 1]
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", etag)
            if ranges:
                self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
            self.end_headers()
            written = 0
            try:
                for offset in range(0, len(body), 65536):   # chunked, so an early close is measurable
                    self.wfile.write(body[offset:offset + 65536])
                    written += len(body[offset:offset + 65536])
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
            self._record("GET", header, status, written)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", log
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def plain_gets(log) -> int:
    """GET requests without a Range header (whole-object reads)."""
    return sum(1 for method, rng, _, _ in log if method == "GET" and rng is None)


def ranged_gets(log) -> int:
    return sum(1 for method, rng, _, _ in log if method == "GET" and rng is not None)


def bytes_sent(log) -> int:
    return sum(sent for *_, sent in log)
