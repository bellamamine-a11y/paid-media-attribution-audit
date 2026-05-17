"""
analysis/create_notebook.py

Generates analysis/diagnosis.ipynb programmatically.
Run once: python analysis/create_notebook.py
"""

import nbformat
from pathlib import Path

HERE = Path(__file__).parent


def md(text):
    c = nbformat.v4.new_markdown_cell(text)
    return c


def code(text):
    c = nbformat.v4.new_code_cell(text)
    return c


cells = []

# ---- Title ----
cells.append(md("""# Paid Media Attribution Audit: Marble & Co
## Diagnosis Notebook

**Brand:** Marble & Co | DTC luxury homegoods
**Period:** 2024-01-01 to 2024-04-29 (120 days)
**Analyst note:** This notebook walks through five measurement problems
found in the synthetic dataset, in the order an analyst would actually
discover them. Each section ends with a plain-language finding.

Run this notebook from the project root or the analysis/ directory.
The data path logic handles both.
"""))

# ---- Setup ----
cells.append(md("## Setup"))
cells.append(code("""\
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# Locate data directory regardless of where Jupyter was launched from
here = Path.cwd()
if (here / "data" / "sample").exists():
    DATA = here / "data" / "sample"
elif (here.parent / "data" / "sample").exists():
    DATA = here.parent / "data" / "sample"
else:
    raise FileNotFoundError("Run from the project root or analysis/ directory.")

spend  = pd.read_csv(DATA / "spend.csv",  parse_dates=["date"])
events = pd.read_csv(DATA / "events.csv", parse_dates=["date"])
email  = pd.read_csv(DATA / "email.csv",  parse_dates=["date"])

print(f"spend:  {len(spend):,} rows, {spend['date'].min().date()} to {spend['date'].max().date()}")
print(f"events: {len(events):,} rows")
print(f"email:  {len(email):,} rows")

TRACKING_FIX = pd.Timestamp("2024-03-01")
PRICE_EVENT  = pd.Timestamp("2024-03-16")
"""))

# ---- Part 1 ----
cells.append(md("""## 1. Headline Funnel and Spend Overview

Before diving into anomalies, understand the overall shape of the business:
where does the spend go, and how does the funnel convert?
"""))

cells.append(code("""\
# Total spend by campaign
camp_spend = (
    spend.groupby("campaign")["cost"].sum()
    .sort_values(ascending=False)
    .reset_index()
)
camp_spend["share"] = camp_spend["cost"] / camp_spend["cost"].sum()

fig = px.bar(
    camp_spend,
    x="campaign", y="cost", text="cost",
    title="Total Spend by Campaign (120 days)",
    labels={"cost": "Spend ($)", "campaign": "Campaign"},
)
fig.update_traces(texttemplate="$%{text:,.0f}", textposition="outside")
fig.update_layout(height=380)
fig.show()

print(camp_spend.assign(cost=camp_spend["cost"].map("${:,.0f}".format),
                        share=camp_spend["share"].map("{:.1%}".format)).to_string(index=False))
"""))

cells.append(code("""\
# Headline funnel: total attributed vs unattributed
attr  = events[events["channel"] != "Direct"]
direct = events[events["channel"] == "Direct"]

print("--- Attributed channels ---")
print(f"  Sessions:         {attr['sessions'].sum():,}")
print(f"  Add to cart:      {attr['add_to_cart'].sum():,}")
print(f"  Begin checkout:   {attr['begin_checkout'].sum():,}")
print(f"  Purchases:        {attr['purchase'].sum():,}")
print(f"  Revenue:          ${attr['revenue'].sum():,.0f}")

print()
print("--- Direct / Unattributed ---")
print(f"  Purchases:        {direct['purchase'].sum():,}")
print(f"  Revenue:          ${direct['revenue'].sum():,.0f}")

total_purch = events["purchase"].sum()
unattr_pct  = direct["purchase"].sum() / total_purch
print()
print(f"Unattributed share of all purchases: {unattr_pct:.1%}")
"""))

