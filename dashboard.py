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


@st.cache_data(ttl=60)
def _last_seen_for_station(station: str):
    """
    Return the most recent timestamp for a station, timezone-aware (Arizona).
    Tries a lightweight read (if your loader supports it); otherwise falls back
    to a normal load. Cached for 60s to avoid repeated reads.
    """
    # Try: if your loader accepts limit/order kwargs (safe no-op if not supported)
    try:
        df_try = load_station_data(station, limit=1, order="desc")  # optional fast path
        if isinstance(df_try, pd.DataFrame) and not df_try.empty and "timestamp" in df_try:
            ts = pd.to_datetime(df_try["timestamp"], errors="coerce").max()
            if pd.notna(ts):
                if ts.tzinfo is None:
                    ts = ts.tz_localize("UTC").tz_convert(LOCAL_TZ)
                else:
                    ts = ts.tz_convert(LOCAL_TZ)
                return ts
    except TypeError:
        # Fallback path when extra kwargs aren't supported
        pass
    except Exception:
        pass

    # Fallback: normal load
    df = load_station_data(station)
    if isinstance(df, pd.DataFrame) and not df.empty and "timestamp" in df:
        ts = pd.to_datetime(df["timestamp"], errors="coerce").max()
        if pd.notna(ts):
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC").tz_convert(LOCAL_TZ)
            else:
                ts = ts.tz_convert(LOCAL_TZ)
            return ts
    return None


def _render_station_status(stations: list[str]):
    """Render an online/offline grid for all stations based on last 5 minutes."""
    st.subheader("Station Status (last 5 minutes)")
    now_local = pd.Timestamp.now(tz=LOCAL_TZ)

    # Build maps
    last_seen_map = {s: _last_seen_for_station(s) for s in stations}
    online_map = {}
    for s, ts in last_seen_map.items():
        online_map[s] = bool(ts and (now_local - ts <= timedelta(minutes=5)))

    # Grid of 4 columns per row
    per_row = 4
    for i, s in enumerate(stations):
        if i % per_row == 0:
            cols = st.columns(per_row)
        with cols[i % per_row]:
            ts = last_seen_map[s]
            online = online_map[s]
            dot = "🟢" if online else "🔴"
            st.markdown(f"**{s}** {dot}")
            if ts is not None:
                st.caption(f"Last seen: {ts.strftime('%Y-%m-%d %H:%M:%S')} AZ")
            else:
                st.caption("Last seen: —")

    st.divider()
    return online_map, last_seen_map


# Load station list
stations = get_station_list()
if not stations:
    st.warning("No stations with data available.")
    st.stop()

# Status header (online/offline + last update)
online_map, last_seen_map = _render_station_status(stations)

# Sidebar controls (kept simple; defaults to today 00:00 → now)
station, selected_fields, intake_area, (start_date, end_date), controls = render_controls(stations)

# Load data for selected station
df_raw = load_station_data(station)
if df_raw.empty:
    st.warning(f"No data found for station: {station}")
    st.stop()

# Ensure tz-aware timestamps in Arizona time
df_raw = df_raw.copy()
df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"], errors="coerce")
df_raw = df_raw.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
if df_raw["timestamp"].dt.tz is None:
    df_raw["timestamp"] = df_raw["timestamp"].dt.tz_localize("UTC").dt.tz_convert(LOCAL_TZ)
else:
    df_raw["timestamp"] = df_raw["timestamp"].dt.tz_convert(LOCAL_TZ)

# Date filter: today 00:00 → now (the date input in UI already defaults to today)
if end_date < start_date:
    start_date, end_date = end_date, start_date

start_dt = pd.Timestamp(start_date).tz_localize(LOCAL_TZ)
end_of_day = pd.Timestamp(end_date).tz_localize(LOCAL_TZ) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
now_local = pd.Timestamp.now(tz=LOCAL_TZ)
end_dt = min(end_of_day, now_local)

df_raw = df_raw[(df_raw["timestamp"] >= start_dt) & (df_raw["timestamp"] <= end_dt)]
if df_raw.empty:
    st.info("No data in the selected date range.")
    st.stop()

# Process data (clean version)
df_processed = process_data(
    df_raw,
    intake_area=float(intake_area),
    lag_steps=int(controls.get("lag_steps", 10)),  # default 10
)

# Last updated display
latest_time = df_processed["timestamp"].max()
st.markdown(f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

# Main charts/tables
render_data_section(df_processed, station, selected_fields)
