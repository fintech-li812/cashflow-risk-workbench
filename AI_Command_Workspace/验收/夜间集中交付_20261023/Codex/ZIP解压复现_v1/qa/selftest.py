"""Run independent offline tests in caller's fresh workspace; no business files touched."""
import io
import json
from pathlib import Path
import unittest
import qa_tool as q


def run(workdir):
    root = Path(workdir)
    if root.exists() or root.is_symlink():
        raise q.InputError('SELFTEST_WORKDIR_EXISTS')
    root.mkdir(parents=True)
    import test_qa_tool as tests
    tests.TEST_ROOT = str(root)
    suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    tests.TEST_ROOT = None
    (root / 'unittest-output.txt').write_text(stream.getvalue(), encoding='utf-8')
    summary = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
                   nature='offline_synthetic_and_source_package_fixtures', platform_tests=0, database_tests=0,
                   note='通过用例包括预期拒绝的负例；不是被测系统全部通过。')
    (root / 'selftest-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    report = q.Report('selftest')
    report.check(result.wasSuccessful() and result.testsRun > 0, 'SELFTEST_FAILED', 'unittest-output.txt', '独立测试全通过且非空', '修复失败并交新版本')
    report.notes.append(f'独立测试{result.testsRun}项；失败{len(result.failures)}，错误{len(result.errors)}，跳过{len(result.skipped)}。')
    return report