cells.append(code("""\
# Daily revenue: attributed vs total
daily_attr   = attr.groupby("date")["revenue"].sum().rename("attributed")
daily_direct = direct.groupby("date")["revenue"].sum().rename("direct")
daily_rev    = pd.concat([daily_attr, daily_direct], axis=1).fillna(0)
daily_rev["total"] = daily_rev["attributed"] + daily_rev["direct"]

fig = go.Figure()
fig.add_trace(go.Scatter(x=daily_rev.index, y=daily_rev["attributed"],
                         name="Attributed", fill="tozeroy"))
fig.add_trace(go.Scatter(x=daily_rev.index, y=daily_rev["total"],
                         name="Total (incl. Direct)", line=dict(dash="dot")))
fig.add_vline(x=TRACKING_FIX, line_dash="dash", line_color="red",
              annotation_text="Tracking fix")
fig.add_vline(x=PRICE_EVENT, line_dash="dot", line_color="orange",
              annotation_text="Price event")
fig.update_layout(title="Daily Revenue: Attributed vs Total", height=380)
fig.show()
"""))

cells.append(md("""**Finding 1a:** Performance Max and Meta Prospecting together consume
roughly 44% of total spend. We need to verify these are delivering proportional
purchase value, not just funnel activity.

**Finding 1b:** A significant portion of revenue is landing in Direct/Unattributed.
The gap closes sharply around day 60. This warrants immediate investigation.
"""))

# ---- Part 2 ----
cells.append(md("""## 2. The Add-to-Cart vs Purchase Mismatch (Truth 1)

Platforms report "conversions" based on whatever goal you optimize toward.
If a campaign is set to optimize for add-to-cart, the platform will report
strong conversion rates, but those ATCs may not become purchases.

This section compares ATC rate, purchase rate, and ROAS across campaigns.
"""))

cells.append(code("""\
# Per-campaign: ATC rate, purchase rate, ATC-to-purchase rate
camp_funnel = (
    attr.groupby("campaign")
    .agg(
        spend=("cost", "sum") if "cost" in attr.columns else ("revenue", "count"),
        sessions=("sessions", "sum"),
        atc=("add_to_cart", "sum"),
        purchase=("purchase", "sum"),
        revenue=("revenue", "sum"),
    )
    .reset_index()
)

# Need spend from spend table
camp_spend_join = spend.groupby("campaign")["cost"].sum().reset_index()
camp_funnel = camp_funnel.merge(camp_spend_join, on="campaign", how="left")

camp_funnel["atc_rate"]            = camp_funnel["atc"]      / camp_funnel["sessions"]
camp_funnel["purchase_rate"]       = camp_funnel["purchase"] / camp_funnel["sessions"]
camp_funnel["atc_to_purchase_rate"]= camp_funnel["purchase"] / camp_funnel["atc"]
camp_funnel["roas"]                = camp_funnel["revenue"]  / camp_funnel["cost"]
camp_funnel["cpa"]                 = camp_funnel["cost"]     / camp_funnel["purchase"]

camp_funnel = camp_funnel.sort_values("roas", ascending=False)
print(camp_funnel[[
    "campaign", "cost", "roas", "atc_rate",
    "purchase_rate", "atc_to_purchase_rate", "cpa"
]].assign(
    cost=camp_funnel["cost"].map("${:,.0f}".format),
    roas=camp_funnel["roas"].map("{:.2f}x".format),
    atc_rate=camp_funnel["atc_rate"].map("{:.1%}".format),
    purchase_rate=camp_funnel["purchase_rate"].map("{:.2%}".format),
    atc_to_purchase_rate=camp_funnel["atc_to_purchase_rate"].map("{:.1%}".format),
    cpa=camp_funnel["cpa"].map("${:,.2f}".format),
).to_string(index=False))
"""))

