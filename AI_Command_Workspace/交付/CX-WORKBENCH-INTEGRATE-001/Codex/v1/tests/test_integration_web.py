from pathlib import Path
import sys,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from starlette.testclient import TestClient
from web_server import create_app

class IntegrationWebTests(unittest.TestCase):
    def setUp(self):self.client=TestClient(create_app(),base_url='http://127.0.0.1:18765')
    def test_actual_source_endpoint_is_readonly_and_blocked_for_full_result(self):
        response=self.client.get('/api/source-inspection');self.assertEqual(response.status_code,200)
        data=response.json();self.assertEqual(data['inspection']['blocks']['现金流水']['cells']['D8']['value'],'1631300')
        self.assertFalse(data['inspection']['source_modified']);self.assertEqual(data['readiness']['status'],'blocked')
        self.assertNotIn('amounts',data['readiness'])
    def test_source_endpoint_rejects_unexpected_host(self):
        self.assertEqual(self.client.get('/api/source-inspection',headers={'Host':'other.invalid'}).status_code,403)
    def test_status_endpoint_rejects_unexpected_host(self):
        self.assertEqual(self.client.get('/api/workbench',headers={'Host':'other.invalid'}).status_code,403)
    def test_source_failure_does_not_leak_paths_or_claim_ready(self):
        with patch('web_server.inspect_source',side_effect=ValueError('private-path')):
            r=self.client.get('/api/source-inspection');self.assertEqual(r.status_code,503)
            self.assertEqual(r.json()['status'],'blocked');self.assertNotIn('private-path',r.text)
    def test_status_failure_is_not_connected(self):
        with patch('web_server.project_status',side_effect=RuntimeError('private-dsn')):
            r=self.client.get('/api/workbench');self.assertEqual(r.status_code,503)
            self.assertEqual(r.json()['status'],'unavailable');self.assertNotIn('private-dsn',r.text)
    def test_only_fixed_readonly_routes_exposed(self):
        self.assertEqual(self.client.post('/api/source-inspection',json={'source_id':'secret'}).status_code,405)
        self.assertEqual(self.client.get('/api/workbench/secret').status_code,404)

if __name__=='__main__':unittest.main(verbosity=2,failfast=True)
