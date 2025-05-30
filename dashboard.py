import streamlit as st
from firestore_loader import get_station_list, load_station_data
from data_play import process_data
from ui_display import render_controls, render_data_section
from datetime import datetime, timedelta

# Set page layout and title
st.set_page_config(page_title="AWH Dashboard", layout="wide")

# --- Initialize session state ---
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()

# --- Sidebar: Manual Refresh & Info ---
with st.sidebar:
    st.markdown("### 🔄 Refresh Options")

    if st.button("🔄 Refresh Data Now"):
        st.session_state.last_refresh = datetime.now()
        st.experimental_rerun()

    st.markdown(f"🕒 Last refreshed: `{st.session_state.last_refresh.strftime('%H:%M:%S')}`")
    refresh_in = 600 - int((datetime.now() - st.session_state.last_refresh).total_seconds())
    if refresh_in < 0:
        refresh_in = 0
    st.markdown(f"⏳ Auto refresh in: `{refresh_in}` seconds")

# --- Auto refresh trigger (safe) ---
refresh_due = datetime.now() - st.session_state.last_refresh > timedelta(minutes=10)

# --- Load Station List ---
station_list = get_station_list()

if not station_list:
    st.error("🚫 No stations available in Firestore.")
    st.stop()

# --- Sidebar Controls ---
selected_station, selected_fields, intake_area = render_controls(station_list)

if not selected_station:
    st.warning("Please select a station from the list.")
    st.stop()

# --- Load and Process Data ---
df_raw = load_station_data(selected_station)
df = process_data(df_raw, intake_area)

# --- Display Dashboard ---
render_data_section(df, selected_station, selected_fields)

# --- Trigger rerun at the end only if due ---
if refresh_due:
    st.session_state.last_refresh = datetime.now()
    st.experimental_rerun()
