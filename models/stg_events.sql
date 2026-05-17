-- models/stg_events.sql
-- Joins spend and events at the same grain (date, channel, campaign, geo, creative_id).
-- Derives CTR, CVR, ROAS, CPA, CPC, attribution flag, and tracking-period flag.

CREATE OR REPLACE TABLE stg_events AS
SELECT
    e.date,
    e.channel,
    e.campaign,
    e.geo,
    e.creative_id,

    -- Spend-side metrics (NULL for Direct/Unattributed rows)
    COALESCE(s.impressions, 0)          AS impressions,
    COALESCE(s.clicks, 0)               AS clicks,
    COALESCE(s.cost, 0.0)               AS cost,

    -- Event-side metrics
    e.sessions,
    e.add_to_cart,
    e.begin_checkout,
    e.purchase,
    e.revenue,

    -- Derived rates
    CASE
        WHEN COALESCE(s.impressions, 0) > 0
        THEN ROUND(CAST(COALESCE(s.clicks, 0) AS DOUBLE) / s.impressions, 5)
        ELSE NULL
    END AS ctr,

    CASE
        WHEN e.sessions > 0
        THEN ROUND(CAST(e.purchase AS DOUBLE) / e.sessions, 5)
        ELSE NULL
    END AS cvr,

    CASE
        WHEN COALESCE(s.cost, 0) > 0
        THEN ROUND(e.revenue / s.cost, 4)
        ELSE NULL
    END AS roas,

    CASE
        WHEN e.purchase > 0
        THEN ROUND(COALESCE(s.cost, 0.0) / e.purchase, 2)
        ELSE NULL
    END AS cpa,

    CASE
        WHEN COALESCE(s.clicks, 0) > 0
        THEN ROUND(s.cost / s.clicks, 4)
        ELSE NULL
    END AS cpc,

    CASE
        WHEN e.add_to_cart > 0
        THEN ROUND(CAST(e.purchase AS DOUBLE) / e.add_to_cart, 5)
        ELSE NULL
    END AS atc_to_purchase_rate,

    -- Attribution flag: 'unattributed' for Direct rows, 'attributed' otherwise
    CASE
        WHEN e.channel = 'Direct' THEN 'unattributed'
        ELSE 'attributed'
    END AS attribution_type,

    -- Tracking-period flag: day 60 = 2024-03-01 is the fix date
    CASE
        WHEN e.date < DATE '2024-03-01' THEN 'pre_fix'
        ELSE 'post_fix'
    END AS tracking_period

FROM read_csv_auto('data/sample/events.csv') AS e
LEFT JOIN read_csv_auto('data/sample/spend.csv') AS s
    ON  e.date        = s.date
    AND e.channel     = s.channel
    AND e.campaign    = s.campaign
    AND e.geo         = s.geo
    AND e.creative_id = s.creative_id
ORDER BY e.date, e.channel, e.campaign, e.geo, e.creative_id;
