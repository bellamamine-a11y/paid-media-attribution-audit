"""
data/generate.py

Generates 120 days of synthetic paid media funnel data for Marble & Co,
a fictional DTC luxury homegoods brand. Fixed seed for reproducibility.

Five structural truths are encoded in the numbers:
  1. Optimization mismatch: PMax and Meta Prospecting optimized for ATC,
     not purchase. High ATC volume, poor purchase ROAS.
  2. Tracking break: days 1-59 have 35-45% unattributed purchases.
     Day 60 tracking fix causes an attribution step-change, not real growth.
  3. Geo opportunity: PT has ~2x CTR and strong purchase ROAS on tiny spend.
  4. Price event: day 75 AOV steps up 12%, CVR dips 2 weeks then recovers.
  5. Creative concentration: 2 of 6 Meta creatives drive ~73% of purchases.
"""

import numpy as np
import pandas as pd
from pathlib import Path

SEED = 42
rng = np.random.default_rng(SEED)

START = pd.Timestamp("2024-01-01")
DATES = pd.date_range(START, periods=120, freq="D")

TRACKING_FIX_IDX = 59  # 0-based, 2024-03-01
PRICE_EVENT_IDX  = 74  # 0-based, 2024-03-16

OUT = Path(__file__).parent / "sample"
OUT.mkdir(exist_ok=True)

# ---- Campaign definitions ----

CAMPAIGNS = [
    ("Google", "Brand Search"),
    ("Google", "Non-Brand Search"),
    ("Google", "Shopping"),
    ("Google", "Performance Max"),
    ("Meta",   "Prospecting"),
    ("Meta",   "Retargeting"),
]

GEOS = ["US", "UK", "CA", "AU", "DE", "PT"]

GEO_SPEND_SHARE = dict(US=0.57, UK=0.14, CA=0.09, AU=0.08, DE=0.07, PT=0.05)

# Total daily base spend per campaign (across all geos, average weekday)
CAMPAIGN_BASE_SPEND = {
    "Brand Search":     290.0,
    "Non-Brand Search": 425.0,
    "Shopping":         315.0,
    "Performance Max":  560.0,
    "Prospecting":      385.0,
    "Retargeting":      165.0,
}

CREATIVES = {
    "Brand Search":     ["goog_c01", "goog_c02"],
    "Non-Brand Search": ["goog_c03", "goog_c04"],
    "Shopping":         ["goog_c05", "goog_c06"],
    "Performance Max":  ["goog_c07", "goog_c08"],
    "Prospecting":      ["meta_c01", "meta_c02", "meta_c03", "meta_c04", "meta_c05", "meta_c06"],
    "Retargeting":      ["meta_c01", "meta_c02", "meta_c03", "meta_c04", "meta_c05", "meta_c06"],
}

CREATIVE_SPEND_SHARE = {
    "Brand Search":     [0.55, 0.45],
    "Non-Brand Search": [0.52, 0.48],
    "Shopping":         [0.50, 0.50],
    "Performance Max":  [0.54, 0.46],
    "Prospecting":      [0.27, 0.29, 0.14, 0.13, 0.09, 0.08],
    "Retargeting":      [0.33, 0.31, 0.12, 0.11, 0.07, 0.06],
}

# Average CPC per campaign
BASE_CPC = {
    "Brand Search":     1.85,
    "Non-Brand Search": 0.92,
    "Shopping":         0.65,
    "Performance Max":  0.78,
    "Prospecting":      0.45,
    "Retargeting":      0.58,
}

# CTR (impressions -> clicks). Truth 3: PT gets ~2x via GEO_CTR_MULT.
BASE_CTR = {
    "Brand Search":     0.082,
    "Non-Brand Search": 0.031,
    "Shopping":         0.015,
    "Performance Max":  0.008,
    "Prospecting":      0.012,
    "Retargeting":      0.025,
}

GEO_CTR_MULT = dict(US=1.00, UK=0.94, CA=0.91, AU=0.87, DE=0.83, PT=1.95)

# Session -> ATC rate.
# Truth 1: PMax and Prospecting have the HIGHEST ATC rates (optimized for it),
# but the LOWEST purchase rates. The ATC-to-purchase conversion is ~3-6%.
ATC_RATE = {
    "Brand Search":     0.180,
    "Non-Brand Search": 0.150,
    "Shopping":         0.140,
    "Performance Max":  0.190,  # Highest ATC rate, worst purchase efficiency
    "Prospecting":      0.170,  # High ATC rate, terrible purchase efficiency
    "Retargeting":      0.160,
}

# Checkout rate: ATC -> begin_checkout
CHECKOUT_RATE = {
    "Brand Search":     0.80,
    "Non-Brand Search": 0.72,
    "Shopping":         0.70,
    "Performance Max":  0.55,
    "Prospecting":      0.45,
    "Retargeting":      0.68,
}

