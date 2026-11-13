"""供应方协议演练服务，只监听回环地址。"""
from __future__ import annotations
import argparse
import base64
import copy
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import socket
import threading
from urllib.parse import parse_qs, urlsplit
from xml.sax.saxutils import escape
DATA = json.loads((Path(__file__).resolve().parents[1] / 'fixtures/source.json').read_text(encoding='utf-8'))

class Source:

    def __init__(self):
        self.lock = threading.RLock()
        self.state = {'generation': 1, 'requests': [], 'jobs': {}, 'sessions': {}, 'next_session': 1}

    def route(self, method, target, headers, body):
        with self.lock:
            parsed = urlsplit(target)
            path, query = (parsed.path, parse_qs(parsed.query, keep_blank_values=True))
            if path == '/__state':
                return (200, {}, json.dumps(self.state, ensure_ascii=False).encode())
            if path == '/__control' and method == 'POST':
                self.state.update(json.loads(body))
                return (200, {}, b'{}')
            self.state['requests'].append({'method': method, 'target': target, 'headers': dict(headers), 'body': body.decode('utf-8', 'replace')})
            kind = DATA['kind']
            if path == '/session':
                sid = str(self.state['next_session'])
                self.state['next_session'] += 1
                csrf = 'csrf-' + sid
                self.state['sessions'][sid] = csrf
                return (200, {'Set-Cookie': 'sid=%s; Path=/; HttpOnly' % sid}, json.dumps({'csrf': csrf}).encode())
            sid = headers.get('Cookie', '').removeprefix('sid=')
            if sid not in self.state['sessions']:
                return (401, {}, b'{}')
            jobs = self.state['jobs']
            if path == '/exports' and method == 'POST':
                if not self.state['sessions'][sid] or headers.get('X-CSRF-Token') != self.state['sessions'][sid]:
                    return (403, {}, b'{}')
                self.state['sessions'][sid] = ''
                form = json.loads(body)
                ref = form['client_ref']
                if ref in jobs and jobs[ref]['form'] != form:
                    return (409, {}, b'{}')
                jobs.setdefault(ref, {'job_id': 'job-' + str(len(jobs) + 1), 'form': form, 'polls': 0})
                if self.state.pop('lose_submit_response', False):
                    return (None, {}, b'')
                return self.json({'job_id': jobs[ref]['job_id']})
            if path == '/exports':
                job = jobs.get(query.get('client_ref', [''])[0])
                return self.json({'job': copy.deepcopy(job)})
            if path.startswith('/jobs/'):
                job = next((v for v in jobs.values() if v['job_id'] == path.split('/')[2]), None)
                if job is None:
                    return (404, {}, b'{}')
                if path.endswith('/refresh') and method == 'POST':
                    self.state['link_expired'] = False
                job['polls'] += 1
                content = DATA['content'].encode()
                status = self.state.get('job_status', 'ready' if job['polls'] >= 2 else 'running')
                payload = {'status': status, 'download_url': '/download', 'length': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
                return (200, {'Retry-After': '2'}, json.dumps(payload).encode())
            if path == '/download':
                if self.state.get('link_expired'):
                    return (403, {}, b'')
                return (200, {'Content-Type': 'application/octet-stream'}, DATA['content'].encode())
            return (404, {}, b'not found')

    @staticmethod
    def json(value, status=200):
        return (status, {'Content-Type': 'application/json; charset=utf-8'}, json.dumps(value, ensure_ascii=False).encode())

def make_server(port=0):
    source = Source()

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
            try:
                status, headers, payload = source.route(self.command, self.path, self.headers, body)
            except (ValueError, KeyError, IndexError) as error:
                status, headers, payload = (400, {}, str(error).encode())
            if status is None:
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            cut = headers.pop('X-Source-Cut', source.state.get('cut_after'))
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, str(value))
            chunked = headers.get('Transfer-Encoding') == 'chunked'
            if not chunked:
                self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            if chunked:
                for at in range(0, len(payload), 7):
                    chunk = payload[at:at + 7]
                    self.wfile.write(('%x\r\n' % len(chunk)).encode() + chunk + b'\r\n')
                self.wfile.write(b'0\r\nX-Source-End: yes\r\n\r\n')
            else:
                self.wfile.write(payload if cut is None else payload[:int(cut)])
            self.wfile.flush()
            self.close_connection = True
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.source = source
    server.daemon_threads = True
    return server
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='运行本机供应方协议服务')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    with make_server(args.port) as server:
        print('http://127.0.0.1:%d' % server.server_port, flush=True)
        server.serve_forever()
