# dashboard.py
import streamlit as st
from firestore_loader import load_station_data, get_station_list
from data_play import process_data
from ui_display import render_ui

st.set_page_config(page_title="AWH Dashboard", layout="wide")

# Sidebar controls
with st.sidebar:
    st.header("🔧 Controls")
    selected_station = st.selectbox("📍 Select Station", get_station_list())
    show_weight = st.checkbox("⚖️ Weight", value=False)
    show_power = st.checkbox("🔌 Power", value=False)
    show_temp = st.checkbox("🌡️ Intake Air Temp", value=False)

# Load and process data
df_raw = load_station_data(selected_station)
df = process_data(df_raw)

# Render layout
st.title(f"📊 AWH Dashboard – {selected_station}")
render_ui(df, selected_station, show_weight, show_power, show_temp)
