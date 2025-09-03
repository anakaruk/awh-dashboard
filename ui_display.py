import streamlit as st
import pandas as pd
import altair as alt

def _status_chip(name: str, is_online: bool, last_seen_text: str) -> str:
    dot = "🟢" if is_online else "🔴"
    return f"{name}  {dot}"

def render_controls(station_list, default_station=None, station_status=None, last_seen_map=None):
    """
    เพิ่ม:
      - default_station: เลือกสถานีเริ่มต้น (ใช้ตัวที่ออนไลน์เป็นค่าเริ่มต้นจาก dashboard.py)
      - station_status, last_seen_map: dict สำหรับแสดงจุดสถานะใน selectbox
    """
    station_status = station_status or {}
    last_seen_map = last_seen_map or {}

    st.sidebar.header("🔧 Controls")

    # เตรียม label ให้ selectbox มีจุดสถานะหน้า station
    labels = []
    value_to_label = {}
    for s in station_list:
        last_txt = last_seen_map.get(s).strftime("%Y-%m-%d %H:%M:%S") + " AZ" if last_seen_map.get(s) is not None else "—"
        lbl = _status_chip(s, station_status.get(s, False), last_txt)
        labels.append(lbl)
        value_to_label[s] = lbl

    # index ของ default
    if default_station in station_list:
        default_index = station_list.index(default_station)
    else:
        default_index = 0

    selected_label = st.sidebar.selectbox(
        "📍 Select Station",
        options=labels,
        index=default_index,
        help="สถานีที่ขึ้น 🟢 คือมีข้อมูลเข้ามาภายใน 10 นาทีล่าสุด"
    )

    # map label กลับเป็นชื่อสถานี
    selected_station_name = station_list[labels.index(selected_label)]

    intake_area_options = {
        "AquaPars 1: 0.12 m²": 0.12,
        "DewStand 1: 0.04 m²": 0.04,
        "T50 1: 0.18 m²": 0.18
    }

    intake_area_label = st.sidebar.selectbox("🧲 Intake Area (m²)", list(intake_area_options.keys()))
    intake_area = intake_area_options[intake_area_label]

    st.sidebar.markdown("---")
    st.sidebar.subheader("Date period")
    # (ถ้าต้องการ date range filter จริง ๆ สามารถเพิ่ม widget และนำไปใช้กรอง df ภายนอกได้)

    field_options = [
        ("❄️ Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("💧 Water Production (L)", "water_production"),
        ("🔋 Energy Per Liter (kWh/L)", "energy_per_liter (kWh/L)"),
        ("🔋 Power Consumption (kWh)", "accumulated_energy (kWh)"),
        ("🌫️ Abs. Intake humidity (g/m3)", "absolute_intake_air_humidity"),
        ("🌫️ Abs. Outtake humidity (g/m3)", "absolute_outtake_air_humidity"),
        ("🌫️ Adjust Abs. Outtake humidity (g/m3)", "calibrated_outtake_air_humidity"),
        ("🌡️ Intake temperature (°C)", "intake_air_temperature (C)"),
        ("💨 Intake humidity (%)", "intake_air_humidity (%)"),
        ("↘ Intake velocity (m/s)", "intake_air_velocity (m/s)"),
        ("🔥 Outtake temperature (°C)", "outtake_air_temperature (C)"),
        ("💨 Outtake humidity (%)", "outtake_air_humidity (%)"),
        ("↗ Outtake velocity (m/s)", "outtake_air_velocity (m/s)"),
        ("🔌 Current (A)", "current"),
        ("⚡ Power (W)", "power"),
    ]

    selected_fields = ["timestamp"]
    for label, col in field_options:
        if st.sidebar.checkbox(label, value=(col == "harvesting_efficiency")):
            selected_fields.append(col)

    return selected_station_name, selected_fields, intake_area


def render_data_section(df, station_name, selected_fields):
    st.title(f"📊 AWH Dashboard – {station_name}")

    if df.empty:
        st.warning("No data found for this station.")
        return

    available_fields = [col for col in selected_fields if col in df.columns and col != "timestamp"]

    df_sorted = df.sort_values("timestamp").copy()
    df_sorted["Date"] = df_sorted["timestamp"].dt.date
    df_sorted["Time"] = df_sorted["timestamp"].dt.strftime("%H:%M:%S")

    for field in available_fields:
        st.subheader(f"📊 {field} Overview")

        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### 📋 Table")
            st.dataframe(df_sorted[["Date", "Time", field]], use_container_width=True)

            st.download_button(
                label=f"⬇️ Download {field} CSV",
                data=df_sorted[["Date", "Time", field]].to_csv(index=False),
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv"
            )

        with col2:
            st.markdown("#### 📈 Plot")

            df_sorted[field] = pd.to_numeric(df_sorted[field], errors="coerce")
            plot_data = df_sorted[["timestamp", field]].dropna()

            excluded_points = 0
            if field == "harvesting_efficiency":
                excluded_points = (plot_data[field] > 50).sum()
                plot_data = plot_data[plot_data[field] <= 50]

            if plot_data.empty:
                st.warning(f"⚠️ No data available to plot for {field}.")
                continue

            if field == "energy_per_liter (kWh/L)":
                plot_data["Hour"] = plot_data["timestamp"].dt.floor("H")
                hourly_plot = (
                    plot_data.groupby("Hour")[field]
                    .mean()
                    .reset_index()
                    .rename(columns={"Hour": "timestamp"})
                )

                chart = alt.Chart(hourly_plot).mark_bar().encode(
                    x=alt.X("timestamp:T", title="Hour", axis=alt.Axis(format="%H:%M")),
                    y=alt.Y(field, title="Energy per Liter (kWh/L)"),
                    tooltip=["timestamp", field]
                ).properties(width="container", height=300)

                st.altair_chart(chart, use_container_width=True)

            else:
                y_axis = alt.Y(
                    field,
                    title=field,
                    scale=alt.Scale(domain=[0, 30]) if field == "harvesting_efficiency" else alt.Undefined
                )

                chart = alt.Chart(plot_data).mark_circle(size=60).encode(
                    x=alt.X(
                        "timestamp:T",
                        title="Date & Time",
                        axis=alt.Axis(format="%Y-%m-%d %H:%M", labelAngle=-45)
                    ),
                    y=y_axis,
                    tooltip=["timestamp", field]
                ).properties(width="container", height=300)

                st.altair_chart(chart, use_container_width=True)

            if excluded_points > 0:
                st.caption(f"⚠️ {excluded_points} point(s) above 50% were excluded from the plot.")
