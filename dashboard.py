import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, time as dtime, timedelta

from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data

# 🌐 Configure page
st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

AZ = pytz.timezone("America/Phoenix")


def at_midnight_az(d):
    """Return timezone-aware datetime at 00:00 of given date (Arizona)."""
    dt_naive = datetime.combine(d, dtime(0, 0, 0))
    return AZ.localize(dt_naive)


# 🔌 Load list of stations
stations = get_station_list()

if not stations:
    st.warning("⚠️ No stations with data available.")
else:
    # 🎛 Sidebar controls (returns controls dict with date range + intake area)
    station, selected_fields, controls = render_controls(stations)

    # 📥 Load raw data
    df_raw = load_station_data(station)

    if df_raw.empty:
        st.warning(f"⚠️ No data found for station: {station}")
    else:
        df_raw = df_raw.copy()
        df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"], errors="coerce")
        df_raw = df_raw.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        # Assume incoming UTC → convert to AZ if naive; otherwise TZ-convert to AZ
        if df_raw["timestamp"].dt.tz is None:
            df_raw["timestamp"] = df_raw["timestamp"].dt.tz_localize("UTC").dt.tz_convert(AZ)
        else:
            df_raw["timestamp"] = df_raw["timestamp"].dt.tz_convert(AZ)

        # ---------------- Build period flags from date range ----------------
        start_date = controls["date_start"]
        end_date = controls["date_end"]
        # range is [start_midnight, end_midnight_next_day)
        start_ts = at_midnight_az(start_date)
        end_ts_excl = at_midnight_az(end_date + timedelta(days=1))

        # counting only inside the period
        counting_mask = (df_raw["timestamp"] >= start_ts) & (df_raw["timestamp"] < end_ts_excl)

        # reset at the first row on/after start_ts
        reset_flag = pd.Series(False, index=df_raw.index)
        if counting_mask.any():
            first_idx = df_raw.index[(df_raw["timestamp"] >= start_ts)].min()
            reset_flag.loc[first_idx] = True

        df_raw["counting"] = counting_mask.values
        df_raw["reset_flag"] = reset_flag.values
        # no freeze in the simple UI
        df_raw["freeze_flag"] = False

        # 🧮 Process data (accumulations will start from zero at reset row; outside period not counted)
        df_processed = process_data(
            df_raw,
            intake_area=controls["intake_area"],
            lag_steps=10,  # keep your default
            reset_col="reset_flag",
            count_col="counting",
            freeze_col="freeze_flag",
            # session_col="station_id",  # enable if you have multiple devices in one feed
        )

        # 🕒 Display most recent update time within period (if any), else overall
        if counting_mask.any():
            latest_time = df_processed.loc[counting_mask, "timestamp"].max()
        else:
            latest_time = df_processed["timestamp"].max()
        st.markdown(f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 📊 Show dashboard
        render_data_section(df_processed[counting_mask].copy(), station, selected_fields)
