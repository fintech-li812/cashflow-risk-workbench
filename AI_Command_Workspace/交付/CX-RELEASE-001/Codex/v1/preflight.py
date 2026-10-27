"""Read-only release prerequisites. Never turns self-declared evidence into approval."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile

GATES = ('independent_review', 'qwen_read_snapshot', 'qwen_formula_recalc', 'qwen_agent_request',
         'mcp_authorized_call', 'mysql_exact_readback', 'restore_drill', 'real_cashflow_scope', 'final_x_signoff')
ARTIFACTS = ('server_app', 'server_config', 'server_dependencies', 'agent_candidate', 'qa_candidate')
MAX_FILE = 16 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_relative(value):
    if not isinstance(value, str) or not value or '\\' in value or ':' in value or any(ord(c) < 32 for c in value):
        raise ValueError('PATH_UNSAFE')
    if PurePosixPath(value).is_absolute() or any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in value.split('/')):
        raise ValueError('PATH_UNSAFE')
    reserved = {'CON', 'NUL', 'PRN', 'AUX'} | {x+str(i) for x in ('COM', 'LPT') for i in range(1, 10)}
    if any(p.split('.')[0].upper() in reserved for p in value.split('/')):
        raise ValueError('PATH_UNSAFE')
    return value


def locate(roots, root_key, path):
    root = roots[root_key]
    safe_relative(path)
    value = root / path
    node = root
    if root.is_symlink():
        raise ValueError('PATH_LINK')
    for part in path.split('/'):
        node = node / part
        if node.is_symlink():
            raise ValueError('PATH_LINK')
    if not value.resolve().is_relative_to(root.resolve()):
        raise ValueError('PATH_ESCAPE')
    return value


def package_metadata(path):
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        if len(infos) > 2000 or sum(x.file_size for x in infos) > 64 * 1024 * 1024:
            raise ValueError('ZIP_LIMIT')
        names = set()
        for item in infos:
            name = safe_relative(item.filename.rstrip('/'))
            if name.casefold() in names or item.flag_bits & 1 or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('ZIP_UNSAFE')
            names.add(name.casefold())
            if item.file_size > MAX_FILE:
                raise ValueError('ZIP_FILE_LIMIT')
        manifest = json.loads(z.read('manifest.json'))
        if not isinstance(manifest, dict) or not isinstance(manifest.get('files'), list):
            raise ValueError('MANIFEST_INVALID')
        seen = set()
        for item in manifest['files']:
            name = safe_relative(item['path'])
            if name.casefold() in seen or name in ('manifest.json', 'SHA256SUMS.txt'):
                raise ValueError('MANIFEST_DUPLICATE')
            seen.add(name.casefold())
            if sha(z.read(name)) != item.get('sha256'):
                raise ValueError('MANIFEST_HASH')
        if any(x.filename.casefold() not in seen and x.filename not in ('manifest.json', 'SHA256SUMS.txt') for x in infos if not x.is_dir()):
            raise ValueError('MANIFEST_UNLISTED')
        return {'task_id': manifest.get('task_id'), 'package_version': manifest.get('package_version'), 'declared_status': manifest.get('status')}


def run(plan, roots):
    if not isinstance(plan, dict) or plan.get('schema_version') != 'mfg-release-preflight.v1' or plan.get('target') != 'qwen_office':
        raise ValueError('PLAN_SCHEMA')
    checks = plan.get('artifacts')
    gates = plan.get('manual_gates')
    if not isinstance(checks, list) or not isinstance(gates, list):
        raise ValueError('PLAN_SHAPE')
    rows, seen, gate_seen = [], set(), set()
    for item in checks:
        ident = item.get('id')
        if not isinstance(ident, str) or not ident or ident in seen:
            raise ValueError('ARTIFACT_ID')
        seen.add(ident)
        path = locate(roots, item['root'], item['path'])
        row = {'id':ident, 'label':item.get('label', ident), 'status':'通过', 'observation':'', 'scope':'本地文件条件，不能证明可运行'}
        if not path.is_file():
            row.update(status='失败', observation='文件缺失')
        elif path.stat().st_size == 0:
            row.update(status='失败', observation='文件为0字节，不能作为实现完成证据')
        elif path.stat().st_size > MAX_FILE:
            row.update(status='失败', observation='超过本检查器文件上限')
        else:
            row['bytes'] = path.stat().st_size
            if item.get('sha256'):
                observed = sha(path.read_bytes())
                row['sha256'] = observed
                if observed != item['sha256']:
                    row.update(status='失败', observation='文件与固定源摘要不同')
            if item.get('kind') == 'candidate_zip' and row['status'] == '通过':
                row['candidate_metadata'] = package_metadata(path)
                if row['candidate_metadata']['task_id'] != item.get('task_id'):
                    row.update(status='失败', observation='候选任务编号与部署计划不符')
                else:
                    row['observation'] = '候选内容摘要一致；manifest自报状态不是批准'
            elif item.get('kind') not in ('file', 'candidate_zip'):
                row.update(status='失败', observation='未知检查类型，不能默许')
        rows.append(row)
    for required in ARTIFACTS:
        if required not in seen:
            rows.append({'id':required,'label':required,'status':'失败','observation':'发布计划漏掉必要工件','scope':'计划完整性'})
    for gate in gates:
        ident = gate.get('id')
        if not isinstance(ident, str) or not ident or ident in gate_seen:
            raise ValueError('GATE_ID')
        gate_seen.add(ident)
        declared = gate.get('declared_status')
        if declared not in ('通过', '失败', '阻塞', '未执行'):
            raise ValueError('GATE_STATUS')
        # No file contents, filename, or self-declared status can substitute for real independent observation.
        rows.append({'id':ident,'label':gate.get('label',ident),'status':'失败' if declared=='失败' else '阻塞',
                     'declared_status':declared,'observation':gate.get('missing_condition','需要实际独立核验'),
                     'scope':'人工/平台/数据库观察；本工具不能自动批准'})
    for required in GATES:
        if required not in gate_seen:
            rows.append({'id':required,'label':required,'status':'阻塞','observation':'未提供必要实测/签收项，不能用空列表放行','scope':'发布关键条件'})
    totals = {status:sum(x['status']==status for x in rows) for status in ('通过','失败','阻塞','未执行')}
    overall = '失败' if totals['失败'] else ('阻塞' if totals['阻塞'] else '通过')
    return {'schema_version':'mfg-release-preflight-report.v1','status':overall,'release_authorized':False,
            'target':'qwen_office','counts':totals,'checks':rows,
            'notes':['只读本地发布前检查；不联网、不执行候选、不部署。','非空文件不证明程序已实现；独立审批、平台运行、MySQL与恢复演练都需真实证据。']}


def main(argv=None):
    parser=argparse.ArgumentParser(description='只读本地发布前条件检查，不自动授权发布')
    parser.add_argument('--plan',required=True);parser.add_argument('--project-root',required=True);parser.add_argument('--workspace-root',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args(argv)
    try:
        output=Path(args.output)
        if output.exists() or output.is_symlink():raise ValueError('OUTPUT_EXISTS')
        plan_path=Path(args.plan)
        if plan_path.stat().st_size>MAX_FILE:raise ValueError('PLAN_TOO_LARGE')
        roots={'project':Path(args.project_root),'workspace':Path(args.workspace_root)}
        if output.resolve().is_relative_to(roots['project'].resolve()):raise ValueError('OUTPUT_INSIDE_PROJECT')
        plan=json.loads(plan_path.read_text(encoding='utf-8-sig'))
        report=run(plan,roots)
        output.mkdir(parents=True,exist_ok=False)
        (output/'preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        lines=['# 发布前条件检查','',f"状态：{report['status']}；发布许可：未授权。",'', '| 检查 | 状态 | 实际观察/缺项 |','|---|---|---|']
        for row in report['checks']:
            clean=lambda value:str(value).replace('|','\\|').replace('\n',' ')
            lines.append('| '+' | '.join(clean(row[k]) for k in ('label','status','observation'))+' |')
        lines+=['','本报告不能替代独立审核或千问端到端实测。']
        (output/'发布前阻断清单.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
        print(json.dumps({'status':report['status'],'release_authorized':False,'counts':report['counts']},ensure_ascii=True))
        return 1 if report['status']=='失败' else 2
    except (OSError,ValueError,KeyError,TypeError,AttributeError,zipfile.BadZipFile) as exc:
        print(json.dumps({'status':'失败','release_authorized':False,'error_type':type(exc).__name__,'reason':'输入无效、路径不安全或内容摘要不一致；未部署'},ensure_ascii=True))
        return 1


if __name__=='__main__':
    sys.exit(main())
