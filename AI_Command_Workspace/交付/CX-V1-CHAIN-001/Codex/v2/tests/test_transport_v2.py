import hashlib,json,os,sys,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch,MagicMock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from starlette.testclient import TestClient
import web_server
from mcp.types import LATEST_PROTOCOL_VERSION

FP='a'*64
def environment():
    source=ROOT/'fixtures'/'calculated_result_v1.json'
    return {'CF_TENANT_ID':'fixture-tenant','CF_COMPANY_ID':'fixture-manufacturing',
        'CF_RESULT_FILE':str(source),'CF_RESULT_SHA256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'CF_DB_NAME':'cfqa_transport_fixture','CF_DB_USER':'root','CF_DB_HOST':'127.0.0.1',
        'CF_QA_MODE':'1','CF_ALLOW_FIXTURE':'1','CF_DB_PORT':'19999'}

class WebTests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(web_server.create_app(),base_url='http://127.0.0.1:18765')
        self.headers={'Origin':'http://127.0.0.1:18765','Content-Type':'application/json'}
        self.body={'request_id':'fixture-request','workflow_fingerprint':FP}
    def post(self,**kwargs):return self.client.post('/api/run',json=self.body,headers=self.headers,**kwargs)
    def test_fixture_notice(self):self.assertIn('合成数据工程联调',self.client.get('/').text)
    def test_wrong_origin(self):
        self.headers['Origin']='https://other.invalid';self.assertEqual(self.post().status_code,403)
    def test_wrong_host(self):
        self.headers['Host']='other.invalid';self.assertEqual(self.post().status_code,403)
    def test_no_origin(self):
        del self.headers['Origin'];self.assertEqual(self.post().status_code,403)
    def test_bad_json(self):
        self.assertEqual(self.client.post('/api/run',content='{',headers=self.headers).status_code,400)
    def test_duplicate_json_key(self):
        body='{"request_id":"old","request_id":"new","workflow_fingerprint":"'+FP+'"}'
        self.assertEqual(self.client.post('/api/run',content=body,headers=self.headers).status_code,400)
    def test_extra_identity(self):
        self.body['tenant_id']='other';self.assertEqual(self.post().status_code,400)
    def test_empty_id(self):self.body['request_id']=' ';self.assertEqual(self.post().status_code,400)
    def test_missing_fingerprint(self):del self.body['workflow_fingerprint'];self.assertEqual(self.post().status_code,400)
    def test_invalid_fingerprint(self):self.body['workflow_fingerprint']='untrusted';self.assertEqual(self.post().status_code,400)
    def test_nonjson_media_type(self):self.headers['Content-Type']='application/jsonp';self.assertEqual(self.post().status_code,415)
    def test_stream_body_size_limit(self):
        self.assertEqual(self.client.post('/api/run',content='x'*5000,headers=self.headers).status_code,413)
    def test_unknown_route(self):self.assertEqual(self.client.post('/api/no',json=self.body,headers=self.headers).status_code,404)
    def test_run_uncertainty_is_pending(self):
        with patch('web_server.invoke',new=AsyncMock(side_effect=RuntimeError('private-message'))):
            r=self.post();self.assertEqual(r.status_code,503);self.assertEqual(r.json()['status'],'pending')
            self.assertNotIn('private-message',r.text)
    def test_query_failure_not_notfound(self):
        with patch('web_server.invoke',new=AsyncMock(side_effect=RuntimeError('private-message'))):
            r=self.client.post('/api/query',json=self.body,headers=self.headers)
            self.assertEqual(r.json()['status'],'unavailable');self.assertNotEqual(r.json()['status'],'not_found')
    def test_api_passes_fingerprint_without_guess(self):
        fake=AsyncMock(return_value={'status':'conflict'})
        with patch('web_server.invoke',new=fake):
            self.assertEqual(self.post().json()['status'],'conflict')
        fake.assert_awaited_once_with('run','fixture-request',FP)
    def test_health_failure_not_ready(self):
        with patch('web_server.qa_service',side_effect=RuntimeError('hidden-config')):
            r=self.client.get('/api/health');self.assertEqual(r.status_code,503)
            self.assertEqual(r.json()['database'],'尚未确认连接');self.assertNotIn('hidden-config',r.text)
    def test_source_fingerprint_changes_with_file_hash(self):
        with patch.dict(os.environ,environment(),clear=False):
            a=self.client.get('/api/source');self.assertEqual(a.status_code,200)
            original=a.json();self.assertEqual(len(original['workflow_fingerprint']),64)
            loaded=web_server.qa_service().read();loaded['source_file_sha256']='b'*64
            self.assertNotEqual(original['workflow_fingerprint'],web_server.source_metadata(loaded)['workflow_fingerprint'])

class MCPHTTPTests(unittest.TestCase):
    def call(self,*,headers=None,body=None):
        with patch.dict(os.environ,environment(),clear=False):
            with TestClient(web_server.create_app(),base_url='http://127.0.0.1:18765') as client:
                default={'Accept':'application/json, text/event-stream','MCP-Protocol-Version':LATEST_PROTOCOL_VERSION}
                default.update(headers or {})
                return client.post('/mcp/',json=body or {'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}},headers=default)
    def test_actual_tools_list(self):
        r=self.call();self.assertEqual(r.status_code,200,r.text)
        self.assertEqual({t['name'] for t in r.json()['result']['tools']},
            {'read_cashflow_result','save_cashflow_result','query_cashflow_result'})
    def test_wrong_host_rejected(self):
        self.assertEqual(self.call(headers={'Host':'other.invalid'}).status_code,421)
    def test_wrong_origin_rejected(self):
        self.assertEqual(self.call(headers={'Origin':'https://other.invalid'}).status_code,403)
    def test_read_tool_is_explicit_fixture(self):
        r=self.call(body={'jsonrpc':'2.0','id':2,'method':'tools/call',
            'params':{'name':'read_cashflow_result','arguments':{}}})
        self.assertEqual(r.status_code,200,r.text)
        answer=r.json()['result'];self.assertFalse(answer.get('isError',False),r.text)
        value=answer.get('structuredContent')
        if value is None:value=json.loads(answer['content'][0]['text'])
        self.assertTrue(value['fixture']);self.assertFalse(value['platform_native_verified'])
    def test_unknown_tool_no_success(self):
        r=self.call(body={'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'arbitrary_sql','arguments':{}}})
        self.assertTrue(r.json()['result']['isError'])

if __name__=='__main__':unittest.main(verbosity=2,failfast=True)
