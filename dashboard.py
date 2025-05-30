import streamlit as st
from firestore_loader import get_station_list, load_station_data
from data_play import process_data
from ui_display import render_controls, render_data_section

st.set_page_config(page_title="AWH Dashboard", layout="wide")

# Get list of stations
station_list = get_station_list()

# Handle case where no stations are found
if not station_list:
    st.error("🚫 No stations available in Firestore.")
    st.stop()

# Render sidebar and return selected station and field choices
selected_station, selected_fields = render_controls(station_list)

# Handle missing selection
if not selected_station:
    st.warning("Please select a station from the list.")
    st.stop()

# Load and process data
df_raw = load_station_data(selected_station)
df = process_data(df_raw)

# Display results
render_data_section(df, selected_station, selected_fields)
