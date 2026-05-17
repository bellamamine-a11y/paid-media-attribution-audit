-- models/fct_creative_performance.sql
-- Rolls up to creative_id grain for Meta creatives.
-- meta_c01 and meta_c02 will show dominant purchase contribution (Truth 5).

CREATE OR REPLACE TABLE fct_creative_performance AS
WITH meta_creatives AS (
    SELECT *
    FROM stg_events
    WHERE channel = 'Meta'
      AND attribution_type = 'attributed'
),
meta_totals AS (
    SELECT
        SUM(cost)     AS meta_total_cost,
        SUM(purchase) AS meta_total_purchases,
        SUM(revenue)  AS meta_total_revenue
    FROM meta_creatives
)
SELECT
    m.creative_id,
    SUM(m.cost)                                                  AS total_cost,
    SUM(m.impressions)                                           AS total_impressions,
    SUM(m.clicks)                                                AS total_clicks,
    SUM(m.sessions)                                              AS total_sessions,
    SUM(m.add_to_cart)                                           AS total_atc,
    SUM(m.purchase)                                              AS total_purchases,
    SUM(m.revenue)                                               AS total_revenue,

    -- ROAS per creative
    CASE
        WHEN SUM(m.cost) > 0
        THEN ROUND(SUM(m.revenue) / SUM(m.cost), 2)
        ELSE NULL
    END AS roas,

    -- CPA per creative
    CASE
        WHEN SUM(m.purchase) > 0
        THEN ROUND(SUM(m.cost) / SUM(m.purchase), 2)
        ELSE NULL
    END AS cpa,

    -- Spend share within Meta
    ROUND(SUM(m.cost) / t.meta_total_cost, 4)                   AS spend_share,

    -- Purchase contribution: the concentration signal
    ROUND(CAST(SUM(m.purchase) AS DOUBLE) / NULLIF(t.meta_total_purchases, 0), 4) AS purchase_contribution,

    -- Revenue contribution
    ROUND(SUM(m.revenue) / NULLIF(t.meta_total_revenue, 0), 4)  AS revenue_contribution

FROM meta_creatives AS m
CROSS JOIN meta_totals AS t
GROUP BY m.creative_id, t.meta_total_cost, t.meta_total_purchases, t.meta_total_revenue
ORDER BY total_purchases DESC;
