-- Candidate minimal table. Explicitly choose an isolated cfqa_* DB first; not production approval.
CREATE TABLE mfg_cashflow_runs_v1 (
 record_id CHAR(36) CHARACTER SET ascii COLLATE ascii_bin PRIMARY KEY,
 tenant_id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL,
 company_id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL,
 operation VARCHAR(32) CHARACTER SET ascii NOT NULL,
 request_id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL,
 period CHAR(7) CHARACTER SET ascii NOT NULL,
 source_revision VARCHAR(128) COLLATE utf8mb4_bin NOT NULL,
 run_id VARCHAR(128) COLLATE utf8mb4_bin NOT NULL,
 payload_sha256 CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
 payload JSON NOT NULL,
 stored_at DATETIME(6) NOT NULL,
 UNIQUE KEY uq_request (tenant_id,company_id,operation,request_id),
 CHECK (payload_sha256 REGEXP '^[0-9a-f]{64}$')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;
