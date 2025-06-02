import streamlit as st
import pandas as pd
import altair as alt

def render_controls(station_list):
    st.sidebar.header("\U0001F527 Controls")
    selected_station_name = st.sidebar.selectbox("\U0001F4CD Select Station", station_list)

    # Initialize session state for intake areas if not already
    if "intake_areas" not in st.session_state:
        st.session_state.intake_areas = {}

    # Retrieve or set default intake area for the selected station
    default_area = st.session_state.intake_areas.get(selected_station_name, 1.0)

    # Input for intake area per station
    intake_area = st.sidebar.number_input(
        "\U0001F9EE Intake Area (m²)",
        min_value=0.01,
        max_value=100.0,
        value=default_area,
        step=0.01
    )
    st.session_state.intake_areas[selected_station_name] = intake_area

    # Field checkboxes
    show_eff = st.sidebar.checkbox("\u2699\ufe0f Harvesting Efficiency", value=True)
    show_prod = st.sidebar.checkbox("\U0001F4A7 Water Production", value=True)
    show_power_consumption = st.sidebar.checkbox("\U0001F50B Power Consumption (kWh)", value=True)
    show_energy_per_liter = st.sidebar.checkbox("\U0001F50B Energy per Liter (kWh/L)", value=True)
    show_current = st.sidebar.checkbox("\U0001F50C Current", value=True)
    show_power = st.sidebar.checkbox("\u26A1 Power", value=True)
    show_temp_in = st.sidebar.checkbox("\U0001F321\ufe0f Intake Temp", value=True)
    show_humid_in = st.sidebar.checkbox("\U0001F4A8 Intake Humidity", value=True)
    show_velocity_in = st.sidebar.checkbox("\u2198 Intake Velocity", value=True)
    show_abs_in = st.sidebar.checkbox("\U0001F32B\ufe0f Abs Intake Humidity", value=True)
    show_temp_out = st.sidebar.checkbox("\U0001F525 Outtake Temp", value=True)
    show_humid_out = st.sidebar.checkbox("\U0001F4A8 Outtake Humidity", value=True)
    show_velocity_out = st.sidebar.checkbox("\u2197 Outtake Velocity", value=True)
    show_abs_out = st.sidebar.checkbox("\U0001F32B\ufe0f Abs Outtake Humidity", value=True)

    selected_fields = ["timestamp"]
    if show_eff: selected_fields.append("harvesting_efficiency")
    if show_prod: selected_fields.append("water_production")
    if show_power_consumption: selected_fields.append("accumulated_energy (kWh)")
    if show_energy_per_liter: selected_fields.append("energy_per_liter (kWh/L)")
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

    return selected_station_name, selected_fields, intake_area

def render_data_section(df, station_name, selected_fields):
    st.title(f"📊 AWH Dashboard – {station_name}")

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
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv"
            )

        with col2:
            st.markdown("#### 📈 Scatter Plot")
            df_sorted = df.sort_values("timestamp")
            chart = alt.Chart(df_sorted).mark_circle(size=60).encode(
                x='timestamp:T',
                y=alt.Y(field, title=field),
                tooltip=['timestamp', field]
            ).properties(width="container", height=300)

            st.altair_chart(chart, use_container_width=True)
