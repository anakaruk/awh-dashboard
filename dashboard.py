import streamlit as st
import pandas as pd
from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data

st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

# 🔌 Load station list
stations = get_station_list()

if not stations:
    st.warning("⚠️ No stations with data available.")
else:
    # 🎛 Sidebar controls
    station, selected_fields, intake_area = render_controls(stations)

    # 📥 Load and process data
    df_raw = load_station_data(station)
    if df_raw.empty:
        st.warning(f"No data found for station: {station}")
    else:
        df_processed = process_data(df_raw, intake_area=intake_area)

        # 🕒 Display last update time
        latest_time = df_processed["timestamp"].max()
        st.markdown(f"**Last Updated:** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 📊 Display data table + chart
        render_data_section(df_processed, station, selected_fields)
