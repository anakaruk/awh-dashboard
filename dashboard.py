import streamlit as st
from firestore_loader import get_station_list, load_station_data
from data_play import process_data
from ui_display import render_controls, render_data_section

# Set up Streamlit app configuration
st.set_page_config(page_title="AWH Dashboard", layout="wide")

# Load station list and render sidebar controls
station_list = get_station_list()
selected_station, show_weight, show_power, show_temp = render_controls(station_list)

# Load and process data
df_raw = load_station_data(selected_station)
df = process_data(df_raw)

# Determine which fields to display
selected_fields = []
if show_weight and "weight" in df.columns:
    selected_fields.append("weight")
if show_power and "power" in df.columns:
    selected_fields.append("power")
if show_temp and "temperature" in df.columns:
    selected_fields.append("temperature")

# Render the main layout
render_data_section(df, selected_station, selected_fields)
