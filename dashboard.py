import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, timedelta

from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data

# 🌐 Configure page
st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

ARIZONA_TZ = pytz.timezone("America/Phoenix")

def _to_az(dt_series: pd.Series) -> pd.Series:
    if dt_series.dt.tz is None:
        return dt_series.dt.tz_localize("UTC").dt.tz_convert(ARIZONA_TZ)
    return dt_series.dt.tz_convert(ARIZONA_TZ)

@st.cache_data(show_spinner=False, ttl=60)
def compute_station_status(stations, lookback_min=10):
    status = {}
    last_seen = {}
    threshold = datetime.now(ARIZONA_TZ) - timedelta(minutes=lookback_min)

    for s in stations:
        try:
            df = load_station_data(s)
            if df.empty or "timestamp" not in df.columns:
                status[s] = False
                last_seen[s] = None
                continue

            ts = pd.to_datetime(df["timestamp"], errors="coerce").dropna()
            if ts.empty:
                status[s] = False
                last_seen[s] = None
                continue

            ts_az = _to_az(ts)
            latest = ts_az.max()
            last_seen[s] = latest
            status[s] = (latest >= threshold)
        except Exception:
            status[s] = False
            last_seen[s] = None

    return status, last_seen

# 🔌 Load list of stations
stations = get_station_list()
if not stations:
    st.warning("⚠️ No stations with data available.")
    st.stop()

# 🟢 Who is online in last 10 minutes
status, last_seen = compute_station_status(stations, lookback_min=10)
default_station = next((s for s in stations if status.get(s)), stations[0])

# 🧱 Top status bar
st.markdown("### 🔌 Station Status (last 10 minutes)")
cols = st.columns(min(4, len(stations)))
for i, s in enumerate(stations):
    with cols[i % len(cols)]:
        indicator = "🟢 **Online**" if status.get(s) else "🔴 Offline"
        seen_txt = "—"
        if last_seen.get(s) is not None:
            seen_txt = last_seen[s].strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(
            f"""
            <div style="padding:10px;border:1px solid #eee;border-radius:12px;">
              <div style="font-weight:600;margin-bottom:4px;">{s}</div>
              <div>{indicator}</div>
              <div style="font-size:12px;color:#6b7280;">Last seen: {seen_txt} (AZ)</div>
            </div>
            """,
            unsafe_allow_html=True
        )

st.divider()

# 🎛 Sidebar controls (backward compatible call)
try:
    station, selected_fields, intake_area = render_controls(
        station_list=stations,
        default_station=default_station,
        station_status=status,
        last_seen_map=last_seen,
    )
except TypeError:
    # fallback for old ui_display.py that only accepts (station_list)
    station, selected_fields, intake_area = render_controls(stations)

# 📥 Load data
df_raw = load_station_data(station)
if df_raw.empty:
    st.warning(f"⚠️ No data found for station: {station}")
    st.stop()

# 🧮 Process
df_processed = process_data(df_raw, intake_area=intake_area)

# ⏱️ Localize time to AZ
if df_processed["timestamp"].dt.tz is None:
    df_processed["timestamp"] = df_processed["timestamp"].dt.tz_localize("UTC").dt.tz_convert(ARIZONA_TZ)
else:
    df_processed["timestamp"] = df_processed["timestamp"].dt.tz_convert(ARIZONA_TZ)

# 🕒 Latest time + online badge
latest_time = df_processed["timestamp"].max()
badge = "🟢 **Online**" if status.get(station) else "🔴 Offline"
st.markdown(
    f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')} &nbsp;&nbsp; {badge}"
)

# 📊 Render
render_data_section(df_processed, station, selected_fields)
