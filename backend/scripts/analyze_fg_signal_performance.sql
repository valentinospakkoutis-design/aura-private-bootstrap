-- ============================================================================
-- F&G signal-performance analysis  (READ-ONLY — no writes, safe on production)
-- ----------------------------------------------------------------------------
-- Purpose: measure crypto prediction performance (win rate, avg PnL) when the
--          market-wide Fear & Greed index was in "extreme fear" (F&G < 25),
--          compared to the baseline (F&G >= 25), BEFORE deciding whether to
--          change the auto_trading_engine F&G<25 skip threshold.
--
-- Sources:
--   prediction_outcomes   -> outcome/PnL   (was_correct_7d, pnl_7d_pct)  [tracked from /predict, regardless of execution]
--   onchain_signal_history-> historical F&G (fear_greed, per day)         [only persistent F&G source]
--
-- F&G is market-wide/daily, so we join prediction_outcomes to the average
-- daily F&G value on the same calendar day.
--
-- Caveats to keep in mind when reading the numbers:
--   * auto_trading_engine SKIPS trades at F&G<25, so EXECUTED trades at F&G<25
--     are ~zero. prediction_outcomes are signal-level (tracked even when the
--     trade was blocked), which is exactly what you want to evaluate here.
--   * F&G history only exists for the period onchain snapshots were running.
--   * Small n at F&G<25 => not statistically meaningful (that itself is an answer).
--
-- Run:  psql "$DATABASE_URL" -f backend/scripts/analyze_fg_signal_performance.sql
-- ============================================================================

-- Reusable crypto filter (matches asset_predictor: USDC/USDT pairs excl. metals, or -USD)
-- Applied inline in each query below.

\echo '=== [0a] Data availability: evaluated crypto predictions & F&G coverage ==='
SELECT
    (SELECT COUNT(*) FROM prediction_outcomes
       WHERE was_correct_7d IS NOT NULL
         AND (UPPER(symbol) LIKE '%USDT' OR UPPER(symbol) LIKE '%USDC' OR UPPER(symbol) LIKE '%-USD')
         AND UPPER(symbol) NOT SIMILAR TO '(XAU|XAG|XPT|XPD)%')                     AS evaluated_crypto_predictions,
    (SELECT MIN(created_at) FROM onchain_signal_history WHERE fear_greed IS NOT NULL) AS fg_history_from,
    (SELECT MAX(created_at) FROM onchain_signal_history WHERE fear_greed IS NOT NULL) AS fg_history_to,
    (SELECT COUNT(DISTINCT date_trunc('day', created_at))
       FROM onchain_signal_history WHERE fear_greed IS NOT NULL)                    AS days_with_fg,
    (SELECT COUNT(DISTINCT date_trunc('day', created_at))
       FROM onchain_signal_history WHERE fear_greed IS NOT NULL AND fear_greed < 25) AS days_with_extreme_fear;

\echo ''
\echo '=== [0b] Symbol inventory — VALIDATE the crypto filter matches your data ==='
SELECT symbol, COUNT(*) AS n_evaluated
FROM prediction_outcomes
WHERE was_correct_7d IS NOT NULL
GROUP BY symbol
ORDER BY n_evaluated DESC;

\echo ''
\echo '=== [1] MAIN: crypto signal performance by F&G bucket (<25 vs >=25) ==='
WITH fg_daily AS (
    SELECT date_trunc('day', created_at) AS d,
           AVG(fear_greed)::numeric      AS fg
    FROM onchain_signal_history
    WHERE fear_greed IS NOT NULL
    GROUP BY 1
),
crypto_outcomes AS (
    SELECT po.*, f.fg
    FROM prediction_outcomes po
    JOIN fg_daily f ON f.d = date_trunc('day', po.created_at)
    WHERE po.was_correct_7d IS NOT NULL
      AND (UPPER(po.symbol) LIKE '%USDT' OR UPPER(po.symbol) LIKE '%USDC' OR UPPER(po.symbol) LIKE '%-USD')
      AND UPPER(po.symbol) NOT SIMILAR TO '(XAU|XAG|XPT|XPD)%'
)
SELECT
    CASE WHEN fg < 25 THEN 'extreme_fear (F&G<25)' ELSE 'baseline (F&G>=25)' END AS bucket,
    COUNT(*)                                                          AS n_signals,
    ROUND(AVG(CASE WHEN was_correct_7d THEN 1 ELSE 0 END) * 100, 1)   AS win_rate_pct,
    ROUND(AVG(pnl_7d_pct)::numeric, 3)                                AS avg_pnl_7d_pct,
    ROUND(AVG(confidence)::numeric, 1)                                AS avg_confidence,
    ROUND(MIN(fg), 0)                                                 AS fg_min,
    ROUND(MAX(fg), 0)                                                 AS fg_max
FROM crypto_outcomes
GROUP BY 1
ORDER BY 1;

\echo ''
\echo '=== [2] Per-symbol breakdown at F&G<25 (where the extreme-fear signals came from) ==='
WITH fg_daily AS (
    SELECT date_trunc('day', created_at) AS d, AVG(fear_greed)::numeric AS fg
    FROM onchain_signal_history WHERE fear_greed IS NOT NULL GROUP BY 1
)
SELECT
    po.symbol,
    COUNT(*)                                                        AS n_signals,
    ROUND(AVG(CASE WHEN po.was_correct_7d THEN 1 ELSE 0 END)*100,1) AS win_rate_pct,
    ROUND(AVG(po.pnl_7d_pct)::numeric, 3)                           AS avg_pnl_7d_pct
FROM prediction_outcomes po
JOIN fg_daily f ON f.d = date_trunc('day', po.created_at)
WHERE po.was_correct_7d IS NOT NULL
  AND f.fg < 25
  AND (UPPER(po.symbol) LIKE '%USDT' OR UPPER(po.symbol) LIKE '%USDC' OR UPPER(po.symbol) LIKE '%-USD')
  AND UPPER(po.symbol) NOT SIMILAR TO '(XAU|XAG|XPT|XPD)%'
GROUP BY po.symbol
ORDER BY n_signals DESC;
