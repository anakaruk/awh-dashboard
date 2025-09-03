import streamlit as st
import pandas as pd
import pytz

from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data  # unchanged

# Page setup
st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

LOCAL_TZ = pytz.timezone("America/Phoenix")


def _to_local_tz(ts: pd.Series) -> pd.Series:
    """Ensure timestamps are tz-aware and converted to Arizona time."""
    if ts.dt.tz is None:
        return ts.dt.tz_localize("UTC").dt.tz_convert(LOCAL_TZ)
    return ts.dt.tz_convert(LOCAL_TZ)


def _safe_process(df_raw: pd.DataFrame, intake_area: float) -> pd.DataFrame:
    """
    Call process_data normally. If it fails, fall back to a minimal pass-through
    so the UI still works. This does NOT modify your data_play.py.
    """
    try:
        return process_data(df_raw, intake_area=intake_area)
    except Exception as e:
        st.warning(f"Processing failed, showing minimal data only. Details: {type(e).__name__}")
        df = df_raw.copy()

        # Ensure timestamp column exists and is usable
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        else:
            # If no timestamp, create a dummy one so the app can render
            df["timestamp"] = pd.Timestamp.utcnow().tz_localize("UTC")

        return df


# Load station list
stations = get_station_list()
if not stations:
    st.warning("No stations with data available.")
    st.stop()

# Sidebar controls
station, selected_fields, intake_area = render_controls(stations)

# Load data for selected station
df_raw = load_station_data(station)
if df_raw.empty:
    st.warning(f"No data found for station: {station}")
    st.stop()

# Process (with safe fallback)
df_processed = _safe_process(df_raw, intake_area=intake_area)

# Convert to local timezone
if "timestamp" not in df_processed.columns:
    st.warning("Processed data has no 'timestamp' column; showing raw timestamps.")
else:
    df_processed["timestamp"] = _to_local_tz(pd.to_datetime(df_processed["timestamp"], errors="coerce"))

# Default date filter: today 00:00 → now (Arizona time)
today_start = pd.Timestamp.now(tz=LOCAL_TZ).normalize()
now_local = pd.Timestamp.now(tz=LOCAL_TZ)

df_processed = df_processed[
    (df_processed["timestamp"] >= today_start) & (df_processed["timestamp"] <= now_local)
]

if df_processed.empty:
    st.info("No data for today yet (00:00 to now).")
    st.stop()

# Last updated stamp
latest_time = df_processed["timestamp"].max()
st.markdown(f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

# Render main section
render_data_section(df_processed, station, selected_fields)
