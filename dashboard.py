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

        # 🕒 Date range selector (SIDEBAR)
        min_dt = df_processed["timestamp"].min()
        max_dt = df_processed["timestamp"].max()
        min_date = min_dt.date()
        max_date = max_dt.date()

        st.sidebar.markdown("### 📆 Date range")
        date_range = st.sidebar.date_input(
            "Select start and end date",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

        # Normalize return type (tuple or single date)
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = date_range
            end_date = date_range

        # 🔎 Filter data by selected dates (inclusive)
        mask = (df_processed["timestamp"].dt.date >= start_date) & (df_processed["timestamp"].dt.date <= end_date)
        df_filtered = df_processed.loc[mask].copy()

        # 🕒 Display most recent update time (overall + filtered)
        st.markdown(
            f"**Last Updated (Local – Arizona):** {max_dt.strftime('%Y-%m-%d %H:%M:%S')}  "
            f"· **Showing:** {start_date} → {end_date} "
            f"({len(df_filtered)} rows)"
        )

        if df_filtered.empty:
            st.info("No data in the selected date range. Try expanding the range.")
        else:
            # 📊 Show dashboard with filtered data
            render_data_section(df_filtered, station, selected_fields)