# Session -> purchase rate. These encode ROAS relationships:
#   Brand Search ~6x, Non-Brand ~3x, Shopping ~4x,
#   PMax ~1.5x (poor!), Prospecting ~0.9x (money-losing), Retargeting ~3x.
PURCHASE_RATE = {
    "Brand Search":     0.103,
    "Non-Brand Search": 0.026,
    "Shopping":         0.024,
    "Performance Max":  0.011,
    "Prospecting":      0.0038,
    "Retargeting":      0.016,
}

# Truth 3: PT has strong purchase ROAS (~1.85x multiplier)
GEO_PURCHASE_MULT = dict(US=1.00, UK=0.93, CA=0.89, AU=0.85, DE=0.81, PT=2.80)

# Truth 5: Meta creative purchase concentration.
# meta_c01 + meta_c02 drive ~73% of Meta purchases despite ~56% of spend.
META_CREATIVE_PURCHASE_MULT = {
    "meta_c01": 1.38,
    "meta_c02": 1.30,
    "meta_c03": 0.64,
    "meta_c04": 0.62,
    "meta_c05": 0.67,
    "meta_c06": 0.52,
}

BASE_AOV = 122.0
PRICE_STEP = 1.12  # 12% AOV increase on day 75

WEEKDAY_MULT = [0.88, 0.91, 0.95, 0.97, 1.09, 1.13, 1.07]  # Mon-Sun


# ---- Helper functions ----

def _wm(date):
    return WEEKDAY_MULT[date.dayofweek]


def _aov(day_idx):
    base = BASE_AOV if day_idx < PRICE_EVENT_IDX else BASE_AOV * PRICE_STEP
    return base * (1 + rng.normal(0, 0.018))


def _cvr_mult(day_idx):
    """Truth 4: CVR dips after price event, recovers linearly over 14 days."""
    if day_idx < PRICE_EVENT_IDX:
        return 1.0
    days_after = day_idx - PRICE_EVENT_IDX
    if days_after <= 14:
        return 0.82 + (days_after / 14.0) * 0.18
    return 1.0


def _tracking_gap(day_idx):
    """Truth 2: pre-fix gap 35-45%, post-fix gap 2-5%."""
    if day_idx < TRACKING_FIX_IDX:
        return float(rng.uniform(0.35, 0.45))
    return float(rng.uniform(0.02, 0.05))


# ---- Main generation ----

