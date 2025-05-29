import streamlit as st
import json
from firebase_admin import credentials, initialize_app

# Initialize Firebase with Streamlit secrets (MUST be before any Firestore calls)
key_json = st.secrets["FIREBASE_JSON"]
cred = credentials.Certificate(json.loads(key_json))
initialize_app(cred)

from firestore_loader import get_station_list, load_station_data
from data_play import process_data
from ui_display import render_controls, render_data_section

st.set_page_config(page_title="AWH Dashboard", layout="wide")

# Get list of stations (now assumed to be station_name)
station_list = get_station_list()

# Handle case where no stations are found
if not station_list:
    st.error("🚫 No stations available in Firestore.")
    st.stop()

# Render sidebar and return selected station_name and field choices
selected_station_name, selected_fields = render_controls(station_list)

# Handle missing selection
if not selected_station_name:
    st.warning("Please select a station from the list.")
    st.stop()

# Load and process data
df_raw = load_station_data(selected_station_name)
df = process_data(df_raw)

# Display results
render_data_section(df, selected_station_name, selected_fields)