cells.append(code("""\
# Side-by-side chart: ATC rate vs ROAS
fig = go.Figure()
colors = {
    "Brand Search": "#1a56db", "Non-Brand Search": "#7e3af2",
    "Shopping": "#0694a2", "Performance Max": "#e3a008",
    "Prospecting": "#ff5a1f", "Retargeting": "#31c48d",
}
fig.add_trace(go.Bar(
    name="ROAS (purchase-based)",
    x=camp_funnel["campaign"],
    y=camp_funnel["roas"],
    marker_color=[colors.get(c, "#6b7280") for c in camp_funnel["campaign"]],
    yaxis="y1",
))
fig.add_trace(go.Scatter(
    name="ATC rate",
    x=camp_funnel["campaign"],
    y=camp_funnel["atc_rate"],
    mode="lines+markers",
    marker=dict(size=11, color="red"),
    yaxis="y2",
))
fig.update_layout(
    title="ROAS vs ATC Rate by Campaign (the mismatch)",
    yaxis=dict(title="ROAS"),
    yaxis2=dict(title="ATC Rate", overlaying="y", side="right", showgrid=False),
    height=420,
    legend=dict(orientation="h", y=1.12),
)
fig.show()
"""))

cells.append(md("""**Key Finding (Truth 1):**

Performance Max and Meta Prospecting have the **highest ATC rates** in the account
(roughly 17-19% of sessions add to cart). But their ATC-to-purchase conversion
is **3-6%**, compared to **50%+ for Brand Search**.

Both campaigns were set to optimize for add-to-cart, not purchase. The platform
is delivering exactly what it was asked for. But the business metric that matters
is purchase ROAS, and on that measure:

- Brand Search: ~6x ROAS
- Prospecting: ~0.9x ROAS (spending more than it earns)
- Performance Max: ~1.5x ROAS

**Recommendation:** Switch PMax and Prospecting bid strategies to purchase/ROAS
targets immediately. Expect short-term volume drop as the algorithm relearns,
but purchase efficiency should improve materially.
"""))

# ---- Part 3 ----
cells.append(md("""## 3. The Attribution Coverage Break (Truth 2)

A sharp step-change in attributed purchases around day 60 (2024-03-01) catches
the eye. The naive interpretation is a real demand surge. The correct
interpretation is a tracking fix.

This section shows why misreading this as performance improvement would lead to
wrong budget decisions.
"""))

cells.append(code("""\
# Daily attributed vs unattributed purchases
daily_attr_p   = attr.groupby("date")["purchase"].sum().rename("attributed")
daily_direct_p = direct.groupby("date")["purchase"].sum().rename("direct")
daily_purch    = pd.concat([daily_attr_p, daily_direct_p], axis=1).fillna(0)
daily_purch["total"] = daily_purch["attributed"] + daily_purch["direct"]
daily_purch["unattr_pct"] = daily_purch["direct"] / daily_purch["total"]

# 7-day rolling totals to smooth noise
roll = daily_purch.rolling(7, center=True).mean()

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=roll.index, y=roll["total"],
    name="Total purchases (7d avg)", line=dict(color="gray", dash="dot")
))
fig.add_trace(go.Scatter(
    x=roll.index, y=roll["attributed"],
    name="Attributed (7d avg)", fill="tozeroy", line=dict(color="#1a56db")
))
fig.add_trace(go.Scatter(
    x=roll.index, y=roll["direct"],
    name="Unattributed / Direct (7d avg)", fill="tozeroy",
    line=dict(color="#ef4444"), stackgroup="one"
))
fig.add_vline(x=TRACKING_FIX, line_dash="dash", line_color="red",
              annotation_text="Tracking fix landed here")
fig.update_layout(
    title="Daily Purchases: Attributed vs Unattributed (7-day rolling)",
    yaxis_title="Purchases",
    height=420,
)
fig.show()
"""))

cells.append(code("""\
# Quantify the gap before and after the fix
pre_fix  = daily_purch[daily_purch.index < TRACKING_FIX]
post_fix = daily_purch[daily_purch.index >= TRACKING_FIX]

print("Pre-fix period (2024-01-01 to 2024-02-29):")
print(f"  Avg daily attributed purchases:  {pre_fix['attributed'].mean():.1f}")
print(f"  Avg daily unattributed:          {pre_fix['direct'].mean():.1f}")
print(f"  Avg unattributed rate:           {pre_fix['unattr_pct'].mean():.1%}")
print()
print("Post-fix period (2024-03-01 to 2024-04-29):")
print(f"  Avg daily attributed purchases:  {post_fix['attributed'].mean():.1f}")
print(f"  Avg daily unattributed:          {post_fix['direct'].mean():.1f}")
print(f"  Avg unattributed rate:           {post_fix['unattr_pct'].mean():.1%}")
print()
print("Avg total purchases (should be stable across both periods):")
print(f"  Pre:  {pre_fix['total'].mean():.1f}")
print(f"  Post: {post_fix['total'].mean():.1f}")
"""))

