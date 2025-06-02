import streamlit as st
import pandas as pd
import pytz
from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data

# 🌐 Configure page
st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

# 🔌 Load list of stations
stations = get_station_list()

if not stations:
    st.warning("⚠️ No stations with data available.")
else:
    # 🎛 Sidebar controls (station, intake area, selected fields)
    station, selected_fields, intake_area = render_controls(stations)

    # 📥 Load raw data
    df_raw = load_station_data(station)

    if df_raw.empty:
        st.warning(f"⚠️ No data found for station: {station}")
    else:
        # 🧮 Process data (rename, compute metrics, etc.)
        df_processed = process_data(df_raw, intake_area=intake_area)

        # ⏱️ Convert timestamp to local timezone (Arizona)
        local_tz = pytz.timezone("America/Phoenix")
        if df_processed["timestamp"].dt.tz is None:
            df_processed["timestamp"] = df_processed["timestamp"].dt.tz_localize("UTC").dt.tz_convert(local_tz)
        else:
            df_processed["timestamp"] = df_processed["timestamp"].dt.tz_convert(local_tz)

        # 🕒 Display most recent update time
        latest_time = df_processed["timestamp"].max()
        st.markdown(f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 📊 Show dashboard
        render_data_section(df_processed, station, selected_fields)
