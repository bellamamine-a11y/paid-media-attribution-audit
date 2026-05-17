-- models/fct_channel_performance.sql
-- Rolls up to channel + campaign grain.
-- The ATC-to-purchase ratio is the key column that exposes Truth 1.

CREATE OR REPLACE TABLE fct_channel_performance AS
SELECT
    channel,
    campaign,
    SUM(cost)                                           AS total_cost,
    SUM(impressions)                                    AS total_impressions,
    SUM(clicks)                                         AS total_clicks,
    SUM(sessions)                                       AS total_sessions,
    SUM(add_to_cart)                                    AS total_atc,
    SUM(begin_checkout)                                 AS total_begin_checkout,
    SUM(purchase)                                       AS total_purchases,
    SUM(revenue)                                        AS total_revenue,

    -- Blended ROAS on attributed revenue
    CASE
        WHEN SUM(cost) > 0
        THEN ROUND(SUM(revenue) / SUM(cost), 2)
        ELSE NULL
    END AS roas,

    -- CPA: cost per attributed purchase
    CASE
        WHEN SUM(purchase) > 0
        THEN ROUND(SUM(cost) / SUM(purchase), 2)
        ELSE NULL
    END AS cpa,

    -- Blended CTR
    CASE
        WHEN SUM(impressions) > 0
        THEN ROUND(CAST(SUM(clicks) AS DOUBLE) / SUM(impressions), 5)
        ELSE NULL
    END AS blended_ctr,

    -- Session-level CVR (purchase / sessions)
    CASE
        WHEN SUM(sessions) > 0
        THEN ROUND(CAST(SUM(purchase) AS DOUBLE) / SUM(sessions), 5)
        ELSE NULL
    END AS cvr,

    -- ATC rate (add to cart / sessions): PMax and Prospecting score highest here
    CASE
        WHEN SUM(sessions) > 0
        THEN ROUND(CAST(SUM(add_to_cart) AS DOUBLE) / SUM(sessions), 5)
        ELSE NULL
    END AS atc_rate,

    -- ATC-to-purchase rate: reveals the mismatch for PMax and Prospecting
    CASE
        WHEN SUM(add_to_cart) > 0
        THEN ROUND(CAST(SUM(purchase) AS DOUBLE) / SUM(add_to_cart), 5)
        ELSE NULL
    END AS atc_to_purchase_rate,

    -- Spend share (across attributed channels only, excluding Direct)
    CASE
        WHEN SUM(cost) > 0
        THEN ROUND(
            SUM(cost) / NULLIF(SUM(SUM(cost)) OVER (PARTITION BY attribution_type), 0),
            4
        )
        ELSE NULL
    END AS spend_share,

    attribution_type

FROM stg_events
GROUP BY channel, campaign, attribution_type
ORDER BY total_revenue DESC;
