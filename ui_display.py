import streamlit as st
import pandas as pd

def render_controls(station_list):
    st.sidebar.header("🔧 Controls")
    selected_station = st.sidebar.selectbox("📍 Select Station", station_list)

    # Field checkboxes
    show_eff = st.sidebar.checkbox("⚙️ Harvesting Efficiency", value=True)
    show_prod = st.sidebar.checkbox("💧 Water Production", value=True)
    show_current = st.sidebar.checkbox("🔌 Current", value=True)
    show_power = st.sidebar.checkbox("⚡ Power", value=True)
    show_temp_in = st.sidebar.checkbox("🌡️ Intake Temp", value=True)
    show_humid_in = st.sidebar.checkbox("💨 Intake Humidity", value=True)
    show_velocity_in = st.sidebar.checkbox("↘ Intake Velocity", value=True)
    show_abs_in = st.sidebar.checkbox("🌫️ Abs Intake Humidity", value=True)
    show_temp_out = st.sidebar.checkbox("🔥 Outtake Temp", value=True)
    show_humid_out = st.sidebar.checkbox("💨 Outtake Humidity", value=True)
    show_velocity_out = st.sidebar.checkbox("↗ Outtake Velocity", value=True)
    show_abs_out = st.sidebar.checkbox("🌫️ Abs Outtake Humidity", value=True)

    selected_fields = ["timestamp"]
    if show_eff: selected_fields.append("harvesting_efficiency")
    if show_prod: selected_fields.append("water_production")
    if show_current: selected_fields.append("current")
    if show_power: selected_fields.append("power")
    if show_temp_in: selected_fields.append("intake_air_temperature (C)")
    if show_humid_in: selected_fields.append("intake_air_humidity (%)")
    if show_velocity_in: selected_fields.append("intake_air_velocity (m/s)")
    if show_abs_in: selected_fields.append("absolute_intake_air_humidity")
    if show_temp_out: selected_fields.append("outtake_air_temperature (C)")
    if show_humid_out: selected_fields.append("outtake_air_humidity (%)")
    if show_velocity_out: selected_fields.append("outtake_air_velocity (m/s)")
    if show_abs_out: selected_fields.append("absolute_outtake_air_humidity")

    return selected_station, selected_fields


def render_data_section(df, station_id, selected_fields):
    st.title(f"📊 AWH Dashboard – {station_id}")

    if df.empty:
        st.warning("No data found for this station.")
        return

    available_fields = [col for col in selected_fields if col in df.columns and col != "timestamp"]

    for field in available_fields:
        st.subheader(f"📊 `{field}` Overview")

        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### 📋 Table")
            st.dataframe(df[["timestamp", field]], use_container_width=True)

            st.download_button(
                label=f"⬇️ Download `{field}` CSV",
                data=df[["timestamp", field]].to_csv(index=False),
                file_name=f"{station_id}_{field}.csv",
                mime="text/csv"
            )

        with col2:
            st.markdown("#### 📈 Plot")
            df_sorted = df.sort_values("timestamp")
            st.line_chart(df_sorted.set_index("timestamp")[field])
