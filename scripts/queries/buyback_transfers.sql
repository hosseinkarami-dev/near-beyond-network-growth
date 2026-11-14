
DECLARE start_date DATE DEFAULT DATE('{{start_date}}');
DECLARE end_date DATE DEFAULT DATE('{{end_date}}');

DECLARE target_wallet STRING DEFAULT 'buybacks.multisignature.near';

WITH transfer_sources AS (
    SELECT *
    FROM UNNEST([
        STRUCT('intents.near' AS sender, 'intents_transfer' AS transfer_type),
        STRUCT('fefundsadmin.sputnik-dao.near' AS sender, 'frontend_revenue' AS transfer_type),
        STRUCT('1csfundsadmin.sputnik-dao.near' AS sender, 'oneclick_and_other_revenue' AS transfer_type)
    ])
),

native_transfers AS (
    SELECT
        eo.block_date AS utc_date,
        ra.receipt_id,
        ra.receipt_predecessor_account_id AS sender,
        SAFE_CAST(JSON_VALUE(ra.args, '$.deposit') AS BIGNUMERIC)
            / BIGNUMERIC '1000000000000000000000000' AS amount_near
    FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions` AS ra
    INNER JOIN `bigquery-public-data.crypto_near_mainnet_us.execution_outcomes` AS eo
        ON ra.receipt_id = eo.receipt_id
    WHERE ra.block_date >= DATE_SUB(start_date, INTERVAL 7 DAY)
      AND ra.block_date < end_date
      AND eo.block_date >= start_date
      AND eo.block_date < end_date
      AND ra.action_kind = 'TRANSFER'
      AND ra.receipt_receiver_account_id = target_wallet
      AND ra.receipt_predecessor_account_id IN (
          SELECT sender FROM transfer_sources
      )
      AND eo.status = 'SUCCESS_VALUE'
      AND SAFE_CAST(JSON_VALUE(ra.args, '$.deposit') AS BIGNUMERIC) > 0
),

wrapped_logs AS (
    SELECT
        eo.block_date AS utc_date,
        eo.receipt_id,
        log_offset,
        REGEXP_REPLACE(log.element, r'^EVENT_JSON:', '') AS event_json
    FROM `bigquery-public-data.crypto_near_mainnet_us.execution_outcomes` AS eo
    CROSS JOIN UNNEST(eo.logs.list) AS log WITH OFFSET AS log_offset
    WHERE eo.block_date >= start_date
      AND eo.block_date < end_date
      AND eo.executor_account_id = 'wrap.near'
      AND eo.status = 'SUCCESS_VALUE'
      AND STARTS_WITH(log.element, 'EVENT_JSON:')
),

wrapped_transfers AS (
    SELECT
        wl.utc_date,
        wl.receipt_id,
        wl.log_offset,
        transfer_offset,
        JSON_VALUE(transfer_data, '$.old_owner_id') AS sender,
        SAFE_CAST(JSON_VALUE(transfer_data, '$.amount') AS BIGNUMERIC)
            / BIGNUMERIC '1000000000000000000000000' AS amount_near
    FROM wrapped_logs AS wl
    CROSS JOIN UNNEST(JSON_QUERY_ARRAY(wl.event_json, '$.data')) AS transfer_data
        WITH OFFSET AS transfer_offset
    WHERE JSON_VALUE(wl.event_json, '$.standard') = 'nep141'
      AND JSON_VALUE(wl.event_json, '$.event') = 'ft_transfer'
      AND JSON_VALUE(transfer_data, '$.new_owner_id') = target_wallet
      AND JSON_VALUE(transfer_data, '$.old_owner_id') IN (
          SELECT sender FROM transfer_sources
      )
      AND SAFE_CAST(JSON_VALUE(transfer_data, '$.amount') AS BIGNUMERIC) > 0
),

all_transfers AS (
    SELECT
        utc_date,
        sender,
        'native' AS asset,
        amount_near
    FROM native_transfers

    UNION ALL

    SELECT
        utc_date,
        sender,
        'wrapped' AS asset,
        amount_near
    FROM wrapped_transfers
),

daily_sender_totals AS (
    SELECT
        utc_date,
        sender,

        transfer_sources.transfer_type,

        SUM(IF(asset = 'native', amount_near, BIGNUMERIC '0'))
            AS native_inflow_near,

        SUM(IF(asset = 'wrapped', amount_near, BIGNUMERIC '0'))
            AS wrapped_inflow_near,

        COUNTIF(asset = 'native') AS native_transfer_count,
        COUNTIF(asset = 'wrapped') AS wrapped_transfer_count,
        COUNT(*) AS total_transfer_count

    FROM all_transfers
    INNER JOIN transfer_sources USING (sender)
    GROUP BY utc_date, sender, transfer_type
)

SELECT
    utc_date,
    sender,
    transfer_type,
    native_inflow_near,
    wrapped_inflow_near,
    native_inflow_near + wrapped_inflow_near AS total_inflow_near,
    native_transfer_count,
    wrapped_transfer_count,
    total_transfer_count
FROM daily_sender_totals
ORDER BY utc_date, transfer_type;