cells.append(md("""> [!IMPORTANT]
> **Critical Warning: Do not misread the day-60 attributed purchase jump as a performance gain.**
>
> Total purchases (attributed + unattributed) were stable across the entire period.
> What changed on 2024-03-01 is that the tracking fix started correctly attributing
> purchases to paid channels instead of dropping them into Direct.
>
> If a stakeholder sees only the attributed line in their dashboard,
> they will believe marketing performance improved ~60% overnight.
> That is false. Any budget increase made in response to this signal would be
> based on measurement noise, not demand growth.
>
> The correct frame: for historical comparison, pre-fix attributed numbers must
> be divided by ~0.60 (i.e., divided by 1 minus the ~40% average gap rate)
> to get comparable figures.
"""))

# ---- Part 4 ----
cells.append(md("""## 4. The PT Geo Opportunity (Truth 3)

The geo breakdown often reveals markets that punch above their spend weight.
Portugal (PT) is the case here: high CTR, strong purchase ROAS, and tiny
current investment.
"""))

cells.append(code("""\
# Geo rollup
geo_funnel = (
    attr.groupby("geo")
    .agg(
        sessions=("sessions", "sum"),
        atc=("add_to_cart", "sum"),
        purchase=("purchase", "sum"),
        revenue=("revenue", "sum"),
    )
    .reset_index()
)

geo_spend = spend.groupby("geo")[["impressions", "clicks", "cost"]].sum().reset_index()
geo_df = geo_funnel.merge(geo_spend, on="geo")

geo_df["ctr"]          = geo_df["clicks"]   / geo_df["impressions"]
geo_df["roas"]         = geo_df["revenue"]  / geo_df["cost"]
geo_df["cpa"]          = geo_df["cost"]     / geo_df["purchase"]
geo_df["spend_share"]  = geo_df["cost"]     / geo_df["cost"].sum()
geo_df["rev_share"]    = geo_df["revenue"]  / geo_df["revenue"].sum()

geo_df = geo_df.sort_values("roas", ascending=False)

print(geo_df[[
    "geo", "cost", "spend_share", "roas", "ctr", "cpa"
]].assign(
    cost=geo_df["cost"].map("${:,.0f}".format),
    spend_share=geo_df["spend_share"].map("{:.1%}".format),
    roas=geo_df["roas"].map("{:.2f}x".format),
    ctr=geo_df["ctr"].map("{:.2%}".format),
    cpa=geo_df["cpa"].map("${:,.2f}".format),
).to_string(index=False))
"""))

cells.append(code("""\
fig = go.Figure()
fig.add_trace(go.Bar(
    name="ROAS", x=geo_df["geo"], y=geo_df["roas"], yaxis="y1",
    marker_color=["#1a56db" if g == "PT" else "#9ca3af" for g in geo_df["geo"]],
))
fig.add_trace(go.Scatter(
    name="CTR", x=geo_df["geo"], y=geo_df["ctr"],
    mode="lines+markers", yaxis="y2",
    marker=dict(size=10, color="red"),
))
fig.update_layout(
    title="ROAS and CTR by Geo (PT highlighted)",
    yaxis=dict(title="ROAS"),
    yaxis2=dict(title="CTR", overlaying="y", side="right", showgrid=False),
    height=400,
    legend=dict(orientation="h", y=1.12),
)
fig.show()
"""))

