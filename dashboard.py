import streamlit as st
from firestore_loader import get_station_list, load_station_data
from data_play import process_data
from ui_display import render_controls, render_data_section
from datetime import datetime, timedelta
import pytz

# Set page layout
st.set_page_config(page_title="AWH Dashboard", layout="wide")

# Initialize session state
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = datetime.now()

# Auto refresh settings
AUTO_REFRESH_INTERVAL = 600  # seconds (10 minutes)

# Sidebar refresh section
with st.sidebar:
    st.markdown("### 🔄 Refresh Options")

    # Manual refresh button
    if st.button("🔄 Refresh Data Now"):
        st.session_state.last_refresh = datetime.now()
        st.rerun()

    # Display last refreshed time in local timezone
    local_tz = pytz.timezone("America/Phoenix")  # Change if needed
    local_time = st.session_state.last_refresh.astimezone(local_tz)
    last_time_str = local_time.strftime('%Y-%m-%d %H:%M:%S')
    st.markdown(f"🕒 Last refreshed: `{last_time_str}`")

# Auto refresh trigger (after rendering)
seconds_passed = int((datetime.now() - st.session_state.last_refresh).total_seconds())
if seconds_passed >= AUTO_REFRESH_INTERVAL:
    st.session_state.last_refresh = datetime.now()
    st.rerun()

# Load stations
station_list = get_station_list()
if not station_list:
    st.error("🚫 No stations available in Firestore.")
    st.stop()

# Sidebar controls
selected_station, selected_fields, intake_area = render_controls(station_list)
if not selected_station:
    st.warning("Please select a station from the list.")
    st.stop()

# Load + process data
df_raw = load_station_data(selected_station)
df = process_data(df_raw, intake_area)

# Display dashboard content
render_data_section(df, selected_station, selected_fields)
