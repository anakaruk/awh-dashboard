import streamlit as st
import pandas as pd
from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import calculate_absolute_humidity, calculate_water_production

st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

# 🧠 Initialize session state for refresh flag
if "refresh_data" not in st.session_state:
    st.session_state.refresh_data = False

# 🔽 Get list of stations
stations = get_station_list()

if not stations:
    st.warning("⚠️ No stations with data available.")
else:
    # ⏹️ Sidebar controls and selected station
    station, selected_fields, intake_area = render_controls(stations)

    # 🔄 Manual refresh button
    if st.button("🔄 Refresh Data"):
        st.session_state.refresh_data = True
        st.experimental_rerun()

    # 🧠 On rerun, clear the flag
    if st.session_state.refresh_data:
        st.session_state.refresh_data = False

    # 📥 Load data
    df_raw = load_station_data(station)

    if df_raw.empty:
        st.warning(f"No data found for station: {station}")
    else:
        # 🔁 Rename Firestore field names
        df_raw.rename(columns={
            "temperature": "intake_air_temperature (C)",
            "humidity": "intake_air_humidity (%)",
            "velocity": "intake_air_velocity (m/s)",
            "outtake_temperature": "outtake_air_temperature (C)",
            "outtake_humidity": "outtake_air_humidity (%)",
            "outtake_velocity": "outtake_air_velocity (m/s)",
            "energy": "accumulated_energy (kWh)"
        }, inplace=True)

        # 🌫️ Absolute Humidity
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
                ), a
