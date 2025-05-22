import streamlit as st
import pandas as pd

def render_controls(station_list):
    st.header("🔧 Controls")
    selected_station = st.selectbox("📍 Select Station", station_list)
    return selected_station

def render_data_section(df, station_id):
    st.title(f"📊 AWH Dashboard – {station_id}")

    if df.empty:
        st.warning("No data found.")
        return

    display_columns = [
        "timestamp",
        "harvesting_efficiency",
        "water_production",
        "current",
        "power",
        "intake_air_temperature (C)",
        "intake_air_humidity (%)",
        "intake_air_velocity (m/s)",
        "absolute_intake_air_humidity",
        "outtake_air_temperature (C)",
        "outtake_air_humidity (%)",
        "outtake_air_velocity (m/s)",
        "absolute_outtake_air_humidity"
    ]

    existing_columns = [col for col in display_columns if col in df.columns]

    st.dataframe(df[existing_columns], use_container_width=True)

    st.download_button(
        label="⬇️ Download Full Table as CSV",
        data=df[existing_columns].to_csv(index=False),
        file_name=f"{station_id}_processed_data.csv",
        mime="text/csv"
    )
