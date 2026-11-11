SELECT
  TIMESTAMP_MICROS(
    DIV(computed_at_block_timestamp, 1000)
  ) AS block_timestamp_utc,
  block_date AS utc_date,
  total_tokens_supply AS total_supply,
  circulating_tokens_supply AS circulating_supply
FROM
  `bigquery-public-data.crypto_near_mainnet_us.circulating_supply`
WHERE
  block_date >= DATE('{{start_date}}')
  AND block_date < DATE('{{end_date}}')
ORDER BY
  block_date;
