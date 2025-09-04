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
    if not isinstance(time_obj, dtime):
        time_obj = dtime(0, 0, 0)
    dt_naive = datetime.combine(date_obj, time_obj)
    return local_tz.localize(dt_naive)


# 🔌 Load list of stations
stations = get_station_list()

if not stations:
    st.warning("⚠️ No stations with data available.")
else:
    # 🎛 Sidebar controls (unpack ให้ตรงกับ ui_display)
    station, selected_fields, intake_area, (start_date, end_date), controls = render_controls(stations)

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
        end_of_day = pd.Timestamp(end_date).tz_localize(local_tz) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        now_local = pd.Timestamp.now(tz=local_tz)
        end_dt = min(end_of_day, now_local)

        df_raw = df_raw[(df_raw["timestamp"] >= start_dt) & (df_raw["timestamp"] <= end_dt)]

        if df_raw.empty:
            st.info("⚠️ No data in the selected date range.")
            st.stop()

        # ---------------- Build control flags ----------------
        df_flags = pd.DataFrame(index=df_raw.index)
        df_flags["reset_flag"] = False
        df_flags["counting"] = True
        df_flags["freeze_flag"] = False

        # Reset from
        if controls.get("apply_reset"):
            reset_ts = combine_dt(controls.get("reset_date"), controls.get("reset_time"))
            if reset_ts is not None:
                mask = df_raw["timestamp"] >= reset_ts
                if mask.any():
                    first_idx = df_raw.index[mask].min()
                    df_flags.loc[first_idx, "reset_flag"] = True

        # Pause window
        if controls.get("apply_pause"):
            start_ts = combine_dt(controls.get("pause_start_date"), controls.get("pause_start_time"))
            end_ts = combine_dt(controls.get("pause_end_date"), controls.get("pause_end_time"))
            if (start_ts is not None) and (end_ts is not None) and (end_ts >= start_ts):
                pmask = (df_raw["timestamp"] >= start_ts) & (df_raw["timestamp"] <= end_ts)
                df_flags.loc[pmask, "counting"] = False

        # Freeze from
        if controls.get("apply_freeze"):
            freeze_ts = combine_dt(controls.get("freeze_date"), controls.get("freeze_time"))
            if freeze_ts is not None:
                fmask = df_raw["timestamp"] >= freeze_ts
                if fmask.any():
                    first_fidx = df_raw.index[fmask].min()
                    df_flags.loc[first_fidx, "freeze_flag"] = True

        # Merge flags into raw df
        df_raw["reset_flag"] = df_flags["reset_flag"].values
        df_raw["counting"] = df_flags["counting"].values
        df_raw["freeze_flag"] = df_flags["freeze_flag"].values

        # 🧮 Process data with controls
        df_processed = process_data(
            df_raw,
            intake_area=intake_area,
            lag_steps=controls["lag_steps"],
            reset_col="reset_flag",
            count_col="counting",
            freeze_col="freeze_flag",
        )

        # 🕒 Display most recent update time (safe check)
        if not df_processed.empty:
            latest_time = df_processed["timestamp"].max()
            st.markdown(
                f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )

        # 📊 Show dashboard
        render_data_section(df_processed, station, selected_fields)
