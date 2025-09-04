# ui_display.py
import streamlit as st
import pandas as pd

# --- Altair optional (fallback to Streamlit charts if unavailable) ---
try:
    import altair as alt
    _ALT_OK = True
except Exception:
    _ALT_OK = False


# ----------- Sidebar Controls -----------
def render_controls(station_list):
    """
    Renders sidebar with:
      - Station selector (placeholder until chosen)
      - Intake area selector (placeholder until chosen)
      - Date range (defaults: today → today)
      - Field selection + lag_steps

    Returns:
      (station or None, selected_fields, intake_area or None, (start_date, end_date), controls)
    """
    st.sidebar.header("🔧 Controls")

    # --- Station select with placeholder ---
    station_placeholder = "— Please select station —"
    station_choice = st.sidebar.selectbox(
        "📍 Select Station",
        [station_placeholder] + list(station_list),
        index=0,
    )
    station = None if station_choice == station_placeholder else station_choice

    # --- Intake area with placeholder ---
    area_placeholder = "— Please select intake area —"
    intake_area_options = {
        "AquaPars 1: 0.12 m²": 0.12,
        "DewStand 1: 0.04 m²": 0.04,
        "T50 1: 0.18 m²": 0.18,
    }
    intake_labels = [area_placeholder] + list(intake_area_options.keys())
    intake_label = st.sidebar.selectbox("🧲 Intake Area (m²)", intake_labels, index=0)
    intake_area = None if intake_label == area_placeholder else float(intake_area_options[intake_label])

    # --- Date period (today → today) ---
    st.sidebar.subheader("📅 Date period")
    today = pd.Timestamp.now().date()
    picked = st.sidebar.date_input("Select date range", value=(today, today))
    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        start_date, end_date = picked
    else:
        start_date = end_date = picked

    # --- Fields ---
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

    # Lag steps (kept in controls for process_data)
    lag_steps = int(st.sidebar.number_input("Production lag steps", 0, 200, 10, 1))

    if not _ALT_OK:
        st.sidebar.warning("Altair not installed — using fallback charts.")

    controls = {
        "lag_steps": lag_steps,
    }
    return station, selected_fields, intake_area, (start_date, end_date), controls


# ----------- Data Section -----------
def render_data_section(df, station_name, selected_fields):
    st.title(f"📊 AWH Dashboard – {station_name}")

    if df.empty:
        st.warning("No data found for this station.")
        return

    usable_fields = [c for c in selected_fields if c in df.columns and c != "timestamp"]

    df_sorted = df.sort_values("timestamp").copy()
    df_sorted["Date"] = df_sorted["timestamp"].dt.date
    df_sorted["Time"] = df_sorted["timestamp"].dt.strftime("%H:%M:%S")

    for field in usable_fields:
        st.subheader(f"📊 {field} Overview")
        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### 📋 Table")
            st.dataframe(df_sorted[["Date", "Time", field]], use_container_width=True)
            st.download_button(
                f"⬇️ Download {field} CSV",
                df_sorted[["Date", "Time", field]].to_csv(index=False),
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv",
            )

        with col2:
            st.markdown("#### 📈 Plot")
            df_sorted[field] = pd.to_numeric(df_sorted[field], errors="coerce")
            plot_data = df_sorted[["timestamp", field]].dropna()
            if plot_data.empty:
                st.info("No points to plot for this field.")
                continue

            if _ALT_OK:
                # Hourly bar for EPL; scatter for others
                if field == "energy_per_liter (kWh/L)":
                    plot_data = plot_data.copy()
                    plot_data["Hour"] = plot_data["timestamp"].dt.floor("H")
                    hourly = (
                        plot_data.groupby("Hour")[field]
                        .mean()
                        .reset_index()
                        .rename(columns={"Hour": "timestamp"})
                    )
                    chart = (
                        alt.Chart(hourly)
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
