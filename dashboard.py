import streamlit as st
import pandas as pd
import pytz

from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data  # unchanged

st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

LOCAL_TZ = pytz.timezone("America/Phoenix")


def _to_local_tz(ts: pd.Series) -> pd.Series:
    """Ensure timestamps are tz-aware and converted to Arizona time."""
    ts = pd.to_datetime(ts, errors="coerce")
    if ts.dt.tz is None:
        ts = ts.dt.tz_localize("UTC")
    return ts.dt.tz_convert(LOCAL_TZ)


def _safe_process(df_raw: pd.DataFrame, intake_area: float) -> pd.DataFrame:
    """Run process_data; if it fails, fall back to a minimal pass-through."""
    try:
        return process_data(df_raw, intake_area=intake_area)
    except Exception as e:
        st.warning(f"Processing failed, showing minimal data only. Details: {type(e).__name__}")
        df = df_raw.copy()
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        else:
            df["timestamp"] = pd.Timestamp.utcnow().tz_localize("UTC")
        return df


# Load stations
stations = get_station_list()
if not stations:
    st.warning("No stations with data available.")
    st.stop()

# Sidebar controls (now returns date range too)
station, selected_fields, intake_area, (start_date, end_date) = render_controls(stations)

# Load & process
df_raw = load_station_data(station)
if df_raw.empty:
    st.warning(f"No data found for station: {station}")
    st.stop()

df_processed = _safe_process(df_raw, intake_area=intake_area)

# Local timezone
df_processed["timestamp"] = _to_local_tz(df_processed["timestamp"])

# Date range filter: start 00:00 to min(end-of-day, now)
start_dt = pd.Timestamp(start_date).tz_localize(LOCAL_TZ)
end_of_day = pd.Timestamp(end_date).tz_localize(LOCAL_TZ) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
now_local = pd.Timestamp.now(tz=LOCAL_TZ)
end_dt = min(end_of_day, now_local)

df_processed = df_processed[(df_processed["timestamp"] >= start_dt) & (df_processed["timestamp"] <= end_dt)]

if df_processed.empty:
    st.info("No data in the selected date range.")
    st.stop()

latest_time = df_processed["timestamp"].max()
st.markdown(f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

render_data_section(df_processed, station, selected_fields)
