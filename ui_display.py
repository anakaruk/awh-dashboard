import streamlit as st
import pandas as pd

# Optional Altair import (fallback to Streamlit charts if unavailable)
try:
    import altair as alt
    _ALT_OK = True
except Exception:
    _ALT_OK = False


# ----------- Sidebar Controls -----------
def render_controls(station_list):
    """
    Render sidebar controls (simplified for end users):
      - Station selector
      - Intake area selector
      - Date range selector
      - Field selection
    Returns:
      (selected_station, selected_fields, intake_area, (start_date, end_date), controls)
    """
    st.sidebar.header("🔧 Controls")

    # --- Station select ---
    selected_station_name = st.sidebar.selectbox("📍 Select Station", station_list)

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

    # --- Field selection ---
    field_options = [
        ("❄️ Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("💧 Water Production (L)", "water_production"),
        ("🔋 Energy Per Liter (kWh/L)", "energy_per_liter (kWh/L)"),
        ("🔋 Power Consumption (kWh)", "accumulated_energy (kWh)"),
        ("🌫️ Abs. Intake humidity (g/m³)", "absolute_intake_air_humidity"),
        ("🌫️ Abs. Outtake humidity (g/m³)", "absolute_outtake_air_humidity"),
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

    # ---- Minimal controls dict (defaults for process_data) ----
    controls = {
        "lag_steps": 10,
        "apply_reset": False,
        "apply_pause": False,
        "apply_freeze": False,
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
                    chart = (
                        alt.Chart(plot_data)
                        .mark_circle(size=60)
                        .encode(
                            x=alt.X("timestamp:T",
                                    title="Date & Time",
                                    axis=alt.Axis(format="%Y-%m-%d %H:%M", labelAngle=-45)),
                            y=alt.Y(field, title=field),
                            tooltip=["timestamp", field],
                        )
                        .properties(width="container", height=300)
                    )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.line_chart(plot_data.set_index("timestamp")[[field]], use_container_width=True)
