#!/usr/bin/env python3
"""
Simple mock HTTP server for /api/chat and /v1/api/chat used for local testing.
No external dependencies required — uses Python stdlib only.

Run (Windows PowerShell):
    python tools/mock_server.py

Run (WSL):
    python3 tools/mock_server.py

The server listens on 0.0.0.0:11435 by default so it's reachable from WSL <-> Windows.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import uuid
import argparse
import time

# module-level latency (seconds). Set by `run()` from CLI arg `--latency`.
LATENCY = 0.0

# default mock models exposed by /models
DEFAULT_MODELS = [
    {"name": "mistral:7b"},
    {"name": "qwen3:1.7b"},
    {"name": "qwen2-math:1.5b"},
]

class Handler(BaseHTTPRequestHandler):
    # Use HTTP/1.1 so we can emit chunked transfer responses for streaming
    protocol_version = 'HTTP/1.1'
    def _set_json(self, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()

    def do_GET(self):
        try:
            if LATENCY > 0:
                time.sleep(LATENCY)
            # models discovery endpoint
            if self.path == '/models' or self.path == '/api/models':
                self._set_json(200)
                try:
                    self.wfile.write(json.dumps({"models": DEFAULT_MODELS}).encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    self.log_error('Client disconnected during /models response: %s', e)
                return
            if self.path == '/health':
                self._set_json(200)
                try:
                    self.wfile.write(json.dumps({'status': 'healthy'}).encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    self.log_error('Client disconnected during /health response: %s', e)
                return
            if self.path == '/' or self.path.startswith('/api'):
                self._set_json(200)
                try:
                    self.wfile.write(json.dumps({'status': 'ok', 'paths': ['/api/chat','/v1/api/chat']}).encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    self.log_error('Client disconnected during GET response: %s', e)
            else:
                self._set_json(404)
                try:
                    self.wfile.write(json.dumps({'error': 'not found'}).encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    self.log_error('Client disconnected during GET 404 response: %s', e)
        except Exception as e:
            # Catch-all to avoid crashing the server for unexpected errors
            self.log_error('Unhandled error in do_GET: %s', e)

    def do_POST(self):
        try:
            if LATENCY > 0:
                time.sleep(LATENCY)
            if self.path not in ('/api/chat', '/v1/api/chat'):
                self._set_json(404)
                try:
                    self.wfile.write(json.dumps({'error': 'not found'}).encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    self.log_error('Client disconnected during POST 404 response: %s', e)
                return

            length = int(self.headers.get('content-length', 0))
            try:
                payload = self.rfile.read(length).decode('utf-8') if length else ''
            except (ConnectionResetError, OSError) as e:
                self.log_error('Client disconnected while reading request body: %s', e)
                return

            try:
                data = json.loads(payload) if payload else {}
            except Exception:
                self._set_json(400)
                try:
                    self.wfile.write(json.dumps({'error': 'invalid json'}).encode('utf-8'))
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    self.log_error('Client disconnected during invalid-json response: %s', e)
                return

            # simple echo-style mock reply
            req_id = str(uuid.uuid4())
            user_msg = None
            try:
                msgs = data.get('messages') or []
                if isinstance(msgs, list) and msgs:
                    user_msg = msgs[-1].get('content')
            except Exception:
                user_msg = None

            # prepare model-specific reply text
            model = data.get('model')
            if model and isinstance(model, str):
                m = model.lower()
            else:
                m = ''

            if m and 'math' in m:
                reply_text = f"Mock math model solving: {user_msg}"
            elif m and 'qwen' in m:
                reply_text = f"Mock Qwen response: {user_msg}"
            elif m:
                reply_text = f"Mock response for {model}: {user_msg}"
            else:
                reply_text = f"Mock reply echo: {user_msg}" if user_msg else 'Mock reply'

            # If client requested streaming, use chunked transfer encoding
            if data.get('stream'):
                try:
                    # send headers (no Content-Length) and enable chunked transfer
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json; charset=utf-8')
                    self.send_header('Transfer-Encoding', 'chunked')
                    self.send_header('request-id', req_id)
                    self.end_headers()

                    # simple tokenization: split on whitespace to produce small chunks
                    tokens = reply_text.split()
                    for tok in tokens:
                        chunk_obj = {'request_id': req_id, 'model': data.get('model'), 'delta': tok, 'done': False}
                        chunk_bytes = (json.dumps(chunk_obj) + '\n').encode('utf-8')
                        # write chunk: <size in hex>\r\n<data>\r\n
                        self.wfile.write(f"{len(chunk_bytes):x}\r\n".encode('utf-8'))
                        self.wfile.write(chunk_bytes)
                        self.wfile.write(b"\r\n")
                        try:
                            self.wfile.flush()
                        except (ConnectionResetError, BrokenPipeError, OSError) as e:
                            self.log_error('Client disconnected during chunked streaming: %s', e)
                            return
                        # small delay between chunks to better simulate streaming
                        time.sleep(0.05)

                    # final done message
                    final_obj = {'request_id': req_id, 'model': data.get('model'), 'delta': '', 'done': True}
                    final_bytes = (json.dumps(final_obj) + '\n').encode('utf-8')
                    self.wfile.write(f"{len(final_bytes):x}\r\n".encode('utf-8'))
                    self.wfile.write(final_bytes)
                    self.wfile.write(b"\r\n")
                    # end of chunks
                    self.wfile.write(b"0\r\n\r\n")
                    try:
                        self.wfile.flush()
                    except (ConnectionResetError, BrokenPipeError, OSError) as e:
                        self.log_error('Client disconnected after final chunk: %s', e)
                    return
                except (ConnectionResetError, BrokenPipeError, OSError) as e:
                    self.log_error('Streaming failed due to client disconnect: %s', e)
                    return

            # non-stream response
            reply = {
                'request_id': req_id,
                'model': data.get('model'),
                'reply': f'Mock reply echo: {user_msg}' if user_msg else 'Mock reply',
                'received': data,
            }

            try:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('request-id', req_id)
                self.end_headers()
                self.wfile.write(json.dumps(reply).encode('utf-8'))
            except (ConnectionResetError, BrokenPipeError, OSError) as e:
                self.log_error('Client disconnected during POST response: %s', e)
        except Exception as e:
            self.log_error('Unhandled error in do_POST: %s', e)

        reply = {
            'request_id': req_id,
            'model': data.get('model'),
            'reply': f'Mock reply echo: {user_msg}' if user_msg else 'Mock reply',
            'received': data,
        }

        # include request-id header for client parsing
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('request-id', req_id)
        self.end_headers()
        self.wfile.write(json.dumps(reply).encode('utf-8'))


def run(host='0.0.0.0', port=11435):
    global LATENCY
    server = ThreadingHTTPServer((host, port), Handler)
    print('Streaming supported: yes')
    if LATENCY:
        print(f'Latency simulation: {LATENCY}s')
    print(f'Mock server listening on http://{host}:{port} (CTRL+C to stop)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Shutting down')
        server.server_close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=11435)
    parser.add_argument('--latency', type=float, default=0.0, help='Add artificial response latency in seconds')
    args = parser.parse_args()
    LATENCY = float(args.latency)
    run(args.host, args.port)