cells.append(md("""**Finding (Truth 3):**

Portugal (PT) has:
- CTR nearly 2x the network average
- Purchase ROAS materially above the next-best geo
- Only ~3% of total spend

The brand either has unmet organic demand in PT or the creative resonates
particularly well there. Either way, the current allocation underinvests.

**Recommendation:** Run a geo expansion test in PT: increase PT spend by
3-4x and monitor whether ROAS holds at scale. Even at 50% of current ROAS,
the expansion would outperform the spend being allocated to DE.
"""))

# ---- Part 5 ----
cells.append(md("""## 5. Price Event Effect on Conversion Rate (Truth 4)

A step-change in average order value around day 75 (2024-03-16) is visible
in the data. A 12% price increase typically causes a short-term conversion
rate dip as price-sensitive shoppers hesitate, followed by recovery as the
remaining demand adjusts.

This explains a two-week revenue wobble that could otherwise be misattributed
to media performance or seasonality.
"""))

cells.append(code("""\
# Daily AOV and CVR for attributed purchases
daily_rev_p = (
    attr.groupby("date")
    .agg(revenue=("revenue", "sum"), purchase=("purchase", "sum"),
         sessions=("sessions", "sum"))
    .assign(
        aov=lambda d: d["revenue"] / d["purchase"].clip(lower=1),
        cvr=lambda d: d["purchase"] / d["sessions"].clip(lower=1),
    )
)

roll_aov = daily_rev_p["aov"].rolling(7, center=True).mean()
roll_cvr = daily_rev_p["cvr"].rolling(7, center=True).mean()

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=roll_aov.index, y=roll_aov,
    name="AOV (7d avg)", line=dict(color="#1a56db")
))
fig.add_vline(x=PRICE_EVENT, line_dash="dot", line_color="orange",
              annotation_text="Price increase")
fig.update_layout(title="Average Order Value (7-day rolling)", height=320,
                  yaxis_title="AOV ($)")
fig.show()

fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=roll_cvr.index, y=roll_cvr,
    name="CVR (7d avg)", line=dict(color="#7e3af2")
))
fig2.add_vline(x=PRICE_EVENT, line_dash="dot", line_color="orange",
               annotation_text="Price increase")
fig2.update_layout(title="Session-to-Purchase CVR (7-day rolling)", height=320,
                   yaxis_title="CVR", yaxis_tickformat=".2%")
fig2.show()
"""))

cells.append(code("""\
# Quantify the CVR dip
two_weeks_before = daily_rev_p[
    (daily_rev_p.index >= PRICE_EVENT - pd.Timedelta(days=14)) &
    (daily_rev_p.index < PRICE_EVENT)
]["cvr"].mean()

two_weeks_after = daily_rev_p[
    (daily_rev_p.index >= PRICE_EVENT) &
    (daily_rev_p.index < PRICE_EVENT + pd.Timedelta(days=14))
]["cvr"].mean()

four_weeks_after = daily_rev_p[
    (daily_rev_p.index >= PRICE_EVENT + pd.Timedelta(days=14)) &
    (daily_rev_p.index < PRICE_EVENT + pd.Timedelta(days=28))
]["cvr"].mean()

pre_aov  = daily_rev_p[daily_rev_p.index < PRICE_EVENT]["aov"].mean()
post_aov = daily_rev_p[daily_rev_p.index >= PRICE_EVENT]["aov"].mean()

print(f"AOV before price event:          ${pre_aov:.2f}")
print(f"AOV after price event:           ${post_aov:.2f} (+{(post_aov/pre_aov - 1):.1%})")
print()
print(f"CVR 2 weeks before event:        {two_weeks_before:.2%}")
print(f"CVR 2 weeks immediately after:   {two_weeks_after:.2%}  ({(two_weeks_after/two_weeks_before - 1):.1%} vs prior)")
print(f"CVR 3-4 weeks after (recovery):  {four_weeks_after:.2%}  ({(four_weeks_after/two_weeks_before - 1):.1%} vs prior)")
"""))

