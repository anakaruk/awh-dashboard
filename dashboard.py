import streamlit as st
import pandas as pd
import pytz
from datetime import timedelta

from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data

# Page setup
st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

LOCAL_TZ = pytz.timezone("America/Phoenix")


def _resample_df(df: pd.DataFrame, rule: str | None) -> pd.DataFrame:
    """Downsample raw sensor data safely (mean for most, last for cumulative/status)."""
    if not rule:
        return df
    df = df.copy().sort_values("timestamp")
    df = df.set_index("timestamp")

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    prefer_last = {"weight", "water_production_raw", "pump_status", "state", "status", "current_session"}

    agg_map = {}
    for c in numeric_cols:
        agg_map[c] = "last" if (c in prefer_last or c.lower() in prefer_last) else "mean"

    out = df.resample(rule, label="right", closed="right").agg(agg_map)
    out = out.reset_index()
    return out


@st.cache_data(ttl=180, show_spinner=False)
def get_processed(
    station: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    intake_area: float,
    lag_steps: int,
    resample_rule: str | None,
) -> pd.DataFrame:
    """Load → tz-convert → filter → resample → process; cached by parameters."""
    raw = load_station_data(station)
    if raw is None or raw.empty:
        return pd.DataFrame()

    df = raw.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC").dt.tz_convert(LOCAL_TZ)
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert(LOCAL_TZ)

    # Date window (inclusive day range)
    start_dt = pd.Timestamp(start_date).tz_localize(LOCAL_TZ)
    end_of_day = pd.Timestamp(end_date).tz_localize(LOCAL_TZ) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    now_local = pd.Timestamp.now(tz=LOCAL_TZ)
    end_dt = min(end_of_day, now_local)

    df = df[(df["timestamp"] >= start_dt) & (df["timestamp"] <= end_dt)]
    if df.empty:
        return df

    # Downsample
    df = _resample_df(df, resample_rule)

    # Process metrics
    return process_data(df, intake_area=float(intake_area), lag_steps=int(lag_steps))


# ---------------------- Page flow ----------------------
stations = get_station_list()
if not stations:
    st.warning("No stations with data available.")
    st.stop()

station, selected_fields, intake_area, (start_date, end_date), controls = render_controls(stations)

# guard placeholders
if not station or intake_area is None:
    st.info("👋 Please select a **station** and **intake area** in the sidebar to begin.")
    st.stop()

# normalize dates
if end_date < start_date:
    start_date, end_date = end_date, start_date

df_processed = get_processed(
    station=station,
    start_date=start_date,
    end_date=end_date,
    intake_area=intake_area,
    lag_steps=controls.get("lag_steps", 10),
    resample_rule=controls.get("resample_rule"),
)

if df_processed.empty:
    st.info("No data in the selected date range.")
    st.stop()

latest_time = df_processed["timestamp"].max()
st.markdown(f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

render_data_section(df_processed, station, selected_fields)
