import streamlit as st
import pandas as pd
import altair as alt

def render_controls(station_list):
    st.sidebar.header("🔧 Controls")
    selected_station_name = st.sidebar.selectbox("📍 Select Station", station_list)

    intake_area_options = {
        "DewStand 1: 0.0507 m²": 0.0507,
        "T50 1: 0.18 m²": 0.18
    }

    intake_area_label = st.sidebar.selectbox("🧮 Intake Area (m²)", list(intake_area_options.keys()))
    intake_area = intake_area_options[intake_area_label]

    # Field checkboxes
    show_harvest_eff = st.sidebar.checkbox("⚙️ Harvesting Efficiency (%)", value=True)
    show_intake_water = st.sidebar.checkbox("💦 Intake Water (L)", value=True)
    show_prod = st.sidebar.checkbox("💧 Water Production", value=True)
    show_power_consumption = st.sidebar.checkbox("🔋 Power Consumption (kWh)", value=True)
    show_energy_per_liter = st.sidebar.checkbox("🔋 Energy per Liter (kWh/L)", value=True)
    show_current = st.sidebar.checkbox("🔌 Current", value=True)
    show_power = st.sidebar.checkbox("⚡ Power", value=True)
    show_temp_in = st.sidebar.checkbox("🌡️ Intake Temp", value=True)
    show_humid_in = st.sidebar.checkbox("💨 Intake Humidity", value=True)
    show_velocity_in = st.sidebar.checkbox("↘ Intake Velocity", value=True)
    show_abs_in = st.sidebar.checkbox("🌫️ Abs Intake Humidity", value=True)
    show_temp_out = st.sidebar.checkbox("🔥 Outtake Temp", value=True)
    show_humid_out = st.sidebar.checkbox("💨 Outtake Humidity", value=True)
    show_velocity_out = st.sidebar.checkbox("↗ Outtake Velocity", value=True)
    show_abs_out = st.sidebar.checkbox("🌫️ Abs Outtake Humidity", value=True)

    selected_fields = ["timestamp"]
    if show_harvest_eff: selected_fields.append("harvesting_efficiency")
    if show_intake_water: selected_fields.append("accumulated_intake_water")
    if show_prod: selected_fields.append("water_production")
    if show_power_consumption: selected_fields.append("accumulated_energy (kWh)")
    if show_energy_per_liter: selected_fields.append("energy_per_liter (kWh/L)")
    if show_current: selected_fields.append("current")
    if show_power: selected_fields.append("power")
    if show_temp_in: selected_fields.append("intake_air_temperature (C)")
    if show_humid_in: selected_fields.append("intake_air_humidity (%)")
    if show_velocity_in: selected_fields.append("intake_air_velocity (m/s)")
    if show_abs_in: selected_fields.append("absolute_intake_air_humidity")
    if show_temp_out: selected_fields.append("outtake_air_temperature (C)")
    if show_humid_out: selected_fields.append("outtake_air_humidity (%)")
    if show_velocity_out: selected_fields.append("outtake_air_velocity (m/s)")
    if show_abs_out: selected_fields.append("absolute_outtake_air_humidity")

    return selected_station_name, selected_fields, intake_area

def render_data_section(df, station_name, selected_fields):
    st.title(f"📊 AWH Dashboard – {station_name}")

    if df.empty:
        st.warning("No data found for this station.")
        return

    available_fields = [col for col in selected_fields if col in df.columns and col != "timestamp"]

    for field in available_fields:
        st.subheader(f"📊 `{field}` Overview")

        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### 📋 Table")
            st.dataframe(df[["timestamp", field]], use_container_width=True)

            st.download_button(
                label=f"⬇️ Download `{field}` CSV",
                data=df[["timestamp", field]].to_csv(index=False),
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv"
            )

        with col2:
            st.markdown("#### 📈 Scatter Plot")
            df_sorted = df.sort_values("timestamp")
            chart = alt.Chart(df_sorted).mark_circle(size=60).encode(
                x='timestamp:T',
                y=alt.Y(field, title=field),
                tooltip=['timestamp', field]
            ).properties(width="container", height=300)

            st.altair_chart(chart, use_container_width=True)
