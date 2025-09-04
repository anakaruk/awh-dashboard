import streamlit as st
import pandas as pd
import pytz

from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data

# 🌐 Configure page
st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

local_tz = pytz.timezone("America/Phoenix")

# 🔌 Load list of stations
stations = get_station_list()

if not stations:
    st.warning("⚠️ No stations with data available.")
else:
    # 🎛 Sidebar controls
    station, selected_fields, intake_area, (start_date, end_date) = render_controls(stations)

    # 📥 Load raw data
    df_raw = load_station_data(station)

    if df_raw.empty:
        st.warning(f"⚠️ No data found for station: {station}")
    else:
        # Ensure timestamp is tz-aware (Arizona)
        df_raw = df_raw.copy()
        df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"], errors="coerce")
        df_raw = df_raw.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        if df_raw["timestamp"].dt.tz is None:
            df_raw["timestamp"] = df_raw["timestamp"].dt.tz_localize("UTC").dt.tz_convert(local_tz)
        else:
            df_raw["timestamp"] = df_raw["timestamp"].dt.tz_convert(local_tz)

        # --- Apply date range filter ---
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        start_dt = pd.Timestamp(start_date).tz_localize(local_tz)
        end_of_day = (
            pd.Timestamp(end_date).tz_localize(local_tz)
            + pd.Timedelta(days=1)
            - pd.Timedelta(microseconds=1)
        )
        now_local = pd.Timestamp.now(tz=local_tz)
        end_dt = min(end_of_day, now_local)

        df_raw = df_raw[(df_raw["timestamp"] >= start_dt) & (df_raw["timestamp"] <= end_dt)]

        if df_raw.empty:
            st.info("⚠️ No data in the selected date range.")
            st.stop()

        # 🧮 Process data (clean, no reset/pause/freeze)
        df_processed = process_data(
            df_raw,
            intake_area=intake_area,
            lag_steps=10,  # fixed default
        )

        # 🕒 Display most recent update time
        latest_time = df_processed["timestamp"].max()
        st.markdown(
            f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        # 📊 Show dashboard
        render_data_section(df_processed, station, selected_fields)
