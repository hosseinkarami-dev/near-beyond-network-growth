SELECT
    b.block_date AS utc_date,
    b.block_height,
    b.total_supply,
    c.circulating_tokens_supply as circulating_supply
FROM
    `bigquery-public-data.crypto_near_mainnet_us.blocks` b
LEFT JOIN
    `bigquery-public-data.crypto_near_mainnet_us.circulating_supply` c
    ON b.block_date = c.block_date
WHERE
  b.block_date >= DATE('{{start_date}}')
  AND b.block_date < DATE('{{end_date}}')
QUALIFY
    ROW_NUMBER() OVER (
        PARTITION BY b.block_date
        ORDER BY b.block_timestamp DESC, b.block_height DESC
    ) = 1
ORDER BY
    utc_date;