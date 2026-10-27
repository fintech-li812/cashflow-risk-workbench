-- Candidate only; tie rule and effective-date semantics require review.
CREATE OR REPLACE VIEW v_template_latest_proposed AS
SELECT tenant_id, industry_key, template_version, params, provenance, effective_from, published_at
FROM (
 SELECT p.tenant_id,p.industry_key,p.template_version,p.params,p.provenance,p.effective_from,p.published_at,
 ROW_NUMBER() OVER (PARTITION BY p.tenant_id,p.industry_key ORDER BY p.effective_from DESC,p.id DESC) AS choice_order
 FROM param_template p
 WHERE p.publication_status='published' AND p.effective_from<=UTC_TIMESTAMP(6)
 AND NOT EXISTS (
  SELECT 1 FROM param_template s
  WHERE s.tenant_id=p.tenant_id AND s.industry_key=p.industry_key AND s.supersedes_id=p.id
  AND s.publication_status='published' AND s.effective_from<=UTC_TIMESTAMP(6)
 )
) ranked WHERE choice_order=1;
