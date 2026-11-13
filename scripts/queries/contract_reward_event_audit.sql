DECLARE start_date DATE DEFAULT DATE '2026-11-01';
DECLARE end_date DATE DEFAULT CURRENT_DATE();

-- Read 7 days before start_date to retrieve previous balances.
DECLARE seed_lookback_days INT64 DEFAULT 7;

WITH account_changes_window AS (
    SELECT
        block_date,
        block_height,
        index_in_block,
        affected_account_id,
        update_reason,
        affected_account_nonstaked_balance AS balance_after,
        COUNT(*) OVER (
            PARTITION BY affected_account_id, block_height, index_in_block
        ) AS position_count
    FROM `bigquery-public-data.crypto_near_mainnet_us.account_changes`
    WHERE block_date BETWEEN
        DATE_SUB(start_date, INTERVAL seed_lookback_days DAY)
        AND end_date
),
ordered_changes AS (
    SELECT
        block_date,
        block_height,
        affected_account_id,
        update_reason,
        balance_after,
        position_count,
        LAG(balance_after) OVER account_sequence AS balance_before,
        LAG(position_count) OVER account_sequence AS previous_position_count
    FROM account_changes_window
    WINDOW account_sequence AS (
        PARTITION BY affected_account_id
        ORDER BY block_height, index_in_block
    )
),
classified_rewards AS (
    SELECT
        block_date,
        CASE
            WHEN balance_before IS NULL OR balance_after IS NULL
                THEN 'missing_previous_balance'
            WHEN position_count != 1 OR previous_position_count != 1
                THEN 'ambiguous_order'
            WHEN balance_after - balance_before <= 0
                THEN 'non_positive_delta'
            ELSE 'valid'
        END AS calculation_status,
        balance_after - balance_before AS reward_delta_yocto
    FROM ordered_changes
    WHERE update_reason = 'action_receipt_gas_reward'
      AND block_date BETWEEN start_date AND end_date
),
daily_audit AS (
    SELECT
        block_date AS utc_date,
        COUNT(*) AS total_reward_events,
        COUNTIF(calculation_status = 'valid') AS valid_reward_events,
        COUNTIF(calculation_status = 'missing_previous_balance') AS missing_previous_balance,
        COUNTIF(calculation_status = 'ambiguous_order') AS ambiguous_order,
        COUNTIF(calculation_status = 'non_positive_delta') AS non_positive_delta,
        SAFE_DIVIDE(COUNTIF(calculation_status = 'valid'), COUNT(*)) * 100
            AS event_count_coverage_pct,
        SUM(IF(calculation_status = 'valid', reward_delta_yocto, 0)) / 1e24
            AS contract_rewards_near
    FROM classified_rewards
    GROUP BY utc_date
),
calendar AS (
    SELECT utc_date
    FROM UNNEST(GENERATE_DATE_ARRAY(start_date, end_date)) AS utc_date
)
SELECT
    calendar.utc_date,
    COALESCE(daily_audit.total_reward_events, 0) AS total_reward_events,
    COALESCE(daily_audit.valid_reward_events, 0) AS valid_reward_events,
    COALESCE(daily_audit.missing_previous_balance, 0) AS missing_previous_balance,
    COALESCE(daily_audit.ambiguous_order, 0) AS ambiguous_order,
    COALESCE(daily_audit.non_positive_delta, 0) AS non_positive_delta,
    COALESCE(daily_audit.event_count_coverage_pct, 100) AS event_count_coverage_pct,
    COALESCE(daily_audit.contract_rewards_near, 0) AS contract_rewards_near
FROM calendar
LEFT JOIN daily_audit USING (utc_date)
ORDER BY calendar.utc_date;
