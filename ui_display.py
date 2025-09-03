import streamlit as st
import pandas as pd

# Optional Altair import (fallback to Streamlit charts if unavailable)
try:
    import altair as alt
    _ALT_OK = True
except Exception:
    _ALT_OK = False


def render_controls(station_list):
    st.sidebar.header("🔧 Controls")
    selected_station_name = st.sidebar.selectbox("📍 Select Station", station_list)

    intake_area_options = {
        "AquaPars 1: 0.12 m²": 0.12,
        "DewStand 1: 0.04 m²": 0.04,
        "T50 1: 0.18 m²": 0.18,
    }
    intake_area_label = st.sidebar.selectbox(
        "🧲 Intake Area (m²)", list(intake_area_options.keys())
    )
    intake_area = float(intake_area_options[intake_area_label])

    st.sidebar.markdown("### ⏱️ Calculation Window")

    # --- Reset from ---
    apply_reset = st.sidebar.checkbox("🔄 Reset accumulations from…", value=False)
    reset_date = st.sidebar.date_input("Reset date", value=None, disabled=not apply_reset)
    reset_time = st.sidebar.time_input("Reset time", value=None, disabled=not apply_reset)

    # --- Pause window ---
    apply_pause = st.sidebar.checkbox("⏸️ Pause counting between…", value=False)
    pause_start_date = st.sidebar.date_input("Pause start date", value=None, disabled=not apply_pause)
    pause_start_time = st.sidebar.time_input("Pause start time", value=None, disabled=not apply_pause)
    pause_end_date = st.sidebar.date_input("Pause end date", value=None, disabled=not apply_pause)
    pause_end_time = st.sidebar.time_input("Pause end time", value=None, disabled=not apply_pause)

    # --- Freeze from ---
    apply_freeze = st.sidebar.checkbox("🛑 Freeze outputs from…", value=False)
    freeze_date = st.sidebar.date_input("Freeze date", value=None, disabled=not apply_freeze)
    freeze_time = st.sidebar.time_input("Freeze time", value=None, disabled=not apply_freeze)

    # Optional: adjust lag steps for efficiency
    lag_steps = int(st.sidebar.number_input("Production lag steps", min_value=0, max_value=200, value=10, step=1))

    field_options = [
        ("❄️ Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("💧 Water Production (L)", "water_production"),
        ("🔋 Energy Per Liter (kWh/L)", "energy_per_liter (kWh/L)"),
        ("🔋 Power Consumption (kWh)", "accumulated_energy (kWh)"),
        ("🌫️ Abs. Intake humidity (g/m3)", "absolute_intake_air_humidity"),
        ("🌫️ Abs. Outtake humidity (g/m3)", "absolute_outtake_air_humidity"),
        ("🌫️ Adjust Abs. Outtake humidity (g/m3)", "calibrated_outtake_air_humidity"),
        ("🌡️ Intake temperature (°C)", "intake_air_temperature (C)"),
        ("💨 Intake humidity (%)", "intake_air_humidity (%)"),
        ("↘ Intake velocity (m/s)", "intake_air_velocity (m/s)"),
        ("🔥 Outtake temperature (°C)", "outtake_air_temperature (C)"),
        ("💨 Outtake humidity (%)", "outtake_air_humidity (%)"),
        ("↗ Outtake velocity (m/s)", "outtake_air_velocity (m/s)"),
        ("🔌 Current (A)", "current"),
        ("⚡ Power (W)", "power"),
    ]

    selected_fields = ["timestamp"]
    for label, col in field_options:
        if st.sidebar.checkbox(label, value=(col == "harvesting_efficiency")):
            selected_fields.append(col)

    if not _ALT_OK:
        st.sidebar.warning("Altair not installed — using fallback charts.")

    controls = {
        "apply_reset": apply_reset,
        "reset_date": reset_date,
        "reset_time": reset_time,
        "apply_pause": apply_pause,
        "pause_start_date": pause_start_date,
        "pause_start_time": pause_start_time,
        "pause_end_date": pause_end_date,
        "pause_end_time": pause_end_time,
        "apply_freeze": apply_freeze,
        "freeze_date": freeze_date,
        "freeze_time": freeze_time,
        "lag_steps": lag_steps,
        "intake_area": intake_area,
    }

    return selected_station_name, selected_fields, controls


def _plot_with_altair(plot_data: pd.DataFrame, field: str):
    if field == "energy_per_liter (kWh/L)":
        plot_data = plot_data.copy()
        plot_data["Hour"] = plot_data["timestamp"].dt.floor("H")
        hourly_plot = (
            plot_data.groupby("Hour")[field]
            .mean()
            .reset_index()
            .rename(columns={"Hour": "timestamp"})
        )
        chart = (
            alt.Chart(hourly_plot)
            .mark_bar()
            .encode(
                x=alt.X("timestamp:T", title="Hour", axis=alt.Axis(format="%H:%M")),
                y=alt.Y(field, title="Energy per Liter (kWh/L)"),
                tooltip=["timestamp", field],
            )
            .properties(width="container", height=300)
        )
        return chart

    y_axis = alt.Y(
        field,
        title=field,
        scale=alt.Scale(domain=[0, 50]) if field == "harvesting_efficiency" else alt.Undefined,
    )

    chart = (
        alt.Chart(plot_data)
        .mark_circle(size=60)
        .encode(
            x=alt.X(
                "timestamp:T",
                title="Date & Time",
                axis=alt.Axis(format="%Y-%m-%d %H:%M", labelAngle=-45),
            ),
            y=y_axis,
            tooltip=["timestamp", field],
        )
        .properties(width="container", height=300)
    )
    return chart


def _plot_fallback(plot_data: pd.DataFrame, field: str):
    st.line_chart(plot_data.set_index("timestamp")[[field]], use_container_width=True)


def render_data_section(df, station_name, selected_fields):
    st.title(f"📊 AWH Dashboard – {station_name}")

    if df.empty:
        st.warning("No data found for this station.")
        return

    available_fields = [col for col in selected_fields if col in df.columns and col != "timestamp"]

    df_sorted = df.sort_values("timestamp").copy()
    df_sorted["Date"] = df_sorted["timestamp"].dt.date
    df_sorted["Time"] = df_sorted["timestamp"].dt.strftime("%H:%M:%S")

    for field in available_fields:
        st.subheader(f"📊 {field} Overview")

        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### 📋 Table")
            st.dataframe(df_sorted[["Date", "Time", field]], use_container_width=True)

            st.download_button(
                label=f"⬇️ Download {field} CSV",
                data=df_sorted[["Date", "Time", field]].to_csv(index=False),
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv",
            )

        with col2:
            st.markdown("#### 📈 Plot")

            df_sorted[field] = pd.to_numeric(df_sorted[field], errors="coerce")
            plot_data = df_sorted[["timestamp", field]].dropna()

            excluded_points = 0
            if field == "harvesting_efficiency":
                excluded_points = (plot_data[field] > 50).sum()
                plot_data = plot_data[plot_data[field] <= 50]

            if plot_data.empty:
                st.warning(f"⚠️ No data available to plot for {field}.")
                continue

            if _ALT_OK:
                chart = _plot_with_altair(plot_data, field)
                st.altair_chart(chart, use_container_width=True)
            else:
                _plot_fallback(plot_data, field)

            if excluded_points > 0:
                st.caption("⚠️ Some points above 50% were excluded from the plot.")
