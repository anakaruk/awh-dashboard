import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, time as dtime

from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data

# 🌐 Configure page
st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

local_tz = pytz.timezone("America/Phoenix")

def combine_dt(date_obj, time_obj):
    """Safely combine date+time to timezone-aware datetime in Arizona; return None if missing."""
    if date_obj is None or time_obj is None:
        return None
    dt_naive = datetime.combine(date_obj, time_obj if isinstance(time_obj, dtime) else dtime(0, 0, 0))
    return local_tz.localize(dt_naive)

# 🔌 Load list of stations
stations = get_station_list()

if not stations:
    st.warning("⚠️ No stations with data available.")
else:
    # 🎛 Sidebar controls (now returns controls dict)
    station, selected_fields, controls = render_controls(stations)

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
            # assume incoming is UTC; convert to Arizona
            df_raw["timestamp"] = df_raw["timestamp"].dt.tz_localize("UTC").dt.tz_convert(local_tz)
        else:
            df_raw["timestamp"] = df_raw["timestamp"].dt.tz_convert(local_tz)

        # ---------------- Build control flags ----------------
        df_flags = pd.DataFrame(index=df_raw.index)
        df_flags["reset_flag"] = False
        df_flags["counting"] = True
        df_flags["freeze_flag"] = False

        # Reset from (mark exactly 1 row True at the first row >= reset_ts)
        if controls["apply_reset"]:
            reset_ts = combine_dt(controls["reset_date"], controls["reset_time"])
            if reset_ts is not None:
                mask = df_raw["timestamp"] >= reset_ts
                if mask.any():
                    first_idx = df_raw.index[mask].min()
                    df_flags.loc[first_idx, "reset_flag"] = True

        # Pause window (set counting=False within range)
        if controls["apply_pause"]:
            start_ts = combine_dt(controls["pause_start_date"], controls["pause_start_time"])
            end_ts = combine_dt(controls["pause_end_date"], controls["pause_end_time"])
            if (start_ts is not None) and (end_ts is not None) and (end_ts >= start_ts):
                pmask = (df_raw["timestamp"] >= start_ts) & (df_raw["timestamp"] <= end_ts)
                df_flags.loc[pmask, "counting"] = False

        # Freeze from (first True at boundary; process_data will carry-forward)
        if controls["apply_freeze"]:
            freeze_ts = combine_dt(controls["freeze_date"], controls["freeze_time"])
            if freeze_ts is not None:
                fmask = df_raw["timestamp"] >= freeze_ts
                if fmask.any():
                    first_fidx = df_raw.index[fmask].min()
                    df_flags.loc[first_fidx, "freeze_flag"] = True

        # Merge flags
        df_raw["reset_flag"] = df_flags["reset_flag"].values
        df_raw["counting"] = df_flags["counting"].values
        df_raw["freeze_flag"] = df_flags["freeze_flag"].values

        # 🧮 Process data with controls
        df_processed = process_data(
            df_raw,
            intake_area=controls["intake_area"],
            lag_steps=controls["lag_steps"],
            reset_col="reset_flag",
            count_col="counting",
            freeze_col="freeze_flag",
            # session_col="station_id",  # uncomment if you have per-device sessions
        )

        # 🕒 Display most recent update time
        latest_time = df_processed["timestamp"].max()
        st.markdown(f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 📊 Show dashboard
        render_data_section(df_processed, station, selected_fields)