def generate_spend_events():
    spend_rows = []
    event_rows = []

    for day_idx, date in enumerate(DATES):
        wm = _wm(date)
        gap = _tracking_gap(day_idx)
        cvr_mult = _cvr_mult(day_idx)
        aov = _aov(day_idx)

        day_unattrib_purchases = 0
        day_unattrib_revenue = 0.0

        for channel, campaign in CAMPAIGNS:
            base_spend = CAMPAIGN_BASE_SPEND[campaign]
            creatives = CREATIVES[campaign]
            c_shares = CREATIVE_SPEND_SHARE[campaign]
            cpc = BASE_CPC[campaign]
            ctr = BASE_CTR[campaign]
            atc_rate = ATC_RATE[campaign]
            checkout_rate = CHECKOUT_RATE[campaign]
            purchase_rate = PURCHASE_RATE[campaign]

            for geo in GEOS:
                geo_spend_total = base_spend * GEO_SPEND_SHARE[geo] * wm
                geo_spend_total *= (1 + rng.normal(0, 0.07))
                geo_spend_total = max(geo_spend_total, 1.0)

                geo_ctr_m = GEO_CTR_MULT[geo]
                geo_purch_m = GEO_PURCHASE_MULT[geo]

                for c_idx, creative_id in enumerate(creatives):
                    c_share = c_shares[c_idx]
                    spend = geo_spend_total * c_share * (1 + rng.normal(0, 0.05))
                    spend = max(spend, 0.01)

                    # Clicks derived from spend / CPC
                    clicks = max(0, int(round(spend / cpc * (1 + rng.normal(0, 0.09)))))

                    # Impressions derived from CTR
                    eff_ctr = ctr * geo_ctr_m * (1 + rng.normal(0, 0.06))
                    eff_ctr = max(eff_ctr, 0.001)
                    impressions = int(clicks / eff_ctr) if clicks > 0 else 0

                    # Sessions
                    sessions = max(0, int(round(clicks * 0.88 * (1 + rng.normal(0, 0.05)))))

                    # Effective purchase rate with geo and creative multipliers
                    if channel == "Meta":
                        creative_purch_m = META_CREATIVE_PURCHASE_MULT.get(creative_id, 1.0)
                    else:
                        creative_purch_m = 1.0

                    eff_purch_rate = (
                        purchase_rate
                        * geo_purch_m
                        * cvr_mult
                        * creative_purch_m
                        * (1 + rng.normal(0, 0.10))
                    )
                    eff_purch_rate = max(eff_purch_rate, 0.0)

                    # Poisson draw is the correct model for rare discrete events
                    # (avoids int(round()) collapsing small rates to 0)
                    true_purchases = int(rng.poisson(max(sessions * eff_purch_rate, 0)))

                    # Apply attribution tracking gap via binomial draw (Truth 2).
                    # Using binomial instead of rounding avoids integer-rounding
                    # collapse at low purchase counts, especially for post-fix
                    # where the gap is only 2-5%.
                    unattrib = int(rng.binomial(true_purchases, gap))
                    attributed_purchases = true_purchases - unattrib

                    day_unattrib_purchases += unattrib
                    day_unattrib_revenue += unattrib * aov

                    # ATC: sessions * rate, but must be >= true_purchases
                    # (logically you add to cart before purchasing)
                    eff_atc_rate = atc_rate * (1 + rng.normal(0, 0.08))
                    atc_natural = max(0, int(round(sessions * eff_atc_rate)))
                    atc = max(true_purchases, atc_natural)

                    # Checkout: between atc and true_purchases
                    begin_checkout_natural = max(0, int(round(atc * checkout_rate * (1 + rng.normal(0, 0.07)))))
                    begin_checkout = max(true_purchases, begin_checkout_natural)

                    revenue = attributed_purchases * aov

                    spend_rows.append({
                        "date":        date.strftime("%Y-%m-%d"),
                        "channel":     channel,
                        "campaign":    campaign,
                        "geo":         geo,
                        "creative_id": creative_id,
                        "impressions": impressions,
                        "clicks":      clicks,
                        "cost":        round(spend, 2),
                    })
                    event_rows.append({
                        "date":           date.strftime("%Y-%m-%d"),
                        "channel":        channel,
                        "campaign":       campaign,
                        "geo":            geo,
                        "creative_id":    creative_id,
                        "sessions":       sessions,
                        "add_to_cart":    atc,
                        "begin_checkout": begin_checkout,
                        "purchase":       attributed_purchases,
                        "revenue":        round(revenue, 2),
                    })

        # Direct / Unattributed row (Truth 2: the tracking gap materialises here)
        event_rows.append({
            "date":           date.strftime("%Y-%m-%d"),
            "channel":        "Direct",
            "campaign":       "Unattributed",
            "geo":            "Unknown",
            "creative_id":    "none",
            "sessions":       0,
            "add_to_cart":    0,
            "begin_checkout": 0,
            "purchase":       day_unattrib_purchases,
            "revenue":        round(day_unattrib_revenue, 2),
        })

    return pd.DataFrame(spend_rows), pd.DataFrame(event_rows)


def generate_email():
    rows = []
    flows = {
        "welcome": {
            "base_sent": 520, "open_rate": 0.35, "click_rate": 0.08,
            "rev_per_click": 14.50,
        },
        "abandoned_cart": {
            "base_sent": 210, "open_rate": 0.46, "click_rate": 0.21,
            "rev_per_click": 38.00,
        },
        "post_purchase": {
            "base_sent": 155, "open_rate": 0.51, "click_rate": 0.13,
            "rev_per_click": 6.20,
        },
    }
    for date in DATES:
        wm = _wm(date)
        for flow, cfg in flows.items():
            sent = max(1, int(round(cfg["base_sent"] * wm * (1 + rng.normal(0, 0.08)))))
            opens = max(0, int(round(sent * cfg["open_rate"] * (1 + rng.normal(0, 0.06)))))
            clicks = max(0, int(round(opens * cfg["click_rate"] * (1 + rng.normal(0, 0.07)))))
            attributed_revenue = round(clicks * cfg["rev_per_click"] * (1 + rng.normal(0, 0.05)), 2)
            rows.append({
                "date":               date.strftime("%Y-%m-%d"),
                "flow":               flow,
                "sent":               sent,
                "opens":              opens,
                "clicks":             clicks,
                "attributed_revenue": attributed_revenue,
            })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("Generating synthetic data for Marble & Co...")
    spend_df, events_df = generate_spend_events()
    email_df = generate_email()

    spend_df.to_csv(OUT / "spend.csv", index=False)
    events_df.to_csv(OUT / "events.csv", index=False)
    email_df.to_csv(OUT / "email.csv", index=False)

    print(f"  spend.csv:  {len(spend_df):,} rows")
    print(f"  events.csv: {len(events_df):,} rows")
    print(f"  email.csv:  {len(email_df):,} rows")
    print(f"Output directory: {OUT}")
    print("Done.")
