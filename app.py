from __future__ import annotations

from pathlib import Path
import io
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Nassau Candy | Profitability Dashboard",
    page_icon="🍬",
    layout="wide",
)

REQUIRED_COLUMNS = {
    "Order Date", "Order ID", "Division", "Product ID", "Product Name",
    "Sales", "Units", "Gross Profit", "Cost"
}
MONEY_COLUMNS = ["Sales", "Gross Profit", "Cost"]


@st.cache_data(show_spinner=False)
def load_data(file_bytes: bytes | None, default_path: str) -> pd.DataFrame:
    """Load the CSV and create row-level analytical fields."""
    if file_bytes is not None:
        df = pd.read_csv(io.BytesIO(file_bytes))
    else:
        df = pd.read_csv(default_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError("Required columns missing: " + ", ".join(sorted(missing)))

    for col in MONEY_COLUMNS + ["Units"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["Order Date", "Ship Date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    for col in ["Division", "Product Name", "Product ID"]:
        df[col] = df[col].astype("string").str.strip()

    # Row-level gross margin. Aggregated margins are recalculated from totals below.
    df["Gross Margin (%)"] = np.where(
        df["Sales"].ne(0), df["Gross Profit"] / df["Sales"] * 100, np.nan
    )
    df["Profit per Unit"] = np.where(
        df["Units"].ne(0), df["Gross Profit"] / df["Units"], np.nan
    )
    if "Ship Date" in df.columns:
        df["Ship Lag (days)"] = (df["Ship Date"] - df["Order Date"]).dt.days
    return df


def money(value: float) -> str:
    return f"${value:,.2f}"


def safe_percent(numerator: pd.Series | float, denominator: float) -> pd.Series | float:
    if denominator == 0:
        if isinstance(numerator, pd.Series):
            return pd.Series(np.nan, index=numerator.index)
        return np.nan
    return numerator / denominator * 100


def make_product_summary(data: pd.DataFrame) -> pd.DataFrame:
    products = (
        data.groupby(["Product ID", "Product Name", "Division"], dropna=False)
        .agg(
            Sales=("Sales", "sum"),
            Gross_Profit=("Gross Profit", "sum"),
            Cost=("Cost", "sum"),
            Units=("Units", "sum"),
            Order_Count=("Order ID", "nunique"),
            Transaction_Rows=("Product Name", "size"),
        )
        .reset_index()
    )
    products["Gross Margin (%)"] = np.where(
        products["Sales"].ne(0),
        products["Gross_Profit"] / products["Sales"] * 100,
        np.nan,
    )
    products["Profit per Unit"] = np.where(
        products["Units"].ne(0),
        products["Gross_Profit"] / products["Units"],
        np.nan,
    )
    products["Profit Contribution (%)"] = safe_percent(
        products["Gross_Profit"], products["Gross_Profit"].sum()
    )
    products["Sales Contribution (%)"] = safe_percent(
        products["Sales"], products["Sales"].sum()
    )
    products["Margin Risk"] = np.select(
        [
            products["Gross Margin (%)"].isna(),
            products["Gross Margin (%)"] < 0,
            products["Gross Margin (%)"] < 30,
            products["Gross Margin (%)"] < 50,
        ],
        ["Check data", "Negative profit", "High risk: <30%", "Review: <50%"],
        default="Healthy by threshold",
    )
    return products


def make_division_summary(data: pd.DataFrame) -> pd.DataFrame:
    divisions = (
        data.groupby("Division", dropna=False)
        .agg(
            Sales=("Sales", "sum"),
            Gross_Profit=("Gross Profit", "sum"),
            Cost=("Cost", "sum"),
            Units=("Units", "sum"),
            Products=("Product ID", "nunique"),
            Orders=("Order ID", "nunique"),
        )
        .reset_index()
    )
    divisions["Gross Margin (%)"] = np.where(
        divisions["Sales"].ne(0),
        divisions["Gross_Profit"] / divisions["Sales"] * 100,
        np.nan,
    )
    divisions["Sales Share (%)"] = safe_percent(divisions["Sales"], divisions["Sales"].sum())
    divisions["Profit Share (%)"] = safe_percent(
        divisions["Gross_Profit"], divisions["Gross_Profit"].sum()
    )
    return divisions


st.title("🍬 Nassau Candy Distributor")
st.subheader("Product Line Profitability & Margin Performance")
st.caption("Interactive decision-support dashboard · Gross profit is not the same as net profit.")

with st.sidebar:
    st.header("Dashboard filters")
    uploaded_file = st.file_uploader("Upload a replacement CSV (optional)", type=["csv"])
    csv_path = Path(__file__).with_name("Nassau Candy Distributor.csv")
    try:
        raw = load_data(uploaded_file.getvalue() if uploaded_file else None, str(csv_path))
    except Exception as exc:
        st.error(f"Unable to load the dataset: {exc}")
        st.stop()

    min_order_date = raw["Order Date"].min()
    max_order_date = raw["Order Date"].max()
    if pd.notna(min_order_date) and pd.notna(max_order_date):
        date_range = st.date_input(
            "Order date range",
            value=(min_order_date.date(), max_order_date.date()),
            min_value=min_order_date.date(),
            max_value=max_order_date.date(),
        )
    else:
        date_range = None

    division_options = sorted(raw["Division"].dropna().astype(str).unique())
    selected_divisions = st.multiselect(
        "Division filter", division_options, default=division_options
    )
    margin_threshold = st.slider(
        "Margin risk threshold (%)", min_value=0, max_value=100, value=50, step=5,
        help="Products below this margin are flagged for investigation, not automatic removal.",
    )
    product_search = st.text_input(
        "Product search", placeholder="Search product name or ID..."
    )

filtered = raw[raw["Division"].astype(str).isin(selected_divisions)].copy()
if date_range and isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date = pd.Timestamp(date_range[0])
    end_date = pd.Timestamp(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    filtered = filtered[filtered["Order Date"].between(start_date, end_date)]

if product_search.strip():
    search = product_search.strip().casefold()
    match = (
        filtered["Product Name"].astype(str).str.casefold().str.contains(search, na=False)
        | filtered["Product ID"].astype(str).str.casefold().str.contains(search, na=False)
    )
    filtered = filtered[match]

if filtered.empty:
    st.warning("No rows match these filters. Try a wider date range or another division/product.")
    st.stop()

products = make_product_summary(filtered)
divisions = make_division_summary(filtered)
sales_total = filtered["Sales"].sum()
profit_total = filtered["Gross Profit"].sum()
cost_total = filtered["Cost"].sum()
units_total = filtered["Units"].sum()
overall_margin = profit_total / sales_total * 100 if sales_total else np.nan
product_display = products.rename(columns={"Gross_Profit": "Gross Profit"}).copy()
division_display = divisions.rename(columns={"Gross_Profit": "Gross Profit"}).copy()

tab_overview, tab_products, tab_divisions, tab_diagnostics, tab_concentration, tab_quality = st.tabs(
    [
        "Overview",
        "Product profitability",
        "Division performance",
        "Cost vs margin",
        "Profit concentration",
        "Data quality",
    ]
)

with tab_overview:
    st.markdown("### Performance at a glance")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Sales", money(sales_total))
    k2.metric("Gross profit", money(profit_total))
    k3.metric("Total cost", money(cost_total))
    k4.metric("Weighted gross margin", f"{overall_margin:.2f}%")
    k5.metric("Units sold", f"{units_total:,.0f}")

    left, right = st.columns(2)
    with left:
        fig = px.bar(
            division_display.sort_values("Sales", ascending=False),
            x="Division", y=["Sales", "Gross Profit"], barmode="group",
            title="Revenue vs gross profit by division",
        )
        st.plotly_chart(fig, use_container_width=True)
    with right:
        fig = px.bar(
            product_display.nlargest(10, "Gross Profit").sort_values("Gross Profit"),
            x="Gross Profit", y="Product Name", color="Gross Margin (%)",
            orientation="h", title="Top 10 products by gross profit",
            hover_data=["Sales", "Cost", "Profit Contribution (%)"],
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Key observations in the selected data")
    if not division_display.empty:
        top_sales_division = division_display.loc[division_display["Sales"].idxmax()]
        top_profit_division = division_display.loc[division_display["Gross Profit"].idxmax()]
        st.write(
            f"- **Largest division by sales:** {top_sales_division['Division']} "
            f"({money(top_sales_division['Sales'])})."
        )
        st.write(
            f"- **Largest division by gross profit:** {top_profit_division['Division']} "
            f"({money(top_profit_division['Gross Profit'])})."
        )
    st.caption(
        "All totals and charts respond to the date, division, and product search filters. "
        "Use the flags as review prompts; validate pricing, discounts, product mix, and data quality "
        "before making business decisions."
    )

with tab_products:
    st.markdown("### Product-level margin leaderboard")
    sort_choice = st.radio(
        "Rank products by", ["Gross profit", "Sales", "Gross margin"], horizontal=True
    )
    sort_column = {
        "Gross profit": "Gross Profit",
        "Sales": "Sales",
        "Gross margin": "Gross Margin (%)",
    }[sort_choice]
    leaderboard = product_display.sort_values(sort_column, ascending=False)
    st.dataframe(
        leaderboard[
            [
                "Product ID", "Product Name", "Division", "Sales", "Cost", "Gross Profit",
                "Gross Margin (%)", "Profit Contribution (%)", "Sales Contribution (%)",
                "Margin Risk",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        contribution = product_display.nlargest(15, "Gross Profit").sort_values("Gross Profit")
        fig = px.bar(
            contribution, x="Gross Profit", y="Product Name", color="Profit Contribution (%)",
            orientation="h", title="Gross profit contribution — top 15 products",
            hover_data=["Sales", "Gross Margin (%)", "Profit Contribution (%)"],
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.scatter(
            product_display, x="Sales", y="Gross Margin (%)", size="Gross Profit",
            color="Division", hover_name="Product Name",
            hover_data=["Cost", "Profit Contribution (%)"],
            title="Product sales vs gross margin",
        )
        fig.add_hline(y=margin_threshold, line_dash="dash", annotation_text="Selected risk threshold")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown(f"### Margin risk flags (below {margin_threshold}% gross margin)")
    risk_rows = product_display[
        (product_display["Gross Margin (%)"] < margin_threshold)
        | (product_display["Gross Margin (%)"] < 0)
    ].sort_values("Gross Margin (%)")
    if risk_rows.empty:
        st.success("No products fall below the selected threshold in the filtered data.")
    else:
        st.dataframe(
            risk_rows[
                ["Product ID", "Product Name", "Division", "Sales", "Cost", "Gross Profit",
                 "Gross Margin (%)", "Profit Contribution (%)", "Margin Risk"]
            ],
            use_container_width=True,
            hide_index=True,
        )
    st.caption(
        "A low margin alone does not prove a product should be discontinued. Consider volume, "
        "strategic importance, price elasticity, and data accuracy."
    )
    st.download_button(
        "Download product leaderboard CSV",
        product_display.to_csv(index=False).encode("utf-8"),
        "nassau_product_profitability.csv",
        "text/csv",
    )

with tab_divisions:
    st.markdown("### Division performance")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(
            division_display.sort_values("Sales", ascending=False),
            x="Division", y=["Sales", "Gross Profit"], barmode="group",
            title="Revenue vs gross profit",
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        # Distribution of row-level margins, not only the weighted aggregate margin.
        margin_rows = filtered.dropna(subset=["Gross Margin (%)"])
        fig = px.box(
            margin_rows, x="Division", y="Gross Margin (%)", color="Division",
            points="outliers", title="Transaction-level margin distribution by division",
        )
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(division_display, use_container_width=True, hide_index=True)
    st.caption(
        "The box plot shows the distribution of row-level margins. The table's division margin "
        "is calculated from total gross profit divided by total sales."
    )

with tab_diagnostics:
    st.markdown("### Cost vs margin diagnostics")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.scatter(
            filtered, x="Cost", y="Gross Profit", color="Division",
            size="Units", hover_name="Product Name",
            hover_data=["Sales", "Gross Margin (%)", "Order ID"],
            title="Cost vs gross profit by transaction row",
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        fig = px.scatter(
            filtered, x="Sales", y="Gross Margin (%)", color="Division",
            size="Cost", hover_name="Product Name",
            hover_data=["Cost", "Gross Profit", "Units"],
            title="Sales vs margin diagnostics",
        )
        fig.add_hline(y=margin_threshold, line_dash="dash", annotation_text="Margin threshold")
        st.plotly_chart(fig, use_container_width=True)

    diagnostics = filtered.copy()
    diagnostics["Diagnostic Flag"] = np.select(
        [
            diagnostics["Sales"].isna() | diagnostics["Cost"].isna() | diagnostics["Gross Profit"].isna(),
            diagnostics["Sales"].le(0),
            diagnostics["Gross Margin (%)"].lt(0),
            diagnostics["Gross Margin (%)"].lt(margin_threshold),
            (diagnostics["Sales"] - diagnostics["Cost"] - diagnostics["Gross Profit"]).abs().gt(0.011),
        ],
        [
            "Missing financial value",
            "Zero/negative sales",
            "Negative gross margin",
            "Below selected margin threshold",
            "Sales-cost-profit mismatch",
        ],
        default="No rule-based flag",
    )
    st.markdown("### Rows requiring review")
    flagged_rows = diagnostics[diagnostics["Diagnostic Flag"] != "No rule-based flag"].copy()
    st.dataframe(
        flagged_rows[
            ["Order ID", "Product ID", "Product Name", "Division", "Sales", "Cost",
             "Gross Profit", "Gross Margin (%)", "Diagnostic Flag"]
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "These are rule-based diagnostics, not proof of an accounting error. A row may meet more "
        "than one rule; the displayed flag is the first matching rule in the code."
    )

with tab_concentration:
    st.markdown("### Profit concentration and dependency indicators")
    c1, c2 = st.columns(2)
    with c1:
        pareto_profit = product_display.sort_values("Gross Profit", ascending=False).copy()
        total_profit_for_share = pareto_profit["Gross Profit"].sum()
        pareto_profit["Cumulative Profit Share (%)"] = (
            pareto_profit["Gross Profit"].cumsum() / total_profit_for_share * 100
            if total_profit_for_share else np.nan
        )
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=pareto_profit["Product Name"],
                y=pareto_profit["Gross Profit"],
                name="Gross profit",
                yaxis="y",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=pareto_profit["Product Name"],
                y=pareto_profit["Cumulative Profit Share (%)"],
                name="Cumulative profit share",
                yaxis="y2",
                mode="lines+markers",
            )
        )
        fig.add_hline(y=80, line_dash="dash", annotation_text="80% cumulative share", yref="y2")
        fig.update_layout(
            title="Profit Pareto: product contribution",
            xaxis_title="Products ranked by gross profit",
            yaxis=dict(title="Gross profit ($)"),
            yaxis2=dict(title="Cumulative profit share (%)", overlaying="y", side="right", range=[0, 100]),
            legend=dict(orientation="h"),
        )
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        pareto_sales = product_display.sort_values("Sales", ascending=False).copy()
        pareto_sales["Cumulative Sales Share (%)"] = (
            pareto_sales["Sales"].cumsum() / pareto_sales["Sales"].sum() * 100
            if pareto_sales["Sales"].sum() else np.nan
        )
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=list(range(1, len(pareto_sales) + 1)),
                y=pareto_sales["Cumulative Sales Share (%)"],
                mode="lines",
                name="Cumulative sales share",
            )
        )
        fig.add_hline(y=80, line_dash="dash", annotation_text="80% of sales")
        fig.update_layout(
            title="Revenue Pareto curve",
            xaxis_title="Products ranked by sales",
            yaxis_title="Cumulative sales share (%)",
            yaxis=dict(range=[0, 100]),
        )
        st.plotly_chart(fig, use_container_width=True)

    if len(pareto_sales) and pareto_sales["Sales"].sum() != 0:
        products_to_80 = int((pareto_sales["Cumulative Sales Share (%)"] < 80).sum() + 1)
        top5_sales_share = pareto_sales.head(5)["Sales"].sum() / pareto_sales["Sales"].sum() * 100
        top5_profit_share = (
            product_display.nlargest(5, "Gross Profit")["Gross Profit"].sum() / profit_total * 100
            if profit_total else np.nan
        )
        p1, p2, p3 = st.columns(3)
        p1.metric("Products reaching 80% of sales", f"{products_to_80} / {len(pareto_sales)}")
        p2.metric("Top 5 sales dependency", f"{top5_sales_share:.1f}%")
        p3.metric("Top 5 gross-profit dependency", f"{top5_profit_share:.1f}%")
    st.caption(
        "Dependency indicators quantify concentration in this filtered dataset. High concentration "
        "may increase exposure if a leading product loses demand; it does not by itself imply poor performance."
    )
    st.download_button(
        "Download profit concentration table",
        pareto_profit.to_csv(index=False).encode("utf-8"),
        "nassau_profit_concentration.csv",
        "text/csv",
    )

with tab_quality:
    st.markdown("### Data quality checks")
    mismatch_count = int(
        ((filtered["Sales"] - filtered["Cost"] - filtered["Gross Profit"]).abs() > 0.011).sum()
    )
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Filtered rows", f"{len(filtered):,}")
    q2.metric("Missing cells", f"{int(filtered.isna().sum().sum()):,}")
    q3.metric("Duplicate rows", f"{int(filtered.duplicated().sum()):,}")
    q4.metric("Financial reconciliation flags", f"{mismatch_count:,}")

    quality_rows = [
        ("Missing order dates", int(filtered["Order Date"].isna().sum())),
        ("Missing product IDs", int(filtered["Product ID"].isna().sum())),
        ("Missing sales values", int(filtered["Sales"].isna().sum())),
        ("Sales-cost-profit mismatch", mismatch_count),
    ]
    if "Ship Date" in filtered.columns:
        quality_rows.extend([
            ("Missing ship dates", int(filtered["Ship Date"].isna().sum())),
            ("Ship date before order date", int((filtered["Ship Lag (days)"] < 0).sum())),
            ("Ship lag above 90 days", int((filtered["Ship Lag (days)"] > 90).sum())),
        ])
    st.dataframe(
        pd.DataFrame(quality_rows, columns=["Check", "Count"]),
        use_container_width=True,
        hide_index=True,
    )
    if "Ship Lag (days)" in filtered.columns and (filtered["Ship Lag (days)"] > 90).any():
        st.warning(
            "Some ship dates are more than 90 days after order dates. Verify the source date fields "
            "before using shipping-performance metrics."
        )
    missingness = (
        filtered.isna().sum().rename("Missing values").reset_index()
        .rename(columns={"index": "Column"})
    )
    st.dataframe(missingness, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered dataset",
        filtered.to_csv(index=False).encode("utf-8"),
        "nassau_filtered_data.csv",
        "text/csv",
    )

st.divider()
st.caption(
    "Definitions: Gross margin = gross profit ÷ sales. Weighted margin is total gross profit ÷ "
    "total sales. Flags support investigation; they do not automatically prescribe price changes "
    "or product discontinuation."
)
