from firestore_loader import get_station_list, load_station_data
from data_play import process_data
from ui_display import render_controls, render_data_section
import streamlit as st

st.set_page_config(page_title="AWH Dashboard", layout="wide")

station_list = get_station_list()
selected_station = render_controls(station_list)

df_raw = load_station_data(selected_station)
df = process_data(df_raw)

render_data_section(df, selected_station)
