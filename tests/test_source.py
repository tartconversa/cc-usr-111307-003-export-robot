import json
import threading
import unittest
from urllib.request import urlopen
from src import source

class SupplierSourceTests(unittest.TestCase):
    def setUp(self): self.source = source.Source()
    def route(self, path, headers=None): return self.source.route('GET', path, headers or {}, b'')
    def test_protocol(self):
        session = self.route('/session'); csrf = json.loads(session[2])['csrf']
        headers = {'Cookie': session[1]['Set-Cookie'].split(';')[0], 'X-CSRF-Token': csrf}
        payload = json.dumps({'client_ref': 'x', 'dataset_id': 'a'}).encode()
        self.source.state['lose_submit_response'] = True
        self.assertIsNone(self.source.route('POST', '/exports', headers, payload)[0])
        self.assertEqual(self.source.route('POST', '/exports', headers, payload)[0], 403)
        session = self.route('/session')
        headers = {'Cookie': session[1]['Set-Cookie'].split(';')[0], 'X-CSRF-Token': json.loads(session[2])['csrf']}
        retry = self.source.route('POST', '/exports', headers, payload)
        self.assertEqual(json.loads(retry[2])['job_id'], 'job-1')
        self.assertEqual(len(self.source.state['jobs']), 1)
        session = self.route('/session')
        headers = {'Cookie': session[1]['Set-Cookie'].split(';')[0], 'X-CSRF-Token': json.loads(session[2])['csrf']}
        self.assertEqual(self.source.route('POST', '/exports', headers, payload.replace(b'"a"', b'"b"'))[0], 409)
    def test_http_state_endpoint(self):
        with source.make_server() as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            try:
                with urlopen('http://127.0.0.1:%d/__state' % server.server_port, timeout=5) as response:
                    self.assertEqual(json.load(response)['generation'], 1)
            finally:
                server.shutdown(); thread.join()

if __name__ == '__main__': unittest.main()
