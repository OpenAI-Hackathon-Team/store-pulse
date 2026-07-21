"""Store Pulse retail analytics dashboard.

Run with: streamlit run app.py
"""

import os

import altair as alt
import pandas as pd
import streamlit as st
from ai_insights import DEFAULT_MODEL, DEMO_MODE, answer_question, build_data_summary, generate_summary
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


st.set_page_config(
    page_title="Store Pulse",
    page_icon=":material/monitoring:",
    layout="wide",
)


@st.cache_resource
def get_engine():
    """Build the database connection from the project's .env configuration."""

    load_dotenv()
    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        database=os.environ["DB_NAME"],
    )
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=300, show_spinner="Loading sales data…")
def load_sales_data():
    """Load the dashboard fields; refresh the cache every five minutes."""

    query = text("""
        SELECT store, dept, date, weekly_sales, isholiday, type, size,
               temperature, fuel_price, markdown1, markdown2, markdown3,
               markdown4, markdown5, cpi, unemployment
        FROM clean_sales
    """)
    with get_engine().connect() as connection:
        data = pd.read_sql(query, connection)

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["weekly_sales"] = pd.to_numeric(data["weekly_sales"], errors="coerce")
    for column in ["temperature", "fuel_price", "cpi", "unemployment"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def currency(value: float) -> str:
    return f"${value:,.0f}"


def build_filters(data: pd.DataFrame) -> pd.DataFrame:
    """Render sidebar controls and return the selected data slice."""

    sales = data.dropna(subset=["weekly_sales"]).copy()
    if sales.empty:
        return sales

    with st.sidebar:
        st.title("Store Pulse")
        st.caption("Retail sales intelligence")
        st.subheader("Filters")

        date_min, date_max = sales["date"].min().date(), sales["date"].max().date()
        selected_dates = st.date_input(
            "Date range",
            value=(date_min, date_max),
            min_value=date_min,
            max_value=date_max,
        )
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
            start_date, end_date = pd.Timestamp(selected_dates[0]), pd.Timestamp(selected_dates[1])
            sales = sales[sales["date"].between(start_date, end_date)]

        stores = sorted(sales["store"].dropna().unique().tolist())
        selected_stores = st.multiselect("Stores", stores, default=stores)
        if selected_stores:
            sales = sales[sales["store"].isin(selected_stores)]
        else:
            sales = sales.iloc[0:0]

        departments = sorted(sales["dept"].dropna().unique().tolist())
        selected_departments = st.multiselect("Departments", departments, default=departments)
        if selected_departments:
            sales = sales[sales["dept"].isin(selected_departments)]
        else:
            sales = sales.iloc[0:0]

        holiday_only = st.toggle("Holiday weeks only")
        if holiday_only:
            sales = sales[sales["isholiday"].fillna(False)]

        st.caption("Filters apply to every KPI and chart.")
    return sales


def show_dashboard(data: pd.DataFrame) -> None:
    sales = build_filters(data)
    if sales.empty:
        st.warning("No sales records match the selected filters.")
        return

    total_sales = sales["weekly_sales"].sum()
    sales_rows = len(sales)
    weekly_sales = sales.groupby("date", as_index=False)["weekly_sales"].sum()
    average_weekly_sales = weekly_sales["weekly_sales"].mean()
    active_stores = sales["store"].nunique()

    with st.container(horizontal=True, horizontal_alignment="distribute"):
        st.title("Sales performance")
        st.badge("Live database view", icon=":material/database:", color="blue")
    st.caption(
        f"{sales['date'].min():%b %d, %Y} – {sales['date'].max():%b %d, %Y}  ·  "
        "Updated from `clean_sales`"
    )

    overview_tab, stores_tab, departments_tab, trends_tab, ask_tab = st.tabs(
        ["Overview", "Store Performance", "Department Performance", "Trends & External Factors", "Ask Store Pulse"]
    )

    with overview_tab:
        with st.container(horizontal=True):
            st.metric("Total sales", currency(total_sales), border=True)
            st.metric("Average weekly sales", currency(average_weekly_sales), border=True)
            st.metric("Active stores", f"{active_stores:,}", border=True)
            st.metric("Sales records", f"{sales_rows:,}", border=True)

        time_chart = (
            alt.Chart(weekly_sales)
            .mark_area(
                line={"color": "#60A5FA"},
                color=alt.Gradient(
                    gradient="linear",
                    stops=[alt.GradientStop(color="#60A5FA", offset=0), alt.GradientStop(color="#0F172A", offset=1)],
                    x1=1,
                    x2=1,
                    y1=1,
                    y2=0,
                ),
            )
            .encode(
                x=alt.X("date:T", title="Week"),
                y=alt.Y("weekly_sales:Q", title="Weekly sales", axis=alt.Axis(format="$,.0f")),
                tooltip=[alt.Tooltip("date:T", title="Week"), alt.Tooltip("weekly_sales:Q", title="Sales", format="$,.2f")],
            )
            .properties(height=330)
        )
        with st.container(border=True):
            st.subheader("Sales over time")
            st.caption("Weekly sales volume across the selected stores and departments")
            st.altair_chart(time_chart, width="stretch")

        with st.expander("View and export filtered records", icon=":material/table_chart:"):
            st.dataframe(
                sales.sort_values("date", ascending=False),
                width="stretch",
                height=360,
                hide_index=True,
            )
            st.download_button(
                "Download filtered data as CSV",
                data=sales.to_csv(index=False).encode("utf-8"),
                file_name="store_pulse_filtered_sales.csv",
                mime="text/csv",
            )

    type_colors = alt.Scale(
        domain=["A", "B", "C"],
        range=["#60A5FA", "#34D399", "#A78BFA"],
    )
    store_weekly_sales = sales.groupby(["store", "date"], as_index=False)["weekly_sales"].sum()
    store_details = sales.groupby("store", as_index=False).agg(type=("type", "first"), size=("size", "first"))
    store_scorecard = (
        store_weekly_sales.groupby("store", as_index=False)
        .agg(total_sales=("weekly_sales", "sum"), average_weekly_sales=("weekly_sales", "mean"))
        .merge(store_details, on="store", how="left")
        .sort_values("total_sales", ascending=False)
    )
    top_stores = store_scorecard.nlargest(10, "total_sales").sort_values("total_sales")

    with stores_tab:
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.subheader("Top stores")
                st.caption("Top 10 by total sales, colored by store type")
                top_stores_chart = alt.Chart(top_stores).mark_bar().encode(
                    x=alt.X("total_sales:Q", title="Total sales", axis=alt.Axis(format="$,.0f")),
                    y=alt.Y("store:N", title="Store", sort="-x"),
                    color=alt.Color("type:N", title="Store type", scale=type_colors),
                    tooltip=[
                        alt.Tooltip("store:N", title="Store"),
                        alt.Tooltip("type:N", title="Type"),
                        alt.Tooltip("total_sales:Q", title="Total sales", format="$,.2f"),
                    ],
                ).properties(height=310)
                st.altair_chart(top_stores_chart, width="stretch")
        with right:
            with st.container(border=True):
                st.subheader("Sales mix by store type")
                st.caption("Share of selected sales contributed by each store type")
                type_sales = sales.groupby("type", as_index=False)["weekly_sales"].sum()
                type_donut = alt.Chart(type_sales).mark_arc(innerRadius=65).encode(
                    theta=alt.Theta("weekly_sales:Q"),
                    color=alt.Color("type:N", title="Store type", scale=type_colors),
                    tooltip=[
                        alt.Tooltip("type:N", title="Store type"),
                        alt.Tooltip("weekly_sales:Q", title="Total sales", format="$,.2f"),
                    ],
                ).properties(height=310)
                st.altair_chart(type_donut, width="stretch")

        with st.container(border=True):
            st.subheader("Store size and sales")
            st.caption("Each point is a store; compare footprint with total selected sales")
            size_sales_chart = alt.Chart(store_scorecard.dropna(subset=["size"])).mark_circle(size=110, opacity=0.75).encode(
                x=alt.X("size:Q", title="Store size"),
                y=alt.Y("total_sales:Q", title="Total sales", axis=alt.Axis(format="$,.0f")),
                color=alt.Color("type:N", title="Store type", scale=type_colors),
                tooltip=[
                    alt.Tooltip("store:N", title="Store"),
                    alt.Tooltip("type:N", title="Type"),
                    alt.Tooltip("size:Q", title="Size", format=","),
                    alt.Tooltip("total_sales:Q", title="Total sales", format="$,.2f"),
                ],
            ).properties(height=330)
            st.altair_chart(size_sales_chart, width="stretch")

        with st.container(border=True):
            st.subheader("Store scorecard")
            st.caption("Ranked store totals and weekly averages for the selected data")
            st.dataframe(
                store_scorecard.style.background_gradient(subset=["total_sales"], cmap="Blues"),
                column_config={
                    "store": st.column_config.NumberColumn("Store"),
                    "total_sales": st.column_config.NumberColumn("Total sales", format="$%.2f"),
                    "average_weekly_sales": st.column_config.NumberColumn("Average weekly sales", format="$%.2f"),
                    "type": st.column_config.TextColumn("Type"),
                    "size": st.column_config.NumberColumn("Size", format="%d"),
                },
                hide_index=True,
                height=360,
            )

    dept_sales = sales.groupby("dept", as_index=False)["weekly_sales"].sum()
    top_departments = dept_sales.nlargest(10, "weekly_sales").sort_values("weekly_sales")
    bottom_departments = dept_sales.nsmallest(10, "weekly_sales").sort_values("weekly_sales", ascending=False)
    department_weekly_sales = sales.groupby(["dept", "date"], as_index=False)["weekly_sales"].sum()
    department_stats = (
        department_weekly_sales.groupby("dept", as_index=False)
        .agg(total_sales=("weekly_sales", "sum"), average_weekly_sales=("weekly_sales", "mean"))
        .merge(sales.groupby("dept", as_index=False)["store"].nunique().rename(columns={"store": "stores_carrying"}), on="dept")
        .sort_values("total_sales", ascending=False)
    )

    with departments_tab:
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.subheader("Top departments")
                st.caption("Top 10 by total sales")
                st.bar_chart(top_departments.set_index("dept"), y="weekly_sales", color="#34D399", height=310)
        with right:
            with st.container(border=True):
                st.subheader("Bottom performers")
                st.caption("10 departments with the lowest total sales")
                st.bar_chart(bottom_departments.set_index("dept"), y="weekly_sales", color="#F87171", height=310)

        with st.container(border=True):
            st.subheader("Department statistics")
            st.caption("Sales, weekly average, and store coverage by department")
            st.dataframe(
                department_stats,
                column_config={
                    "dept": st.column_config.NumberColumn("Department"),
                    "total_sales": st.column_config.NumberColumn("Total sales", format="$%.2f"),
                    "average_weekly_sales": st.column_config.NumberColumn("Average weekly sales", format="$%.2f"),
                    "stores_carrying": st.column_config.NumberColumn("Stores carrying"),
                },
                hide_index=True,
                height=360,
            )

    weekly_context = sales.groupby(["date", "isholiday"], as_index=False)["weekly_sales"].sum()
    holiday_sales = weekly_context.groupby("isholiday", as_index=False)["weekly_sales"].mean()
    holiday_sales["week_type"] = holiday_sales["isholiday"].map({True: "Holiday", False: "Non-holiday"}).fillna("Non-holiday")
    seasonality = weekly_context.assign(week_of_year=weekly_context["date"].dt.isocalendar().week.astype(int))
    seasonality = seasonality.groupby("week_of_year", as_index=False)["weekly_sales"].mean()

    with trends_tab:
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.subheader("Holiday sales lift")
                st.caption("Average total weekly sales for holiday and non-holiday weeks")
                holiday_chart = alt.Chart(holiday_sales).mark_bar().encode(
                    x=alt.X("week_type:N", title=None, sort=["Non-holiday", "Holiday"]),
                    y=alt.Y("weekly_sales:Q", title="Average weekly sales", axis=alt.Axis(format="$,.0f")),
                    color=alt.Color(
                        "week_type:N",
                        legend=None,
                        scale=alt.Scale(domain=["Non-holiday", "Holiday"], range=["#38BDF8", "#FBBF24"]),
                    ),
                    tooltip=[
                        alt.Tooltip("week_type:N", title="Week type"),
                        alt.Tooltip("weekly_sales:Q", title="Average weekly sales", format="$,.2f"),
                    ],
                ).properties(height=310)
                st.altair_chart(holiday_chart, width="stretch")
        with right:
            with st.container(border=True):
                st.subheader("Weekly seasonality")
                st.caption("Average weekly sales by ISO week number across the selected period")
                seasonality_chart = alt.Chart(seasonality).mark_line(color="#A78BFA", point=True).encode(
                    x=alt.X("week_of_year:Q", title="Week of year", scale=alt.Scale(domain=[1, 52])),
                    y=alt.Y("weekly_sales:Q", title="Average weekly sales", axis=alt.Axis(format="$,.0f")),
                    tooltip=[
                        alt.Tooltip("week_of_year:Q", title="Week of year"),
                        alt.Tooltip("weekly_sales:Q", title="Average weekly sales", format="$,.2f"),
                    ],
                ).properties(height=310)
                st.altair_chart(seasonality_chart, width="stretch")

        with st.container(border=True):
            st.subheader("Sales and external factors")
            st.caption("Each point is a selected sales record; selections above 3,000 rows are sampled for responsive charts")
            factor_charts = []
            for column, label in [
                ("temperature", "Temperature"),
                ("fuel_price", "Fuel price"),
                ("cpi", "CPI"),
                ("unemployment", "Unemployment"),
            ]:
                factor_data = sales.dropna(subset=[column, "weekly_sales"])
                if len(factor_data) > 3_000:
                    factor_data = factor_data.sample(n=3_000, random_state=42)
                factor_charts.append(
                    alt.Chart(factor_data).mark_circle(opacity=0.3, color="#38BDF8").encode(
                        x=alt.X(f"{column}:Q", title=label),
                        y=alt.Y("weekly_sales:Q", title="Weekly sales", axis=alt.Axis(format="$,.0f")),
                        tooltip=[
                            alt.Tooltip(f"{column}:Q", title=label, format=".2f"),
                            alt.Tooltip("weekly_sales:Q", title="Weekly sales", format="$,.2f"),
                        ],
                    ).properties(width=330, height=230)
                )
            st.altair_chart(alt.concat(*factor_charts, columns=2), width="stretch")

    with ask_tab:
        with st.container(border=True):
            st.subheader("Ask Store Pulse")
            st.caption("GPT-5.6 analyzes only the currently filtered, pre-aggregated sales summary.")

            if DEMO_MODE:
                st.caption("Demo mode — connect an OpenAI API key in `.env` to enable live GPT-5.6 responses.")

            data_summary = build_data_summary(sales)
            st.session_state.setdefault("store_pulse_chat_history", [])

            if st.button("Generate executive summary", icon=":material/auto_awesome:"):
                try:
                    with st.spinner("Asking GPT-5.6…"):
                        st.session_state["store_pulse_summary"] = generate_summary(data_summary, model=DEFAULT_MODEL)
                except Exception as error:
                    st.error(f"Could not generate the executive summary: {error}")

            if st.session_state.get("store_pulse_summary"):
                st.markdown(st.session_state["store_pulse_summary"])

            for message in st.session_state.store_pulse_chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            question = st.chat_input("Ask about the selected sales data", key="store_pulse_question")
            if question:
                st.session_state.store_pulse_chat_history.append({"role": "user", "content": question})
                with st.chat_message("user"):
                    st.markdown(question)

                try:
                    with st.chat_message("assistant"):
                        with st.spinner("Asking GPT-5.6…"):
                            answer = answer_question(question, data_summary, model=DEFAULT_MODEL)
                        st.markdown(answer)
                    st.session_state.store_pulse_chat_history.append({"role": "assistant", "content": answer})
                except Exception as error:
                    st.error(f"Could not answer that question: {error}")


try:
    sales_data = load_sales_data()
    show_dashboard(sales_data)
except Exception as error:
    st.error("The dashboard could not load data from PostgreSQL.")
    st.exception(error)
    st.info("Check that `.env` has valid DB_* values and that the ETL has created `clean_sales`.")
