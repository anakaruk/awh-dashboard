# ui_display.py — no top metrics; plots HE only up to 50%
import streamlit as st
import pandas as pd
import numpy as np

try:
    import altair as alt
    _ALT_OK = True
except Exception:
    _ALT_OK = False


def render_controls(station_list):
    st.sidebar.header("🔧 Controls")

    # Station
    station_placeholder = "— Please select station —"
    station_options = [station_placeholder] + list(station_list)
    station_choice = st.sidebar.selectbox("📍 Select Station", station_options, index=0)
    selected_station = None if station_choice == station_placeholder else station_choice

    # Intake area
    intake_area_map = {
        "AquaPars 1: 0.12 m²": 0.12,
        "DewStand 1: 0.04 m²": 0.04,
        "T50 1: 0.18 m²": 0.18,
    }
    intake_placeholder = "— Please select intake area —"
    intake_labels = [intake_placeholder] + list(intake_area_map.keys())
    intake_choice = st.sidebar.selectbox("🧲 Intake Area (m²)", intake_labels, index=0)
    intake_area = None if intake_choice == intake_placeholder else float(intake_area_map[intake_choice])

    # Dates
    st.sidebar.subheader("📅 Date period")
    today = pd.Timestamp.now().date()
    start_date = st.sidebar.date_input("Start date", today)
    end_date = st.sidebar.date_input("End date", today)
    if end_date < start_date:
        st.sidebar.warning("End date is before start date. The app will swap them for you.")

    # Fields
    field_options = [
        ("❄️ Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("💧 Water Production (L)", "water_production"),
        ("🧪 Total volume (L)", "flow_total (L)"),
        ("🚿 Flow rate (L/min)", "flow_rate (L/min)"),
        ("🔋 Energy Per Liter (kWh/L)", "energy_per_liter (kWh/L)"),
        ("🔋 Power Consumption (kWh)", "accumulated_energy (kWh)"),
        ("🌫️ Abs. Intake humidity (g/m³)", "absolute_intake_air_humidity"),
        ("🌫️ Abs. Outtake humidity (g/m³)", "absolute_outtake_air_humidity"),
        ("🌡️ Intake temperature (°C)", "intake_air_temperature (C)"),
        ("💨 Intake humidity (%)", "intake_air_humidity (%)"),
        ("↘ Intake velocity (m/s)", "intake_air_velocity (m/s)"),
        ("🔥 Outtake temperature (°C)", "outtake_air_temperature (C)"),
        ("💨 Outtake humidity (%)", "outtake_air_humidity (%)"),
        ("↗ Outtake velocity (m/s)", "outtake_air_velocity (m/s)"),
        ("🔌 Current (A)", "current"),
        ("⚡ Power (W)", "power"),
        ("🟢 Pump status (0/1)", "pump_status"),
    ]

    selected_fields = ["timestamp"]
    for label, col in field_options:
        default_checked = (col == "harvesting_efficiency")
        if st.sidebar.checkbox(label, value=default_checked):
            selected_fields.append(col)

    if not _ALT_OK:
        st.sidebar.info("Altair not installed — using fallback charts.")

    controls = {"lag_steps": 10}
    return selected_station, selected_fields, intake_area, (start_date, end_date), controls


def render_data_section(df, station_name, selected_fields):
    title = f"📊 AWH Dashboard – {station_name}" if station_name else "📊 AWH Dashboard"
    st.title(title)

    if df.empty:
        st.warning("No data found for this station.")
        return

    available_fields = [c for c in selected_fields if c in df.columns and c != "timestamp"]

    df_sorted = df.sort_values("timestamp").copy()
    df_sorted["Date"] = df_sorted["timestamp"].dt.date
    df_sorted["Time"] = df_sorted["timestamp"].dt.strftime("%H:%M:%S")

    for field in available_fields:
        st.subheader(f"📊 {field} Overview")

        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### 📋 Table")
            table_view = df_sorted[["Date", "Time", field]].copy()
            st.dataframe(table_view, use_container_width=True)
            st.download_button(
                label=f"⬇️ Download {field} CSV",
                data=table_view.to_csv(index=False),
                file_name=f"{(station_name or 'station').replace(' ', '_')}_{field.replace(' ', '_')}.csv",
                mime="text/csv",
            )

        with col2:
            st.markdown("#### 📈 Plot")

            plot_data = df_sorted[["timestamp", field]].copy()
            plot_data[field] = pd.to_numeric(plot_data[field], errors="coerce")
            plot_data.replace([np.inf, -np.inf], np.nan, inplace=True)

            # For harvesting_efficiency: only plot 0–50%
            if field == "harvesting_efficiency":
                plot_data = plot_data[(plot_data[field] >= 0) & (plot_data[field] <= 50)]

            plot_data.dropna(subset=[field], inplace=True)

            if plot_data.empty:
                st.info(f"⚠️ No data available to plot for **{field}**.")
                continue

            if _ALT_OK:
                y_scale = alt.Undefined
                if field == "harvesting_efficiency":
                    y_scale = alt.Scale(domain=[0, 50])
                elif field == "pump_status":
                    y_scale = alt.Scale(domain=[-0.1, 1.1])

                # choose mark
                if field in ("flow_total (L)", "water_production", "accumulated_energy (kWh)"):
                    chart = (
                        alt.Chart(plot_data)
                        .mark_line()
                        .encode(
                            x=alt.X("timestamp:T", title="Date & Time",
                                    axis=alt.Axis(format="%Y-%m-%d %H:%M", labelAngle=-45)),
                            y=alt.Y(field, title=field, scale=y_scale),
                            tooltip=["timestamp:T", field],
                        )
                        .properties(width="container", height=300)
                        .interactive()
                    )
                elif field == "pump_status":
                    chart = (
                        alt.Chart(plot_data)
                        .mark_line(interpolate="step-after")
                        .encode(
                            x=alt.X("timestamp:T", title="Date & Time",
                                    axis=alt.Axis(format="%Y-%m-%d %H:%M", labelAngle=-45)),
                            y=alt.Y(field, title=field, scale=y_scale),
                            tooltip=["timestamp:T", field],
                        )
                        .properties(width="container", height=300)
                        .interactive()
                    )
                else:
                    chart = (
                        alt.Chart(plot_data)
                        .mark_circle(size=20, opacity=0.75)
                        .encode(
                            x=alt.X("timestamp:T", title="Date & Time",
                                    axis=alt.Axis(format="%Y-%m-%d %H:%M", labelAngle=-45)),
                            y=alt.Y(field, title=field, scale=y_scale),
                            tooltip=["timestamp:T", field],
                        )
                        .properties(width="container", height=300)
                        .interactive()
                    )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.line_chart(plot_data.set_index("timestamp")[[field]], use_container_width=True)
