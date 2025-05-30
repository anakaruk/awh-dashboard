import streamlit as st
from firestore_loader import get_station_list, load_station_data
from data_play import process_data
from ui_display import render_controls, render_data_section

# Set page layout and title
st.set_page_config(page_title="AWH Dashboard", layout="wide")

# Get list of stations from Firestore
station_list = get_station_list()

# Handle case where no stations are found
if not station_list:
    st.error("🚫 No stations available in Firestore.")
    st.stop()

# Render sidebar controls and retrieve user input
selected_station, selected_fields, intake_area = render_controls(station_list)

# Handle missing station selection
if not selected_station:
    st.warning("Please select a station from the list.")
    st.stop()

# Load raw data for the selected station
df_raw = load_station_data(selected_station)

# Process the data with intake area (used for harvesting efficiency)
df = process_data(df_raw, intake_area)

# Display results: tables and charts
render_data_section(df, selected_station, selected_fields)
