-- models/fct_geo_performance.sql
-- Rolls up to geo grain across all attributed channels.
-- PT appears with high CTR and ROAS but minimal spend share (Truth 3).

CREATE OR REPLACE TABLE fct_geo_performance AS
WITH attributed AS (
    SELECT *
    FROM stg_events
    WHERE attribution_type = 'attributed'
),
totals AS (
    SELECT
        SUM(cost)    AS grand_cost,
        SUM(revenue) AS grand_revenue
    FROM attributed
)
SELECT
    a.geo,
    SUM(a.cost)                                                  AS total_cost,
    SUM(a.impressions)                                           AS total_impressions,
    SUM(a.clicks)                                                AS total_clicks,
    SUM(a.sessions)                                              AS total_sessions,
    SUM(a.add_to_cart)                                           AS total_atc,
    SUM(a.purchase)                                              AS total_purchases,
    SUM(a.revenue)                                               AS total_revenue,

    -- CTR: PT will be ~2x the network average
    CASE
        WHEN SUM(a.impressions) > 0
        THEN ROUND(CAST(SUM(a.clicks) AS DOUBLE) / SUM(a.impressions), 5)
        ELSE NULL
    END AS blended_ctr,

    -- ROAS
    CASE
        WHEN SUM(a.cost) > 0
        THEN ROUND(SUM(a.revenue) / SUM(a.cost), 2)
        ELSE NULL
    END AS roas,

    -- CPA
    CASE
        WHEN SUM(a.purchase) > 0
        THEN ROUND(SUM(a.cost) / SUM(a.purchase), 2)
        ELSE NULL
    END AS cpa,

    -- Spend share (should reveal PT as underinvested)
    ROUND(SUM(a.cost) / t.grand_cost, 4)                        AS spend_share,

    -- Revenue share
    ROUND(SUM(a.revenue) / t.grand_revenue, 4)                  AS revenue_share

FROM attributed AS a
CROSS JOIN totals AS t
GROUP BY a.geo, t.grand_cost, t.grand_revenue
ORDER BY total_revenue DESC;
