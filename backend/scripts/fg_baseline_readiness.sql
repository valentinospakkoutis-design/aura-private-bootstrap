-- ============================================================================
-- F&G baseline readiness + CLEAN re-run  (READ-ONLY — safe on production)
-- ----------------------------------------------------------------------------
-- Context: the F&G<25 vs baseline comparison is currently IMPOSSIBLE because
-- every matured (7d) live-era prediction day so far was extreme fear (F&G<25).
-- We need matured predictions on baseline days (F&G>=25) before re-running the
-- clean analysis. A prediction "matures" 7 days after created_at.
--
-- HOW TO KNOW IT'S READY:
--   Run [R] below. When `baseline_days_ready` is comfortably populated
--   (rule of thumb: >= ~10-15 distinct days AND baseline_signals_ready well
--   over ~30 after dedup), the comparison in [C] becomes meaningful.
--   While baseline_days_ready = 0, do NOT draw any conclusion.
--
-- Cleaning rules (same as the clean re-run agreed on 2026-07-01):
--   * live era only: created_at >= 2026-06-18 (after the stale/backfill block)
--   * dedup: one signal per (symbol, prediction_day) — earliest of the day
--   * BUY/SELL only (HOLD has the was_correct_7d labeling bug)
--
-- Run:  docker exec -i aura-postgres psql -U aura_user -d aura -f backend/scripts/fg_baseline_readiness.sql
--   or: psql "$DATABASE_URL" -f backend/scripts/fg_baseline_readiness.sql
-- ============================================================================

\echo '=== [R] READINESS: matured (7d) live-era BUY/SELL signals by F&G bucket ==='
WITH fg_daily AS (
    SELECT date_trunc('day', created_at) AS d, AVG(fear_greed)::numeric AS fg
    FROM onchain_signal_history WHERE fear_greed IS NOT NULL GROUP BY 1
)
SELECT
  COUNT(DISTINCT date_trunc('day', po.created_at)) FILTER (WHERE f.fg >= 25) AS baseline_days_ready,
  COUNT(*)                                         FILTER (WHERE f.fg >= 25) AS baseline_signals_ready,
  COUNT(DISTINCT date_trunc('day', po.created_at)) FILTER (WHERE f.fg <  25) AS extremefear_days_ready,
  COUNT(*)                                         FILTER (WHERE f.fg <  25) AS extremefear_signals_ready,
  MAX(date_trunc('day', po.created_at))::date                               AS latest_matured_pred_day
FROM prediction_outcomes po
JOIN fg_daily f ON f.d = date_trunc('day', po.created_at)
WHERE po.was_correct_7d IS NOT NULL
  AND po.created_at >= '2026-06-18'
  AND po.action IN ('BUY','SELL');

\echo ''
\echo '=== [C] CLEAN analysis: live-era, dedup (symbol,day), BUY/SELL only, F&G<25 vs baseline ==='
WITH fg_daily AS (
    SELECT date_trunc('day', created_at) AS d, AVG(fear_greed)::numeric AS fg
    FROM onchain_signal_history WHERE fear_greed IS NOT NULL GROUP BY 1
),
dedup AS (
    SELECT DISTINCT ON (po.symbol, date_trunc('day', po.created_at))
           po.symbol,
           date_trunc('day', po.created_at) AS pday,
           po.action, po.was_correct_7d, po.pnl_7d_pct
    FROM prediction_outcomes po
    WHERE po.was_correct_7d IS NOT NULL
      AND po.created_at >= '2026-06-18'
      AND po.action IN ('BUY','SELL')
      AND (UPPER(po.symbol) LIKE '%USDT' OR UPPER(po.symbol) LIKE '%USDC' OR UPPER(po.symbol) LIKE '%-USD')
      AND UPPER(po.symbol) NOT SIMILAR TO '(XAU|XAG|XPT|XPD)%'
    ORDER BY po.symbol, date_trunc('day', po.created_at), po.created_at
),
joined AS (SELECT d.*, f.fg FROM dedup d JOIN fg_daily f ON f.d = d.pday)
SELECT
    CASE WHEN fg < 25 THEN 'extreme_fear (F&G<25)' ELSE 'baseline (F&G>=25)' END AS bucket,
    COUNT(*)                                                      AS n_signals,
    COUNT(DISTINCT symbol)                                        AS n_symbols,
    COUNT(DISTINCT pday)                                          AS n_days,
    ROUND(AVG(CASE WHEN was_correct_7d THEN 1 ELSE 0 END)*100, 1) AS win_rate_pct,
    ROUND(AVG(pnl_7d_pct)::numeric, 3)                            AS avg_pnl_7d_pct
FROM joined
GROUP BY 1 ORDER BY 1;
