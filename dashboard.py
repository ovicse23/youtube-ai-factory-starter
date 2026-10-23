#!/usr/bin/env python3
"""Local-only research settings UI. No external requests or paid AI calls."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from research_router import load_settings, save_settings, research_instructions
from upload_timing import compute_upload_windows

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'dashboard' / 'index.html'


class Handler(BaseHTTPRequestHandler):
    def _reply(self, status: int, data: bytes, content_type: str):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status, obj):
        self._reply(status, json.dumps(obj).encode('utf-8'), 'application/json; charset=utf-8')

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/':
            return self._reply(200, STATIC.read_bytes(), 'text/html; charset=utf-8')
        if url.path == '/dashboard/app.js':
            return self._reply(200, (ROOT / 'dashboard' / 'app.js').read_bytes(), 'text/javascript; charset=utf-8')
        if url.path == '/api/settings':
            return self._json(200, load_settings())
        if url.path == '/api/research-plan':
            topic = parse_qs(url.query).get('topic', ['Research 5 original YouTube niches'])[0][:400]
            return self._reply(200, research_instructions(load_settings(), topic).encode('utf-8'), 'text/plain; charset=utf-8')
        if url.path == '/api/upload-plan':
            qs = parse_qs(url.query)
            aspect = qs.get('aspect', ['9:16'])[0]
            if aspect not in ('9:16', '16:9'):
                return self._json(400, {'error': 'aspect must be 9:16 or 16:9'})
            settings = load_settings()
            return self._json(200, compute_upload_windows(
                aspect=aspect,
                target_countries=settings['research']['target_countries'],
                creator_tz=settings['publishing']['creator_timezone'],
            ))
        return self._json(404, {'error': 'Not found'})

    def do_POST(self):
        if self.path != '/api/research-settings':
            return self._json(404, {'error': 'Not found'})
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self._json(403, {'error': 'Origin not allowed'})
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self._json(415, {'error': 'Send application/json'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if size < 2 or size > 8192:
                raise ValueError('Request body length invalid')
            patch = json.loads(self.rfile.read(size))
            allowed = {'provider', 'depth', 'fallback_to_gemini', 'target_countries', 'creator_timezone'}
            if not isinstance(patch, dict) or set(patch) - allowed:
                raise ValueError('Only research provider, depth, fallback, target_countries, and creator_timezone can be updated')
            settings = load_settings()
            if 'creator_timezone' in patch:
                settings['publishing']['creator_timezone'] = patch.pop('creator_timezone')
            settings['research'].update(patch)
            return self._json(200, save_settings(settings))
        except (json.JSONDecodeError, ValueError) as e:
            return self._json(400, {'error': str(e)})


def serve(port=8787):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'Research settings running at http://127.0.0.1:{port}/ (Ctrl+C to stop)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port', type=int, default=8787)
    serve(p.parse_args().port)
