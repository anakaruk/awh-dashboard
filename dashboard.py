# dashboard.py — fast landing page (status only), heavy load after click
import random
import streamlit as st
import pandas as pd
import pytz
from datetime import datetime, timedelta

from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data

# ---------- Page setup ----------
st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

LOCAL_TZ = pytz.timezone("America/Phoenix")


# ---------- Firestore (status-only lightweight client) ----------
@st.cache_resource
def _get_db():
    """
    Minimal Firestore client for tiny reads (status only).
    Uses Streamlit secrets if present; if not, status will be skipped.
    """
    try:
        import os, json
        from google.cloud import firestore

        service_account_info = json.loads(st.secrets["gcp_service_account"])
        key_path = "/tmp/service_account.json"
        with open(key_path, "w") as f:
            json.dump(service_account_info, f)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        return firestore.Client()
    except Exception:
        return None

db = _get_db()


# ---------- Last-seen helpers (no full-load fallback) ----------
@st.cache_data(ttl=45)
def _last_seen_for_station_fast(station: str):
    """
    Return most-recent timestamp for a station (Arizona tz) using a single tiny query:
      stations/{station}/readings ORDER BY timestamp DESC LIMIT 1
    Absolutely no fallback to load-all.
    """
    if db is None:
        return None
    try:
        from google.cloud.firestore_v1 import Query

        ref = (
            db.collection("stations")
              .document(station)
              .collection("readings")
              .order_by("timestamp", direction=Query.DESCENDING)
              .limit(1)
        )
        docs = list(ref.stream())
        if not docs:
            return None

        d = docs[0].to_dict()
        ts = d.get("timestamp")
        if ts is None:
            return None

        ts = pd.to_datetime(ts, errors="coerce")
        if pd.isna(ts):
            return None

        # normalize to LOCAL_TZ
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC").tz_convert(LOCAL_TZ)
        else:
            ts = ts.tz_convert(LOCAL_TZ)
        return ts
    except Exception:
        return None


def _render_station_status(stations: list[str]):
    """Render an online/offline grid for all stations based on last 5 minutes."""
    st.subheader("Station Status (last 5 minutes)")
    now_local = pd.Timestamp.now(tz=LOCAL_TZ)

    # tiny per-station reads; no dataset loads
    last_seen_map = {s: _last_seen_for_station_fast(s) for s in stations}
    online_map = {
        s: bool(ts and (now_local - ts <= timedelta(minutes=5)))
        for s, ts in last_seen_map.items()
    }

    per_row = 4
    for i, s in enumerate(stations):
        if i % per_row == 0:
            cols = st.columns(per_row)
        with cols[i % per_row]:
            ts = last_seen_map[s]
            dot = "🟢" if online_map[s] else "🔴"
            st.markdown(f"**{s}** {dot}")
            st.caption(
                f"Last seen: {ts.strftime('%Y-%m-%d %H:%M:%S')} AZ" if ts else "Last seen: —"
            )

    st.divider()
    return online_map, last_seen_map


# ---------- Cached heavy loader wrapper (windowed, no sampling) ----------
@st.cache_data(ttl=120, show_spinner=False)
def _load_df_windowed(station: str, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
    """
    Ask loader for a time window if supported; otherwise load-all then filter.
    This runs ONLY after the user clicks 'Load & Plot'.
    """
    # Ensure tz-aware
    if start_dt.tzinfo is None:
        start_dt = start_dt.tz_localize(LOCAL_TZ)
    if end_dt.tzinfo is None:
        end_dt = end_dt.tz_localize(LOCAL_TZ)

    try:
        df = load_station_data(station, start_dt=start_dt, end_dt=end_dt)  # preferred, if supported
        if not isinstance(df, pd.DataFrame):
            df = pd.DataFrame()
    except TypeError:
        # Fallback only here (after click), not on landing
        df = load_station_data(station)
    except Exception as e:
        st.error(f"❌ Failed to load data: {e}")
        return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    # Ensure tz-aware timestamps (Arizona)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    try:
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize("UTC").dt.tz_convert(LOCAL_TZ)
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert(LOCAL_TZ)
    except Exception:
        pass

    # Final window filter
    df = df[(df["timestamp"] >= start_dt) & (df["timestamp"] <= end_dt)]
    return df


# ---------- Load station list & status header (fast path) ----------
stations = get_station_list()
if not stations:
    st.warning("No stations with data available.")
    st.stop()

_ = _render_station_status(stations)

# ---------- Sidebar controls ----------
# (render_controls returns None for station/intake_area until the user picks them)
station, selected_fields, intake_area, (start_date, end_date), controls = render_controls(stations)

# Require selections before doing anything heavy
if station is None or intake_area is None:
    st.info("👈 Please select a **station** and an **air intake area** in the sidebar to get started.")
    st.stop()

# ---------- Build time window (start-of-day to end-of-day or now) ----------
if end_date < start_date:
    start_date, end_date = end_date, start_date

start_dt = pd.Timestamp(start_date).tz_localize(LOCAL_TZ)
end_of_day = pd.Timestamp(end_date).tz_localize(LOCAL_TZ) + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
now_local = pd.Timestamp.now(tz=LOCAL_TZ)
end_dt = min(end_of_day, now_local)

# ---------- Load & Plot trigger ----------
if "ready_to_plot" not in st.session_state:
    st.session_state.ready_to_plot = False

col_left, col_right = st.columns([1, 3])
with col_left:
    load_btn = st.button("🚀 Load & Plot", type="primary")
with col_right:
    st.caption("Landing page uses tiny 'last update' reads only; big data loads happen after this click.")

if load_btn:
    st.session_state.ready_to_plot = True

# ---------- Heavy path (only after click) ----------
if not st.session_state.ready_to_plot:
    st.info("Select date range then press **Load & Plot** to fetch data and draw charts.")
    st.stop()

with st.spinner("Loading data..."):
    df_raw = _load_df_windowed(station, start_dt, end_dt)

if df_raw.empty:
    jokes = [
        "No drops yet — looks like the station took a coffee break ☕. Try a different date!",
        "Quieter than a cactus at noon 🌵😴. Pick another day or station on the left.",
        "We checked under every cloud… still dry! ☁️➡️💧 Try another date range.",
        "No data here, but the vibes are immaculate ✨. Adjust the dates and we’ll pour the graphs!",
    ]
    st.markdown("### 👋 Welcome!")
    st.success(random.choice(jokes))
    st.caption("Tip: set **Date period** to today or pick a different station in the sidebar.")
    st.stop()

# ---------- Process & display (no sampling involved) ----------
df_processed = process_data(
    df_raw,
    intake_area=float(intake_area),
    lag_steps=int(controls.get("lag_steps", 10)),
)

latest_time = df_processed["timestamp"].max()
st.markdown(f"**Last Updated (Local Time - Arizona):** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

render_data_section(df_processed, station, selected_fields)
