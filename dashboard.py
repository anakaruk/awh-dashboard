import streamlit as st
from firestore_loader import get_station_list, load_station_data
from ui_display import render_controls, render_data_section
from data_play import process_data

# 🌐 Page configuration
st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Station Monitoring Dashboard")

# 🔌 Load list of available stations
stations = get_station_list()

if not stations:
    st.warning("⚠️ No stations with data available.")
else:
    # 🎛 Sidebar UI controls
    station, selected_fields, intake_area = render_controls(stations)

    # 🔄 Manual refresh support
    if "refresh_data" not in st.session_state:
        st.session_state.refresh_data = False

    if st.button("🔄 Refresh Data"):
        st.session_state.refresh_data = True
        st.stop()  # Stop current run and rerun on next cycle

    if st.session_state.refresh_data:
        st.session_state.refresh_data = False
        st.experimental_rerun()

    # 📥 Load Firestore data for selected station
    df_raw = load_station_data(station)
    st.write("✅ Raw data preview", df_raw.head())  # Debug line (optional)

    if df_raw.empty:
        st.warning(f"⚠️ No data found for station: {station}")
    else:
        # 🧮 Process data with calculations
        df_processed = process_data(df_raw, intake_area=intake_area)
        st.write("✅ Processed data preview", df_processed.head())  # Debug line (optional)

        # 🕓 Show most recent update time
        latest_time = df_processed["timestamp"].max()
        st.markdown(f"**Last Updated:** {latest_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 📊 Display results
        render_data_section(df_processed, station, selected_fields)