cells.append(md("""**Finding (Truth 4):**

The 12% price increase on 2024-03-16 caused an immediate CVR dip of roughly
18-20% over the following two weeks. CVR then recovered as price-sensitive
demand washed out and the remaining base adapted to the new price.

This explains the revenue "wobble" visible around weeks 11-12 of the period.
The dip is mechanical (price elasticity), not a media performance problem.
A media team that reflexively increased spend in response to the CVR dip
would have wasted budget on a self-resolving issue.

**AOV tracking note:** If AOV is not tracked in your media dashboard, a
price change becomes invisible and the CVR drop looks unexplained. Recommend
adding AOV as a dashboard KPI.
"""))

# ---- Part 6 ----
cells.append(md("""## 6. Creative Concentration in Meta (Truth 5)

Meta's algorithm distributes budget across the creatives in an ad set based on
its performance signals. But it is worth verifying whether budget allocation
actually matches purchase contribution, or whether the spend is spread more
evenly than performance warrants.
"""))

cells.append(code("""\
# Meta creative rollup
meta = attr[attr["channel"] == "Meta"]
meta_spend = spend[spend["channel"] == "Meta"]

meta_cr = (
    meta.groupby("creative_id")
    .agg(purchase=("purchase", "sum"), revenue=("revenue", "sum"),
         atc=("add_to_cart", "sum"))
    .reset_index()
)
meta_cr_spend = meta_spend.groupby("creative_id")["cost"].sum().reset_index()
meta_cr = meta_cr.merge(meta_cr_spend, on="creative_id")

total_meta_purchase = meta_cr["purchase"].sum()
total_meta_spend    = meta_cr["cost"].sum()
total_meta_revenue  = meta_cr["revenue"].sum()

meta_cr["purchase_contrib"] = meta_cr["purchase"] / total_meta_purchase
meta_cr["spend_share"]      = meta_cr["cost"]     / total_meta_spend
meta_cr["roas"]             = meta_cr["revenue"]  / meta_cr["cost"]
meta_cr["cpa"]              = meta_cr["cost"]      / meta_cr["purchase"]

meta_cr = meta_cr.sort_values("purchase_contrib", ascending=False)

print(meta_cr[[
    "creative_id", "cost", "spend_share", "purchase", "purchase_contrib", "roas", "cpa"
]].assign(
    cost=meta_cr["cost"].map("${:,.0f}".format),
    spend_share=meta_cr["spend_share"].map("{:.1%}".format),
    purchase_contrib=meta_cr["purchase_contrib"].map("{:.1%}".format),
    roas=meta_cr["roas"].map("{:.2f}x".format),
    cpa=meta_cr["cpa"].map("${:,.2f}".format),
).to_string(index=False))
"""))

cells.append(code("""\
colors = ["#1a56db" if i < 2 else "#9ca3af" for i in range(len(meta_cr))]
fig = go.Figure()
fig.add_trace(go.Bar(
    name="Purchase contribution",
    x=meta_cr["creative_id"], y=meta_cr["purchase_contrib"],
    marker_color=colors,
    text=[f"{v:.1%}" for v in meta_cr["purchase_contrib"]],
    textposition="outside", yaxis="y1",
))
fig.add_trace(go.Scatter(
    name="Spend share",
    x=meta_cr["creative_id"], y=meta_cr["spend_share"],
    mode="lines+markers",
    marker=dict(size=10, color="orange"),
    yaxis="y2",
))
fig.update_layout(
    title="Meta Creative: Purchase Contribution vs Spend Share",
    yaxis=dict(title="Purchase Contribution", tickformat=".0%"),
    yaxis2=dict(title="Spend Share", overlaying="y", side="right",
                tickformat=".0%", showgrid=False),
    height=420,
    legend=dict(orientation="h", y=1.12),
)
fig.show()
"""))

cells.append(md("""**Finding (Truth 5):**

meta_c01 and meta_c02 together drive approximately 73% of Meta purchases
on roughly 56% of Meta spend. The four remaining creatives (meta_c03 through
meta_c06) collectively receive 44% of budget but generate only 27% of purchases.

The ROAS spread between top and bottom creatives is significant. The algorithm
is partially concentrating spend toward winners, but not fully: the tail
creatives are still consuming meaningful budget.

**Recommendation:**
- Pause meta_c03, meta_c04, meta_c05, and meta_c06.
- Reallocate their budget to meta_c01 and meta_c02.
- Watch for creative fatigue on the winners at higher spend. Plan two to three
  new creative variants within 30 days to maintain auction health.
"""))

