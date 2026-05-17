"""
app.py: Marble & Co Paid Media Attribution Audit Dashboard

Loads pre-built fact tables from data/output/ and presents a stakeholder-facing
view of channel, geo, and creative performance with attribution-gap correction.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(
    page_title="Paid Media Attribution Audit | Marble & Co",
    page_icon="📊",
    layout="wide",
)

ROOT = Path(__file__).parent
OUTPUT = ROOT / "data" / "output"
SAMPLE = ROOT / "data" / "sample"

TRACKING_FIX_DATE = pd.Timestamp("2024-03-01")
PRICE_EVENT_DATE  = pd.Timestamp("2024-03-16")
PRE_FIX_GAP       = 0.40   # Average attribution gap before the tracking fix

CHANNEL_COLORS = {
    "Brand Search":     "#1a56db",
    "Non-Brand Search": "#7e3af2",
    "Shopping":         "#0694a2",
    "Performance Max":  "#e3a008",
    "Prospecting":      "#ff5a1f",
    "Retargeting":      "#31c48d",
    "Direct":           "#9ca3af",
}

# ---- Data loading ----

@st.cache_data
def load_tables():
    ch  = pd.read_csv(OUTPUT / "fct_channel_performance.csv")
    geo = pd.read_csv(OUTPUT / "fct_geo_performance.csv")
    cr  = pd.read_csv(OUTPUT / "fct_creative_performance.csv")
    stg = pd.read_csv(OUTPUT / "stg_events.csv", parse_dates=["date"])
    return ch, geo, cr, stg


@st.cache_data
def load_raw():
    spend  = pd.read_csv(SAMPLE / "spend.csv", parse_dates=["date"])
    events = pd.read_csv(SAMPLE / "events.csv", parse_dates=["date"])
    email  = pd.read_csv(SAMPLE / "email.csv", parse_dates=["date"])
    return spend, events, email


ch_df, geo_df, cr_df, stg_df = load_tables()
spend_raw, events_raw, email_raw = load_raw()

# ---- Sidebar filters ----

st.sidebar.title("Filters")

date_min = stg_df["date"].min().date()
date_max = stg_df["date"].max().date()

date_range = st.sidebar.date_input(
    "Date range",
    value=(date_min, date_max),
    min_value=date_min,
    max_value=date_max,
)

revenue_view = st.sidebar.radio(
    "Revenue view",
    ["Attributed only", "Tracking-adjusted estimate"],
    help=(
        "Attributed only: revenue directly linked to a paid channel. "
        "Tracking-adjusted estimate: adds a modeled uplift for the ~40% of "
        "purchases that were untracked before the 2024-03-01 fix. "
        "The estimate is labeled clearly throughout."
    ),
)

adjusted = revenue_view == "Tracking-adjusted estimate"

# Apply date filter to stg and raw data
if len(date_range) == 2:
    d_start, d_end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
else:
    d_start, d_end = pd.Timestamp(date_min), pd.Timestamp(date_max)

stg_filtered = stg_df[(stg_df["date"] >= d_start) & (stg_df["date"] <= d_end)]

# ---- KPI computation ----

attributed_stg = stg_filtered[stg_filtered["attribution_type"] == "attributed"]
direct_stg     = stg_filtered[stg_filtered["attribution_type"] == "unattributed"]

total_spend        = attributed_stg["cost"].sum()
attributed_revenue = attributed_stg["revenue"].sum()
attributed_purch   = attributed_stg["purchase"].sum()
direct_purch       = direct_stg["purchase"].sum()
total_purch_true   = attributed_purch + direct_purch

if adjusted:
    # Uplift for pre-fix period only
    pre_fix_attr = attributed_stg[attributed_stg["date"] < TRACKING_FIX_DATE]
    post_fix_attr = attributed_stg[attributed_stg["date"] >= TRACKING_FIX_DATE]
    pre_fix_rev = pre_fix_attr["revenue"].sum() / (1 - PRE_FIX_GAP)
    post_fix_rev = post_fix_attr["revenue"].sum()
    display_revenue = pre_fix_rev + post_fix_rev

    pre_fix_purch = pre_fix_attr["purchase"].sum() / (1 - PRE_FIX_GAP)
    post_fix_purch = post_fix_attr["purchase"].sum()
    display_purch = int(pre_fix_purch + post_fix_purch)
else:
    display_revenue = attributed_revenue
    display_purch   = int(attributed_purch)

blended_roas = display_revenue / total_spend if total_spend > 0 else 0
cac          = total_spend / display_purch if display_purch > 0 else 0

# ---- Header ----

st.title("Paid Media Attribution Audit")
st.caption(
    f"Marble & Co | DTC Luxury Homegoods | "
    f"{d_start.strftime('%b %d, %Y')} to {d_end.strftime('%b %d, %Y')}"
)

if adjusted:
    st.info(
        "Tracking-adjusted estimate is active. Revenue and purchases for dates "
        "before 2024-03-01 are inflated by 1/(1-0.40) to model the ~40% "
        "attribution gap. This is a modeled estimate, not measured fact.",
        icon=":material/info:",
    )

# ---- KPI tiles ----

kpi_cols = st.columns(6)
kpi_data = [
    ("Total Spend",       f"${total_spend:,.0f}",      None),
    ("Revenue",           f"${display_revenue:,.0f}",   "Estimated" if adjusted else "Attributed"),
    ("Blended ROAS",      f"{blended_roas:.2f}x",       None),
    ("Cost per Purchase", f"${cac:.2f}",                None),
    ("Purchases",         f"{display_purch:,}",         "Estimated" if adjusted else "Attributed"),
    ("Unattributed (raw)", f"{int(direct_purch):,}",   "All dates"),
]
for col, (label, value, note) in zip(kpi_cols, kpi_data):
    with col:
        st.metric(label, value, delta=note)

st.divider()

# ---- Tabs ----

tab_channel, tab_geo, tab_creative, tab_timeseries = st.tabs([
    "Channel Performance",
    "Geo Analysis",
    "Creative Scorecard",
    "Time Series",
])


# ---- Channel performance ----

with tab_channel:
    st.subheader("Channel and Campaign Performance")
    st.caption(
        "Performance Max and Meta Prospecting show high add-to-cart volume "
        "but the worst purchase ROAS. Brand Search and Non-Brand Search deliver "
        "far stronger returns on actual purchases."
    )

    ch_attr = ch_df[ch_df["attribution_type"] == "attributed"].copy()
    ch_attr = ch_attr.sort_values("roas", ascending=False)

    # Side-by-side: ATC rate vs ROAS bar chart
    fig_ch = go.Figure()

    fig_ch.add_trace(go.Bar(
        name="ROAS (purchases)",
        x=ch_attr["campaign"],
        y=ch_attr["roas"],
        marker_color=[CHANNEL_COLORS.get(c, "#6b7280") for c in ch_attr["campaign"]],
        yaxis="y1",
    ))
    fig_ch.add_trace(go.Scatter(
        name="ATC rate (sessions -> cart)",
        x=ch_attr["campaign"],
        y=ch_attr["atc_rate"],
        mode="lines+markers",
        marker=dict(size=10, color="#ef4444"),
        yaxis="y2",
    ))

    fig_ch.update_layout(
        yaxis=dict(title="ROAS (purchase-based)", side="left"),
        yaxis2=dict(title="ATC rate", side="right", overlaying="y", showgrid=False),
        legend=dict(orientation="h", y=1.12),
        height=420,
        margin=dict(t=40),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_ch, use_container_width=True)

    # Table
    display_cols = {
        "campaign":            "Campaign",
        "total_cost":          "Spend ($)",
        "total_revenue":       "Revenue ($)",
        "roas":                "ROAS",
        "total_atc":           "Add to Cart",
        "total_purchases":     "Purchases",
        "atc_rate":            "ATC Rate",
        "atc_to_purchase_rate":"ATC -> Purchase",
        "cpa":                 "CPA ($)",
    }
    ch_show = ch_attr[list(display_cols.keys())].rename(columns=display_cols)
    ch_show["Spend ($)"]   = ch_show["Spend ($)"].map("${:,.0f}".format)
    ch_show["Revenue ($)"] = ch_show["Revenue ($)"].map("${:,.0f}".format)
    ch_show["CPA ($)"]     = ch_show["CPA ($)"].map("${:,.2f}".format)
    ch_show["ATC Rate"]    = ch_show["ATC Rate"].map("{:.1%}".format)
    ch_show["ATC -> Purchase"] = ch_show["ATC -> Purchase"].map("{:.1%}".format)

    def highlight_mismatch(row):
        if row["Campaign"] in ("Performance Max", "Prospecting"):
            return ["background-color: #B45309; color: white"] * len(row)
        return [""] * len(row)

    st.dataframe(
        ch_show.style.apply(highlight_mismatch, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Highlighted rows (yellow): campaigns optimized for add-to-cart, "
        "not purchase. High ATC rate does not translate to purchase ROAS."
    )


# ---- Geo analysis ----

with tab_geo:
    st.subheader("Geo Performance")
    st.caption(
        "PT (Portugal) has the highest CTR and ROAS in the account "
        "but receives only 3% of total spend. It is the clearest budget "
        "reallocation opportunity."
    )

    geo_df_sorted = geo_df.sort_values("roas", ascending=False)

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        fig_ctr = px.bar(
            geo_df_sorted,
            x="geo",
            y="blended_ctr",
            color="geo",
            title="CTR by Country",
            labels={"blended_ctr": "Blended CTR", "geo": "Country"},
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig_ctr.update_layout(showlegend=False, height=350, margin=dict(t=50))
        fig_ctr.update_yaxes(tickformat=".2%")
        st.plotly_chart(fig_ctr, use_container_width=True)

    with col_g2:
        fig_roas = px.bar(
            geo_df_sorted,
            x="geo",
            y="roas",
            color="geo",
            title="ROAS by Country",
            labels={"roas": "ROAS", "geo": "Country"},
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig_roas.update_layout(showlegend=False, height=350, margin=dict(t=50))
        st.plotly_chart(fig_roas, use_container_width=True)

    # Spend share vs revenue share bubble chart
    fig_bubble = px.scatter(
        geo_df_sorted,
        x="spend_share",
        y="revenue_share",
        size="total_cost",
        color="geo",
        text="geo",
        title="Spend Share vs Revenue Share (bubble = total spend)",
        labels={
            "spend_share": "Spend Share",
            "revenue_share": "Revenue Share",
            "geo": "Country",
        },
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig_bubble.add_shape(
        type="line", x0=0, y0=0, x1=1, y1=1,
        line=dict(color="gray", dash="dash"),
    )
    fig_bubble.update_traces(textposition="top center")
    fig_bubble.update_layout(height=400, margin=dict(t=50))
    fig_bubble.update_xaxes(tickformat=".1%")
    fig_bubble.update_yaxes(tickformat=".1%")
    st.plotly_chart(fig_bubble, use_container_width=True)
    st.caption(
        "Countries above the diagonal generate more revenue share than their spend share. "
        "PT is the standout: strong ROAS on minimal investment."
    )

    geo_show = geo_df_sorted[[
        "geo", "total_cost", "total_revenue", "roas", "blended_ctr",
        "cpa", "spend_share", "revenue_share",
    ]].rename(columns={
        "geo": "Country", "total_cost": "Spend ($)", "total_revenue": "Revenue ($)",
        "roas": "ROAS", "blended_ctr": "CTR", "cpa": "CPA ($)",
        "spend_share": "Spend Share", "revenue_share": "Revenue Share",
    })
    geo_show["Spend ($)"]    = geo_show["Spend ($)"].map("${:,.0f}".format)
    geo_show["Revenue ($)"]  = geo_show["Revenue ($)"].map("${:,.0f}".format)
    geo_show["CPA ($)"]      = geo_show["CPA ($)"].map("${:,.2f}".format)
    geo_show["CTR"]          = geo_show["CTR"].map("{:.2%}".format)
    geo_show["Spend Share"]  = geo_show["Spend Share"].map("{:.1%}".format)
    geo_show["Revenue Share"]= geo_show["Revenue Share"].map("{:.1%}".format)
    st.dataframe(geo_show, use_container_width=True, hide_index=True)


# ---- Creative scorecard ----

with tab_creative:
    st.subheader("Meta Creative Scorecard")
    st.caption(
        "Two creatives (meta_c01 and meta_c02) account for the majority of "
        "Meta purchases. The remaining four spend budget with weak return. "
        "Pausing the underperformers and scaling the winners is the fastest lever."
    )

    cr_df_sorted = cr_df.sort_values("purchase_contribution", ascending=False)

    # Purchase contribution waterfall
    fig_contrib = go.Figure()
    colors = ["#1a56db" if i < 2 else "#9ca3af" for i in range(len(cr_df_sorted))]

    fig_contrib.add_trace(go.Bar(
        x=cr_df_sorted["creative_id"],
        y=cr_df_sorted["purchase_contribution"],
        marker_color=colors,
        text=[f"{v:.1%}" for v in cr_df_sorted["purchase_contribution"]],
        textposition="outside",
        name="Purchase contribution",
    ))
    fig_contrib.update_layout(
        title="Purchase Contribution by Meta Creative",
        yaxis=dict(title="Share of Meta Purchases", tickformat=".0%"),
        height=400,
        margin=dict(t=50),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_contrib, use_container_width=True)

    # Spend vs purchases scatter
    fig_eff = px.scatter(
        cr_df_sorted,
        x="spend_share",
        y="purchase_contribution",
        size="total_cost",
        color="creative_id",
        text="creative_id",
        title="Spend Share vs Purchase Contribution (bubble = total spend)",
        labels={
            "spend_share": "Spend Share within Meta",
            "purchase_contribution": "Purchase Contribution",
        },
    )
    fig_eff.add_shape(
        type="line", x0=0, y0=0, x1=1, y1=1,
        line=dict(color="gray", dash="dash"),
    )
    fig_eff.update_traces(textposition="top center")
    fig_eff.update_layout(height=380, margin=dict(t=50))
    fig_eff.update_xaxes(tickformat=".1%")
    fig_eff.update_yaxes(tickformat=".1%")
    st.plotly_chart(fig_eff, use_container_width=True)
    st.caption(
        "Creatives above the diagonal punch above their spend weight. "
        "meta_c01 and meta_c02 are clear winners. "
        "meta_c03 through meta_c06 are below the diagonal."
    )

    cr_show = cr_df_sorted[[
        "creative_id", "total_cost", "total_revenue", "roas",
        "total_purchases", "cpa", "spend_share", "purchase_contribution",
    ]].rename(columns={
        "creative_id": "Creative", "total_cost": "Spend ($)",
        "total_revenue": "Revenue ($)", "roas": "ROAS",
        "total_purchases": "Purchases", "cpa": "CPA ($)",
        "spend_share": "Spend Share", "purchase_contribution": "Purchase %",
    })
    cr_show["Spend ($)"]   = cr_show["Spend ($)"].map("${:,.0f}".format)
    cr_show["Revenue ($)"] = cr_show["Revenue ($)"].map("${:,.0f}".format)
    cr_show["CPA ($)"]     = cr_show["CPA ($)"].map("${:,.2f}".format)
    cr_show["Spend Share"] = cr_show["Spend Share"].map("{:.1%}".format)
    cr_show["Purchase %"]  = cr_show["Purchase %"].map("{:.1%}".format)
    st.dataframe(cr_show, use_container_width=True, hide_index=True)


# ---- Time series ----

with tab_timeseries:
    st.subheader("Daily Performance Over Time")
    st.caption(
        "Two events are annotated: the 2024-03-01 tracking fix (the jump in "
        "attributed purchases is a measurement change, not real growth) and "
        "the 2024-03-16 price increase (explains the brief conversion rate dip)."
    )

    # Daily rollup
    daily = (
        stg_df[stg_df["date"].between(d_start, d_end)]
        .groupby(["date", "attribution_type"])
        .agg(
            cost=("cost", "sum"),
            revenue=("revenue", "sum"),
            purchase=("purchase", "sum"),
        )
        .reset_index()
    )

    daily_attr   = daily[daily["attribution_type"] == "attributed"]
    daily_direct = daily[daily["attribution_type"] == "unattributed"]

    daily_attr = daily_attr.set_index("date").sort_index()

    if adjusted:
        pre_mask = daily_attr.index < TRACKING_FIX_DATE
        daily_attr["revenue"]  = daily_attr["revenue"].astype(float)
        daily_attr["purchase"] = daily_attr["purchase"].astype(float)
        daily_attr.loc[pre_mask, "revenue"]  /= (1 - PRE_FIX_GAP)
        daily_attr.loc[pre_mask, "purchase"] /= (1 - PRE_FIX_GAP)

    # Revenue time series
    fig_rev = go.Figure()
    fig_rev.add_trace(go.Scatter(
        x=daily_attr.index, y=daily_attr["revenue"],
        name="Attributed Revenue" + (" (adjusted)" if adjusted else ""),
        fill="tozeroy", line=dict(color="#1a56db"),
    ))

    # Annotations
    in_range = lambda d: d_start <= d <= d_end

    if in_range(TRACKING_FIX_DATE):
        fig_rev.add_vline(x=TRACKING_FIX_DATE, line_dash="dash", line_color="#ef4444")
        fig_rev.add_annotation(
            x=TRACKING_FIX_DATE, xref="x", y=1.0, yref="paper",
            yanchor="bottom", showarrow=False,
            text="Tracking fix (2024-03-01)", font=dict(size=12),
            bgcolor="rgba(255,255,255,0.6)",
        )
    if in_range(PRICE_EVENT_DATE):
        fig_rev.add_vline(x=PRICE_EVENT_DATE, line_dash="dot", line_color="#f59e0b")
        fig_rev.add_annotation(
            x=PRICE_EVENT_DATE, xref="x", y=1.0, yref="paper",
            yanchor="bottom", showarrow=False,
            text="Price increase (2024-03-16)", font=dict(size=12),
            bgcolor="rgba(255,255,255,0.6)",
        )

    fig_rev.update_layout(
        title="Daily Attributed Revenue",
        yaxis_title="Revenue ($)",
        height=350,
        margin=dict(t=50),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.12),
    )
    st.plotly_chart(fig_rev, use_container_width=True)

    # Attributed vs unattributed purchases
    daily_direct_idx = daily_direct.set_index("date").sort_index()

    fig_purch = go.Figure()
    fig_purch.add_trace(go.Bar(
        x=daily_attr.index, y=daily_attr["purchase"],
        name="Attributed", marker_color="#1a56db",
    ))
    fig_purch.add_trace(go.Bar(
        x=daily_direct_idx.index, y=daily_direct_idx["purchase"],
        name="Unattributed (Direct)", marker_color="#ef4444",
    ))
    fig_purch.update_layout(
        barmode="stack",
        title="Daily Purchases: Attributed vs Unattributed",
        yaxis_title="Purchases",
        height=350,
        margin=dict(t=50),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.12),
    )
    if in_range(TRACKING_FIX_DATE):
        fig_purch.add_vline(x=TRACKING_FIX_DATE, line_dash="dash", line_color="#ef4444")
        fig_purch.add_annotation(
            x=TRACKING_FIX_DATE, xref="x", y=1.0, yref="paper",
            yanchor="bottom", showarrow=False,
            text="Tracking fix", font=dict(size=12),
            bgcolor="rgba(255,255,255,0.6)",
        )
    st.plotly_chart(fig_purch, use_container_width=True)
    st.warning(
        "The jump in attributed purchases around 2024-03-01 is a measurement "
        "artifact: the tracking fix recovered purchases that were previously "
        "falling into the unattributed bucket. Total purchases (attributed + "
        "unattributed, stacked above) remained stable. Do not interpret the "
        "spike as organic demand growth."
    )

    # Spend over time by channel
    spend_daily = (
        spend_raw[spend_raw["date"].between(d_start, d_end)]
        .groupby(["date", "campaign"])["cost"]
        .sum()
        .reset_index()
    )
    fig_spend = px.area(
        spend_daily,
        x="date",
        y="cost",
        color="campaign",
        title="Daily Spend by Campaign",
        labels={"cost": "Spend ($)", "campaign": "Campaign"},
        color_discrete_map=CHANNEL_COLORS,
    )
    fig_spend.update_layout(height=350, margin=dict(t=50))
    st.plotly_chart(fig_spend, use_container_width=True)

st.divider()
st.caption(
    "Data is synthetic. Methodology mirrors a real paid media attribution audit. "
    "Built with DuckDB, Plotly, and Streamlit. "
    "Source: github.com/[your-handle]/paid-media-attribution-audit"
)
