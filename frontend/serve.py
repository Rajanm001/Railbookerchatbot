"""No-cache HTTP server for development. Forces browser to always fetch fresh files."""
import http.server
import functools
import os
import sys

class NoCacheHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler that sets no-cache headers on every response."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    directory = os.path.dirname(os.path.abspath(__file__))
    handler = functools.partial(NoCacheHandler, directory=directory)
    server = http.server.HTTPServer(("0.0.0.0", port), handler)
    print(f"Serving {directory} on http://localhost:{port} (no-cache)")
    server.serve_forever()
