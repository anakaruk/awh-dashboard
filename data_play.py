# ui_display.py
import streamlit as st
import pandas as pd

try:
    import altair as alt
    _ALT_OK = True
except Exception:
    _ALT_OK = False


# ---------------- Sidebar controls ----------------
def render_controls(station_list):
    st.sidebar.header("Controls")

    # Station
    station = st.sidebar.selectbox(
        "Station",
        ["Please select station"] + sorted(station_list),
        index=0,
    )

    # Intake area
    intake_area = st.sidebar.number_input(
        "Air intake area (m²)",
        min_value=0.01,
        max_value=5.0,
        value=1.0,
        step=0.01,
        help="Cross-sectional area used with velocity to estimate intake volume.",
    )

    # Efficiency window
    lag_steps = st.sidebar.slider(
        "Efficiency window (samples)",
        min_value=3,
        max_value=60,
        value=12,
        help="Rolling window length for harvesting efficiency.",
    )

    # Fields
    default_fields = ["harvesting_efficiency"]
    field_options = [
        "harvesting_efficiency",
        "water_production",
        "accumulated_intake_water",
        "energy_per_liter (kWh/L)",
        "power",
    ]
    selected_fields = st.sidebar.multiselect(
        "Fields to plot",
        options=field_options,
        default=default_fields,
    )

    controls = {"lag_steps": lag_steps}
    return station, intake_area, selected_fields, controls


# ---------------- Main display ----------------
def render_data_section(df: pd.DataFrame, station: str, selected_fields: list[str]):
    st.subheader("Plot")

    if station == "Please select station":
        st.info("Please select a station to view data.")
        return

    if df.empty:
        st.warning("No data for the chosen filters.")
        return

    # Plot each field
    for field in selected_fields:
        plot_data = df[["timestamp", field]].copy()
        plot_data = plot_data.replace([float("inf"), float("-inf")], pd.NA).dropna()

        if plot_data.empty:
            st.caption(f"No valid data for **{field}**.")
            continue

        if _ALT_OK:
            y_arg = alt.Y(
                field,
                title=field,
                # clamp efficiency axis so a stray point can’t blow up the scale
                scale=alt.Scale(domain=[0, 120]) if field == "harvesting_efficiency" else alt.Undefined,
            )

            chart = (
                alt.Chart(plot_data)
                .mark_circle(size=12, opacity=0.7)
                .encode(
                    x=alt.X(
                        "timestamp:T",
                        title="Date & Time",
                        axis=alt.Axis(format="%Y-%m-%d %H:%M", labelAngle=-45),
                    ),
                    y=y_arg,
                    tooltip=["timestamp:T", field],
                )
                .properties(width="container", height=300)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.line_chart(plot_data.set_index("timestamp")[[field]], use_container_width=True)
