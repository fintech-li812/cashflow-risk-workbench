import hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
import qa_entry
from config import Config
from service import Service

class ConfigEntryTests(unittest.TestCase):
    def base(self):
        return Config('fixture-tenant','fixture-manufacturing',ROOT/'fixtures'/'calculated_result_v1.json',qa_entry.APPROVED_SHA256,
            'cfqa_config',port=13317,user='root',qa=True,allow_fixture=True)
    def test_ports_reject_bool_string_zero_and_overflow(self):
        for value in (True,'3306',0,-1,65536,3.2):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'port_invalid'):
                replace(self.base(),port=value).validate()
    def test_security_flags_require_booleans(self):
        for key in ('qa','allow_fixture','qwen_bound'):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'boolean'):
                replace(self.base(),**{key:'false'}).validate()
    def test_root_cannot_connect_to_business_database(self):
        with self.assertRaisesRegex(ValueError,'root_only'):
            replace(self.base(),database='cf_workbench').validate()
    def test_fixture_cannot_be_enabled_for_nonqa_account(self):
        with self.assertRaisesRegex(ValueError,'fixture_only'):
            replace(self.base(),database='cf_workbench',user='cf_app',qa=False).validate()
    def test_remote_host_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'loopback'):
            replace(self.base(),host='untrusted.invalid').validate()
    def test_launcher_overrides_inherited_production_configuration(self):
        with patch.dict(os.environ,{'CF_DB_NAME':'cf_workbench','CF_DB_USER':'prod',
                'CF_DB_PASSWORD':'test-secret-marker','CF_QWEN_BOUND':'1','CF_RESULT_SHA256':'0'*64}):
            env=qa_entry.environment()
        self.assertTrue(env['CF_DB_NAME'].startswith('cfqa_'))
        self.assertEqual(env['CF_DB_USER'],'root');self.assertNotIn('CF_DB_PASSWORD',env)
        self.assertEqual(env['CF_QWEN_BOUND'],'0');self.assertEqual(env['CF_RESULT_SHA256'],qa_entry.APPROVED_SHA256)
    def test_bound_flag_cannot_claim_native_platform_verification(self):
        loaded=Service(replace(self.base(),qwen_bound=True)).read()
        self.assertFalse(loaded['platform_native_verified']);self.assertTrue(loaded['fixture'])
    def test_tampered_fixture_is_rejected_before_start(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'fixtures').mkdir();(root/'evidence').mkdir()
            (root/'fixtures'/'calculated_result_v1.json').write_text('{}',encoding='utf-8')
            (root/'evidence'/'qa_runtime.json').write_text(json.dumps({'database':'cfqa_test','port':13317}),encoding='utf-8')
            with patch.object(qa_entry,'ROOT',root),self.assertRaisesRegex(ValueError,'approved_fixture_changed'):
                qa_entry.environment()
    def test_launcher_rejects_nonqa_runtime_and_boolean_port(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'evidence').mkdir()
            for runtime in ({'database':'cf_workbench','port':13317},{'database':'cfqa_test','port':True}):
                with self.subTest(runtime=runtime):
                    (root/'evidence'/'qa_runtime.json').write_text(json.dumps(runtime),encoding='utf-8')
                    with patch.object(qa_entry,'ROOT',root),self.assertRaises(ValueError):qa_entry.environment()

if __name__=='__main__':unittest.main(verbosity=2,failfast=True)