# ---- Part 7 ----
cells.append(md("""## 7. Recommended Reallocation

This section quantifies the upside from acting on the five findings above,
expressed in business terms.
"""))

cells.append(code("""\
# Current state
total_spend    = spend["cost"].sum()
attr_revenue   = attr["revenue"].sum()
attr_purch     = attr["purchase"].sum()
blended_roas   = attr_revenue / total_spend
blended_cpa    = total_spend  / attr_purch

print("=== Current State (attributed, 120 days) ===")
print(f"Total spend:          ${total_spend:,.0f}")
print(f"Attributed revenue:   ${attr_revenue:,.0f}")
print(f"Attributed purchases: {attr_purch:,}")
print(f"Blended ROAS:         {blended_roas:.2f}x")
print(f"Blended CPA:          ${blended_cpa:.2f}")
"""))

cells.append(code("""\
# Scenario: shift PMax + Prospecting budget to Brand + Non-Brand Search
# Assumption: Brand/Non-Brand maintain current ROAS at incremental spend.
# This is conservative (brand search ROAS often holds well at moderate increments).

pmax_spend = camp_funnel[camp_funnel["campaign"] == "Performance Max"]["cost"].values[0]
prosp_spend= camp_funnel[camp_funnel["campaign"] == "Prospecting"]["cost"].values[0]
reallocated_budget = pmax_spend * 0.40 + prosp_spend * 0.40  # Shift 40% of each

brand_roas   = camp_funnel[camp_funnel["campaign"] == "Brand Search"]["roas"].values[0]
nonbrand_roas= camp_funnel[camp_funnel["campaign"] == "Non-Brand Search"]["roas"].values[0]
avg_search_roas = (brand_roas + nonbrand_roas) / 2

incremental_revenue = reallocated_budget * avg_search_roas
lost_revenue_pmax   = pmax_spend * 0.40 * camp_funnel[camp_funnel["campaign"] == "Performance Max"]["roas"].values[0]
lost_revenue_prosp  = prosp_spend * 0.40 * camp_funnel[camp_funnel["campaign"] == "Prospecting"]["roas"].values[0]
net_revenue_gain    = incremental_revenue - lost_revenue_pmax - lost_revenue_prosp

print("=== Scenario A: Shift 40% of PMax + Prospecting budget to Search ===")
print(f"Budget reallocated:          ${reallocated_budget:,.0f}")
print(f"Incremental revenue (est.):  ${incremental_revenue:,.0f}")
print(f"Revenue given up:            ${lost_revenue_pmax + lost_revenue_prosp:,.0f}")
print(f"Net revenue gain (est.):     ${net_revenue_gain:,.0f}")
print(f"Annualized estimate:         ${net_revenue_gain * 3.04:,.0f}  (120d x 3.04)")
"""))

cells.append(code("""\
# Scenario B: PT geo expansion (3% -> 8% of spend)
pt_current_spend   = geo_df[geo_df["geo"] == "PT"]["cost"].values[0]
pt_current_roas    = geo_df[geo_df["geo"] == "PT"]["roas"].values[0]
pt_target_spend    = total_spend * 0.08  # Grow PT to 8% of budget
pt_incremental_spend = pt_target_spend - pt_current_spend
# Conservative: assume ROAS decreases 30% at scale
pt_incremental_roas  = pt_current_roas * 0.70
pt_incremental_rev   = pt_incremental_spend * pt_incremental_roas

print("=== Scenario B: Expand PT from 3% to 8% of total spend ===")
print(f"Current PT spend:              ${pt_current_spend:,.0f}")
print(f"Current PT ROAS:               {pt_current_roas:.2f}x")
print(f"Incremental PT spend:          ${pt_incremental_spend:,.0f}")
print(f"Conservative PT ROAS at scale: {pt_incremental_roas:.2f}x")
print(f"Incremental revenue (est.):    ${pt_incremental_rev:,.0f}")
print(f"Annualized estimate:           ${pt_incremental_rev * 3.04:,.0f}")
"""))

