SELECT
    block_date AS utc_date,
    SUM(tokens_burnt) / 1e24 AS gross_tokens_burnt_near
FROM
    `bigquery-public-data.crypto_near_mainnet_us.execution_outcomes`
WHERE
    block_date >= DATE('{{start_date}}')
    AND block_date < DATE('{{end_date}}')
GROUP BY
    block_date
ORDER BY
    block_date;