import streamlit as st
import pandas as pd
from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import calculate_absolute_humidity, calculate_water_production

st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

# 🔽 Load available stations
stations = get_station_list()

if not stations:
    st.warning("⚠️ No stations with data available.")
else:
    # ⏹️ Sidebar UI controls and intake area setup
    station, selected_fields, intake_area = render_controls(stations)

    # 🔄 Manual refresh button
    if st.button("🔄 Refresh Data"):
        st.experimental_rerun()

    # 📥 Load data for selected station
    df_raw = load_station_data(station)

    if df_raw.empty:
        st.warning(f"No data found for station: {station}")
    else:
        # 🏷 Rename Firestore field names for UI display
        df_raw.rename(columns={
            "temperature": "intake_air_temperature (C)",
            "humidity": "intake_air_humidity (%)",
            "velocity": "intake_air_velocity (m/s)",
            "outtake_temperature": "outtake_air_temperature (C)",
            "outtake_humidity": "outtake_air_humidity (%)",
            "outtake_velocity": "outtake_air_velocity (m/s)",
            "energy": "accumulated_energy (kWh)"
        }, inplace=True)

        # 🌫️ Calculate absolute humidity if possible
        if "intake_air_temperature (C)" in df_raw and "intake_air_humidity (%)" in df_raw:
            df_raw["absolute_intake_air_humidity"] = df_raw.apply(
                lambda row: calculate_absolute_humidity(
                    row["intake_air_temperature (C)"], row["intake_air_humidity (%)"]
                ), axis=1
            )

        if "outtake_air_temperature (C)" in df_raw and "outtake_air_humidity (%)" in df_raw:
            df_raw["absolute_outtake_air_humidity"] = df_raw.apply(
                lambda row: calculate_absolute_humidity(
                    row["outtake_air_temperature (C)"], row["outtake_air_humidity (%)"]
                ), axis=1
            )

        # 💧 Water production calculation
        if "weight" in df_raw:
            df_raw["water_production"] = calculate_water_production(df_raw["weight"])

        # ⚡ Efficiency and energy per liter
        if "water_production" in df_raw and "accumulated_energy (kWh)" in df_raw:
            df_raw["energy_per_liter (kWh/L)"] = df_raw["accumulated_energy (kWh)"] / (df_raw["water_production"] / 1000 + 1e-6)
            df_raw["harvesting_efficiency"] = df_raw["water_production"] / (df_raw["accumulated_energy (kWh)"] + 1e-6)

        # 🕓 Display latest update time
        latest_time = df_raw["timestamp"].max()
        st.markdown(f"**Last Updated:** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 📊 Render charts and tables
        render_data_section(df_raw, station, selected_fields)
