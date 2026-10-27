from pathlib import Path
import sys,unittest
from unittest.mock import AsyncMock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from starlette.testclient import TestClient
from web_server import app

class WebGuardTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app,base_url='http://127.0.0.1:18765')
        self.headers={'Origin':'http://127.0.0.1:18765','Content-Type':'application/json'}
    def test_home_discloses_fixture(self):
        response=self.client.get('/');self.assertEqual(response.status_code,200)
        self.assertIn('合成数据工程联调',response.text)
    def test_wrong_origin(self):
        response=self.client.post('/api/run',json={'request_id':'x'},headers={'Origin':'https://other.invalid'})
        self.assertEqual(response.status_code,403)
    def test_wrong_host(self):
        response=self.client.post('/api/run',json={'request_id':'x'},headers={**self.headers,'Host':'other.invalid'})
        self.assertEqual(response.status_code,403)
    def test_no_origin(self):self.assertEqual(self.client.post('/api/run',json={'request_id':'x'}).status_code,403)
    def test_bad_json(self):self.assertEqual(self.client.post('/api/run',content='{',headers=self.headers).status_code,400)
    def test_extra_fields(self):self.assertEqual(self.client.post('/api/run',json={'request_id':'x','tenant_id':'other'},headers=self.headers).status_code,400)
    def test_empty_request(self):self.assertEqual(self.client.post('/api/run',json={'request_id':' '},headers=self.headers).status_code,400)
    def test_text_is_not_json(self):self.assertEqual(self.client.post('/api/run',content='{}',headers={'Origin':'http://127.0.0.1:18765','Content-Type':'text/plain'}).status_code,415)
    def test_unknown_route(self):self.assertEqual(self.client.post('/api/unknown',json={'request_id':'x'},headers=self.headers).status_code,404)
    def test_run_failure_is_pending_not_claimed_failed(self):
        with patch('web_server.invoke',new=AsyncMock(side_effect=RuntimeError('do-not-leak-secret'))):
            response=self.client.post('/api/run',json={'request_id':'x','workflow_fingerprint':'a'*64},headers=self.headers)
            self.assertEqual(response.status_code,503);self.assertNotIn('do-not-leak-secret',response.text)
            self.assertEqual(response.json()['status'],'pending')

if __name__=='__main__':unittest.main(verbosity=2,failfast=True)
