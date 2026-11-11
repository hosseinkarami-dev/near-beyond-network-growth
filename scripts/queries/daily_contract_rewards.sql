WITH reward_accounts AS (
    SELECT DISTINCT
        affected_account_id
    FROM
        `bigquery-public-data.crypto_near_mainnet_us.account_changes`
    WHERE
        block_date >= DATE('{{start_date}}')
        AND block_date < DATE('{{end_date}}')
        AND update_reason = 'action_receipt_gas_reward'
),

seed_changes AS (
    SELECT
        ac.block_date,
        ac.block_height,
        ac.index_in_block,
        ac.affected_account_id,
        ac.update_reason,
        ac.affected_account_nonstaked_balance AS balance_after,

        COUNT(*) OVER (
            PARTITION BY
                ac.affected_account_id,
                ac.block_height,
                ac.index_in_block
        ) AS position_count,

        RANK() OVER (
            PARTITION BY ac.affected_account_id
            ORDER BY
                ac.block_height DESC,
                ac.index_in_block DESC
        ) AS latest_position_rank

    FROM
        `bigquery-public-data.crypto_near_mainnet_us.account_changes` ac

    INNER JOIN reward_accounts ra
        ON ac.affected_account_id = ra.affected_account_id

    WHERE
        ac.block_date < DATE('{{start_date}}')

    QUALIFY
        latest_position_rank = 1
),

range_changes AS (
    -- تمام تغییرات موجودی حساب‌های هدف در بازه جدید
    SELECT
        ac.block_date,
        ac.block_height,
        ac.index_in_block,
        ac.affected_account_id,
        ac.update_reason,
        ac.affected_account_nonstaked_balance AS balance_after,

        COUNT(*) OVER (
            PARTITION BY
                ac.affected_account_id,
                ac.block_height,
                ac.index_in_block
        ) AS position_count

    FROM
        `bigquery-public-data.crypto_near_mainnet_us.account_changes` ac

    INNER JOIN reward_accounts ra
        ON ac.affected_account_id = ra.affected_account_id

    WHERE
        ac.block_date >= DATE('{{start_date}}')
        AND ac.block_date < DATE('{{end_date}}')
),

all_changes AS (
    SELECT
        block_date,
        block_height,
        index_in_block,
        affected_account_id,
        update_reason,
        balance_after,
        position_count
    FROM seed_changes

    UNION ALL

    SELECT
        block_date,
        block_height,
        index_in_block,
        affected_account_id,
        update_reason,
        balance_after,
        position_count
    FROM range_changes
),

ordered_changes AS (
    SELECT
        block_date,
        affected_account_id,
        update_reason,
        balance_after,
        position_count,

        LAG(balance_after) OVER account_sequence
            AS balance_before,

        LAG(position_count) OVER account_sequence
            AS previous_position_count

    FROM all_changes

    WINDOW account_sequence AS (
        PARTITION BY affected_account_id
        ORDER BY block_height, index_in_block
    )
)

SELECT
    block_date AS utc_date,

    SUM(
        IF(
            balance_before IS NOT NULL
            AND balance_after IS NOT NULL
            AND position_count = 1
            AND previous_position_count = 1
            AND balance_after > balance_before,

            balance_after - balance_before,
            0
        )
    ) / 1e24 AS contract_rewards_near

FROM ordered_changes

WHERE
    block_date >= DATE('{{start_date}}')
    AND block_date < DATE('{{end_date}}')
    AND update_reason = 'action_receipt_gas_reward'

GROUP BY utc_date
ORDER BY utc_date;