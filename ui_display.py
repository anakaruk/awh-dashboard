import streamlit as st
import pandas as pd

# Optional Altair import (fallback to Streamlit charts if unavailable)
try:
    import altair as alt
    _ALT_OK = True
except Exception:
    _ALT_OK = False


# ----------- Helpers -----------
def _status_chip(name: str, is_online: bool, last_seen_text: str) -> str:
    """Return station label with status dot."""
    dot = "🟢" if is_online else "🔴"
    return f"{name} {dot}"


# ----------- Sidebar Controls -----------
def render_controls(
    station_list,
    default_station=None,
    station_status=None,
    last_seen_map=None
):
    """
    Render sidebar controls.

    Args:
        station_list (list[str]): available stations
        default_station (str): pre-selected station
        station_status (dict): {station: bool} online status
        last_seen_map (dict): {station: datetime} last seen time

    Returns:
        (selected_station_name, selected_fields, intake_area, (start_date, end_date), controls)
    """
    station_status = station_status or {}
    last_seen_map = last_seen_map or {}

    st.sidebar.header("🔧 Controls")

    # --- Station select with status dots ---
    labels = []
    for s in station_list:
        last_txt = (
            last_seen_map.get(s).strftime("%Y-%m-%d %H:%M:%S") + " AZ"
            if last_seen_map.get(s) is not None
            else "—"
        )
        lbl = _status_chip(s, station_status.get(s, False), last_txt)
        labels.append(lbl)

    if default_station in station_list:
        default_index = station_list.index(default_station)
    else:
        default_index = 0

    selected_label = st.sidebar.selectbox(
        "📍 Select Station",
        options=labels,
        index=default_index,
        help="🟢 = station has data in the last 10 minutes"
    )
    selected_station_name = station_list[labels.index(selected_label)]

    # --- Intake area ---
    intake_area_options = {
        "AquaPars 1: 0.12 m²": 0.12,
        "DewStand 1: 0.04 m²": 0.04,
        "T50 1: 0.18 m²": 0.18,
    }
    intake_area_label = st.sidebar.selectbox("🧲 Intake Area (m²)", list(intake_area_options.keys()))
    intake_area = float(intake_area_options[intake_area_label])

    # --- Date period ---
    st.sidebar.subheader("📅 Date period")
    today = pd.Timestamp.now().date()
    picked = st.sidebar.date_input("Select date range", value=(today, today))
    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        start_date, end_date = picked
    else:
        start_date = end_date = picked

    # --- Calculation Window ---
    st.sidebar.markdown("### ⏱️ Calculation Window")

    # Reset from
    apply_reset = st.sidebar.checkbox("🔄 Reset accumulations from…", value=False)
    reset_date = st.sidebar.date_input("Reset date", value=today, disabled=not apply_reset)
    reset_time = st.sidebar.time_input("Reset time", value=pd.to_datetime("00:00").time(), disabled=not apply_reset)

    # Pause window
    apply_pause = st.sidebar.checkbox("⏸️ Pause counting between…", value=False)
    pause_start_date = st.sidebar.date_input("Pause start date", value=today, disabled=not apply_pause)
    pause_start_time = st.sidebar.time_input("Pause start time", value=pd.to_datetime("00:00").time(), disabled=not apply_pause)
    pause_end_date = st.sidebar.date_input("Pause end date", value=today, disabled=not apply_pause)
    pause_end_time = st.sidebar.time_input("Pause end time", value=pd.to_datetime("23:59").time(), disabled=not apply_pause)

    # Freeze from
    apply_freeze = st.sidebar.checkbox("🛑 Freeze outputs from…", value=False)
    freeze_date = st.sidebar.date_input("Freeze date", value=today, disabled=not apply_freeze)
    freeze_time = st.sidebar.time_input("Freeze time", value=pd.to_datetime("00:00").time(), disabled=not apply_freeze)

    # Lag steps
    lag_steps = int(
        st.sidebar.number_input("Production lag steps", min_value=0, max_value=200, value=10, step=1)
    )

    # --- Field selection ---
    field_options = [
        ("❄️ Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("💧 Water Production (L)", "water_production"),
        ("🔋 Energy Per Liter (kWh/L)", "energy_per_liter (kWh/L)"),
        ("🔋 Power Consumption (kWh)", "accumulated_energy (kWh)"),
        ("🌫️ Abs. Intake humidity (g/m³)", "absolute_intake_air_humidity"),
        ("🌫️ Abs. Outtake humidity (g/m³)", "absolute_outtake_air_humidity"),
        ("🌫️ Adjust Abs. Outtake humidity (g/m³)", "calibrated_outtake_air_humidity"),
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

    return selected_station_name, selected_fields, intake_area, (start_date, end_date), controls


# ----------- Data Section -----------
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
                mime="text/csv"
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
                if field == "energy_per_liter (kWh/L)":
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
                else:
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
                st.altair_chart(chart, use_container_width=True)
            else:
                st.line_chart(plot_data.set_index("timestamp")[[field]], use_container_width=True)

            if excluded_points > 0:
                st.caption(f"⚠️ {excluded_points} point(s) above 50% were excluded from the plot.")
