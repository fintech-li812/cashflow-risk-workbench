# 制造业现金流基础版：可审联调候选

用户2026-10-24要求先跑旧版普通链路，核心滚动算法和三态自动判定后置。本包在新目录完成，不覆盖主项目、原交付、样例或三个空占位文件。状态是待独审候选，尚未部署正式业务、尚未接入千问。

## 已实际跑通
规范合成输入→基础现金流算术→规则解释→官方MCP stdio→真实云端MySQL隔离库提交→精确回查→浏览器显示真实回执。进程重启读回相同record_id，另外独立SQL核对。基础算术11方法、真实MySQL17方法、Web输入守卫10方法均通过；两次成功MCP联测分别采用原合成结果和新基础计算结果。一次后处理NameError失败日志保留，修正并间隔30秒后复测。

浏览器地址（仅当前本机临时QA服务运行期间）：http://127.0.0.1:18765/ 。它明确显示合成联调，并连接隔离测试库；不是千问内最终应用。没有安装启动项、定时任务或开放公网端口。

## 从副本复现
先核manifest/SHA，再复制本包到新的测试目录。不要在冻结原包跑会写evidence的测试；重跑记录另存。
使用Python 3.12及requirements.lock.txt的锁定环境。只把依赖装入自己的独立venv，不复制本机venv或Windows二进制环境。锁文件含开发实测Windows包；跨Linux部署需单独审查环境锁，不把Windows pywin32搬进服务器。

纯本地测试（没有服务器权限也可跑）：

    python -B tests/test_arithmetic.py
    python -B tests/test_web_guard.py

基础算术（只允许显式合成）：

    python -B src/arithmetic.py --input fixtures/normalized_input.json --output 新的合成结果.json --allow-fixture

正式数据不走此fixture CLI；通用Excel导入与实际千问公式待队友与平台接入，不能伪装qwen_sheet。

## MySQL与MCP复现前置
需要自己已授权的MySQL 8隔离库cfqa_*及表sql/isolated_schema.sql；应用不会自动建库表，不得对正式库执行测试故障注入。用自己的独立测试环境改副本evidence/qa_runtime.json中的database和port，保留源包文件不变。tests/test_service.py当前使用root仅因QA socket认证，配置强制限制cfqa_*；生产必须使用最小权限应用账号，未验证生产账号权限。
测试代码会追加合成记录，并在一条专用测试记录上故意破坏摘要，供检出验证；不自动清理或删除。它不是可直接指向生产的通用测试脚本。

    python -B tests/test_service.py
    python -B tests/mcp_e2e.py

MCP服务入口src/app.py，stdio标准输入输出，日志到stderr。服务所需非秘密配置名：CF_TENANT_ID、CF_COMPANY_ID、CF_RESULT_FILE、CF_RESULT_SHA256、CF_DB_NAME、CF_DB_HOST、CF_DB_PORT、CF_DB_USER、CF_QA_MODE、CF_ALLOW_FIXTURE、CF_QWEN_BOUND。密码只从环境变量CF_DB_PASSWORD读取，不写文件、不打印Config。当前单一可信启动身份，不是多用户认证。

env中CF_RESULT_FILE必须是可信、固定摘要的批准结果快照；它只是文件级完整性，不证明千问来源真实性。真实Qwen输出未经现场取证不得打开CF_QWEN_BOUND。

## 仍需完成
DeepSeek独立审核及整改；正式业务表/应用账号验证/部署；千问账号恢复后的原生读表、公式重算、MCP工具绑定和实际Agent问答；真实企业输入及余额凭证；生产恢复与运维验收。现有四个外包包仍排队，不把本包最小fixture算术代替完整计算/导入/可靠存储任务验收。

第二阶段方案库：D:/AI_Command_Workspace/迭代方案库/第二阶段_核心算法迭代/README.md。

## 本机临时预览入口
在本包根目录，用装好锁定依赖的Python运行`python -B launch_preview.py`。须已有本机授权QA隧道与qa_runtime.json中的隔离数据库；脚本不获取私钥、不建库、不安装依赖。运行日志在上一级Codex/_runtime，不回写冻结源码。预览需18765端口空闲，本机当前已有会话无需再启动第二个。
