-- =============================================================================
-- 最小权限变更【候选】（WB-ENG-001 产出，未批准，未执行）
-- 文件：sql/grants_admin_view_候选.sql
-- 状态：候选，待 Codex 批准后方可在部署任务中执行。init_v1.1.sql 不执行本文件。
--
-- 依据与推导：
--   init_v1.1.sql 含 10 个 CREATE OR REPLACE VIEW。
--   MySQL 8.0 执行 CREATE VIEW 需要 CREATE VIEW 权限；执行 SHOW CREATE VIEW /
--   查询 information_schema.views 完整定义需要 SHOW VIEW 权限。
--   cf_admin@localhost 当前已授（WB-SRV-001 实测 SHOW GRANTS）：
--     SELECT, INSERT, UPDATE, CREATE, ALTER, DROP, INDEX, REFERENCES ON cf_workbench.*
--   → 缺 CREATE VIEW、SHOW VIEW 两项；缺它们则 init_v1.1.sql 的视图段全部失败。
--
-- 最小变更原则：只补视图所需两项，不扩 CREATE ROUTINE / TRIGGER / SUPER 等任何
-- 其他权限；不动 cf_app / cf_backup / cf_read 既有授权；不创建新账号、不生成口令。
-- =============================================================================

-- 候选语句（执行前请再次核对目标账号与库名）：
GRANT CREATE VIEW, SHOW VIEW ON cf_workbench.* TO 'cf_admin'@'localhost';
FLUSH PRIVILEGES;

-- 验证（执行后）：
--   SHOW GRANTS FOR 'cf_admin'@'localhost';
--   -- 期望在既有权限列表中新增 CREATE VIEW, SHOW VIEW

-- 回滚（如需撤销）：
--   REVOKE CREATE VIEW, SHOW VIEW ON cf_workbench.* FROM 'cf_admin'@'localhost';
--   FLUSH PRIVILEGES;