cells.append(code("""\
# Scenario C: Meta creative consolidation (pause c03-c06, scale c01+c02)
# Assume c01+c02 maintain ROAS when receiving c03-c06 budget
tail_spend  = meta_cr[~meta_cr["creative_id"].isin(["meta_c01","meta_c02"])]["cost"].sum()
winner_roas = meta_cr[meta_cr["creative_id"].isin(["meta_c01","meta_c02"])]["roas"].mean()
tail_roas   = meta_cr[~meta_cr["creative_id"].isin(["meta_c01","meta_c02"])]["roas"].mean()

incremental_rev_creative = tail_spend * (winner_roas * 0.85 - tail_roas)

print("=== Scenario C: Pause Meta c03-c06, reallocate to c01+c02 ===")
print(f"Budget freed from tail creatives:  ${tail_spend:,.0f}")
print(f"Winner ROAS (conservative, -15%):  {winner_roas * 0.85:.2f}x")
print(f"Tail creative ROAS (replaced):     {tail_roas:.2f}x")
print(f"Incremental revenue (est.):        ${incremental_rev_creative:,.0f}")
print(f"Annualized estimate:               ${incremental_rev_creative * 3.04:,.0f}")
"""))

cells.append(code("""\
total_annual_upside = (net_revenue_gain + pt_incremental_rev + incremental_rev_creative) * 3.04

print("=== Combined Annual Revenue Upside Estimate ===")
print(f"Scenario A (Search reallocation):  ${net_revenue_gain * 3.04:,.0f}")
print(f"Scenario B (PT expansion):         ${pt_incremental_rev * 3.04:,.0f}")
print(f"Scenario C (Creative consolidation): ${incremental_rev_creative * 3.04:,.0f}")
print(f"----------------------------------------------")
print(f"Total annual upside estimate:      ${total_annual_upside:,.0f}")
print()
print("These are directional estimates, not guarantees.")
print("Each scenario should be validated with a controlled test before full rollout.")
"""))

cells.append(md("""## Summary

The audit found five structural problems in the Marble & Co paid media account,
all diagnosable from the raw data:

1. **Optimization mismatch.** PMax and Meta Prospecting are optimized for
   add-to-cart, not purchase. Their ATC rates look great on platform dashboards,
   but purchase ROAS is 0.9x to 1.5x. Switching bid strategies to purchase
   targets is the highest-priority fix.

2. **Tracking break.** A tracking issue before 2024-03-01 caused 35-45% of
   purchases to appear as Direct/Unattributed. The fix on that date created a
   step-change in attributed metrics that looks like a performance jump but is
   purely a measurement improvement. Historical comparisons crossing this date
   must apply the gap correction.

3. **Geo opportunity.** Portugal has nearly 2x the network CTR and strong
   purchase ROAS on 3% of spend. A geo expansion test targeting 8% spend
   allocation is low-risk and high-potential.

4. **Price event.** The 12% AOV increase on 2024-03-16 caused a predictable
   CVR dip that resolved in two weeks. This is mechanical, not a media problem.
   Track AOV as a first-class KPI to avoid future misdiagnosis.

5. **Creative concentration.** Two Meta creatives drive 73% of purchases.
   The remaining four are burning ~44% of Meta budget at below-average ROAS.
   Pause the tail and scale the winners.

**Conservative annual revenue upside across all three actionable scenarios:**
see Scenario output above. The largest lever is fixing bid strategy optimization,
followed by creative consolidation.

*All figures are based on synthetic data generated to mirror real account patterns.*
*Contact for a live version of this audit on your actual paid media data.*
"""))


# Write the notebook
nb = nbformat.v4.new_notebook()
nb.cells = cells
nb.metadata["kernelspec"] = {
    "display_name": "Python 3",
    "language": "python",
    "name": "python3",
}
nb.metadata["language_info"] = {
    "name": "python",
    "version": "3.11.0",
}

out_path = HERE / "diagnosis.ipynb"
with open(out_path, "w") as f:
    nbformat.write(nb, f)

print(f"Notebook written to {out_path}")
