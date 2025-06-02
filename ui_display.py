import streamlit as st
import pandas as pd
import altair as alt

def render_controls(station_list):
    st.sidebar.header("🔧 Controls")
    selected_station_name = st.sidebar.selectbox("📍 Select Station", station_list)

    intake_area_options = {
        "DewStand 1: 0.0507 m²": 0.0507,
        "T50 1: 0.18 m²": 0.18
    }

    intake_area_label = st.sidebar.selectbox("🧮 Intake Area (m²)", list(intake_area_options.keys()))
    intake_area = intake_area_options[intake_area_label]

    # Sidebar checkboxes (label, corresponding column name)
    field_options = [
        ("❄️ Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("💧 Water Production (L)", "water_production"),
        ("🔋 Energy Per Liter (kW.hr/L)", "energy_per_liter (kWh/L)"),
        ("🔋 Power Consumption (kW.hr)", "accumulated_energy (kWh)"),
        ("🌫️ Abs. Intake humidity (g/m3)", "absolute_intake_air_humidity"),
        ("🌫️ Abs. Outtake humidity (g/m3)", "absolute_outtake_air_humidity"),
        ("🌡️ Intake temperature (°C)", "intake_air_temperature (C)"),
        ("💨 Intake humidity (%)", "intake_air_humidity (%)"),
        ("↘ Intake velocity (m/s)", "intake_air_velocity (m/s)"),
        ("🔥 Outtake temperature (°C)", "outtake_air_temperature (C)"),
        ("💨 Outtake humidity (%)", "outtake_air_humidity (%)"),
        ("↗ Outtake velocity (m/s)", "outtake_air_velocity (m/s)"),
        ("🔌 Current (A)", "current"),
        ("⚡ Power (W)", "power")
    ]

    selected_fields = ["timestamp"]
    for label, field in field_options:
        if st.sidebar.checkbox(label, value=(field == "harvesting_efficiency")):
            selected_fields.append(field)

    return selected_station_name, selected_fields, intake_area

def render_data_section(df, station_name, selected_fields):
    st.title(f"📊 AWH Dashboard – {station_name}")

    if df.empty:
        st.warning("No data found for this station.")
        return

    df_sorted = df.sort_values("timestamp").copy()
    df_sorted["Date"] = df_sorted["timestamp"].dt.date
    df_sorted["Time"] = df_sorted["timestamp"].dt.strftime("%H:%M:%S")

    available_fields = [col for col in selected_fields if col in df_sorted.columns and col != "timestamp"]

    for field in available_fields:
        st.subheader(f"📊 `{field}` Overview")
        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### 📋 Table")
            st.dataframe(df_sorted[["Date", "Time", field]], use_container_width=True)

            st.download_button(
                label=f"⬇️ Download `{field}` CSV",
                data=df_sorted[["Date", "Time", field]].to_csv(index=False),
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv"
            )

        with col2:
            st.markdown("#### 📈 Scatter Plot")
            y_axis = alt.Y(
                field,
                title=field,
                scale=alt.Scale(domain=[0, 50]) if field == "harvesting_efficiency" else alt.Undefined
            )

            chart = alt.Chart(df_sorted).mark_circle(size=60).encode(
                x=alt.X("Time:N", title="Time"),
                y=y_axis,
                tooltip=["Date", "Time", field]
            ).properties(width="container", height=300)

            st.altair_chart(chart, use_container_width=True)
