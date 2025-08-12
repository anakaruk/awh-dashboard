import streamlit as st
import pandas as pd
import altair as alt
from datetime import timedelta

def render_controls(station_list):
    st.sidebar.header("🔧 Controls")
    selected_station_name = st.sidebar.selectbox("📍 Select Station", station_list)

    intake_area_options = {
        "DewStand 1: 0.04 m²": 0.04,
        "T50 1: 0.18 m²": 0.18
    }
    intake_area_label = st.sidebar.selectbox("🧲 Intake Area (m²)", list(intake_area_options.keys()))
    intake_area = intake_area_options[intake_area_label]

    field_options = [
        ("❄️ Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("💧 Water Production (L)", "water_production"),
        ("🔋 Energy Per Liter (kW.hr/L)", "energy_per_liter (kWh/L)"),
        ("🔋 Power Consumption (kW.hr)", "accumulated_energy (kWh)"),
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

    # New: downsampling selector (helps performance on long spans)
    downsample_map = {
        "Raw (no downsampling)": None,
        "Every 5 minutes": "5T",
        "Every 15 minutes": "15T",
        "Hourly": "1H",
        "Daily": "1D",
    }
    downsample_label = st.sidebar.selectbox("⏱️ Downsample for charts", list(downsample_map.keys()), index=2)
    downsample_rule = downsample_map[downsample_label]

    return selected_station_name, selected_fields, intake_area, downsample_rule


def render_data_section(df, station_name, selected_fields, downsample_rule=None):
    st.title(f"📊 AWH Dashboard – {station_name}")

    if df.empty:
        st.warning("No data found for this station.")
        return

    # Ensure timestamp is datetime and sorted
    if "timestamp" not in df.columns:
        st.warning("No 'timestamp' column in data.")
        return

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp")

    # ---- New: Date range filter (inclusive) ----
    min_dt = df["timestamp"].min().normalize()
    max_dt = df["timestamp"].max().normalize()
    default_start = max(min_dt, max_dt - pd.Timedelta(days=3))  # last 3 days by default
    default_end = max_dt

    st.sidebar.markdown("### 🗓️ Date range")
    start_date, end_date = st.sidebar.date_input(
        "Select start and end date",
        value=(default_start.date(), default_end.date()),
        min_value=min_dt.date(),
        max_value=max_dt.date()
    )

    # Make end date inclusive by adding one day and filtering < next_day_start
    try:
        start_ts = pd.to_datetime(str(start_date))
        end_ts = pd.to_datetime(str(end_date)) + pd.Timedelta(days=1)
    except Exception:
        start_ts = default_start
        end_ts = default_end + pd.Timedelta(days=1)

    df = df[(df["timestamp"] >= start_ts) & (df["timestamp"] < end_ts)]
    if df.empty:
        st.info("No data in the selected date range.")
        return

    # Optional: light downsampling for charts (table remains raw in-range)
    def downsample_for_field(frame: pd.DataFrame, field: str) -> pd.DataFrame:
        if not downsample_rule:
            return frame[["timestamp", field]].dropna()
        # Resample by mean for numeric fields
        tmp = frame.set_index("timestamp")[[field]].dropna()
        try:
            out = tmp.resample(downsample_rule).mean().dropna().reset_index()
        except Exception:
            out = tmp.reset_index()  # fallback
        return out.rename(columns={"index": "timestamp"})

    available_fields = [c for c in selected_fields if c in df.columns and c != "timestamp"]

    # Add convenient Date & Time columns for the table
    df["Date"] = df["timestamp"].dt.date
    df["Time"] = df["timestamp"].dt.strftime("%H:%M:%S")

    for field in available_fields:
        st.subheader(f"📊 {field} Overview")

        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### 📋 Table")
            st.dataframe(df[["Date", "Time", field]].dropna(), use_container_width=True)

            st.download_button(
                label=f"⬇️ Download {field} CSV",
                data=df[["Date", "Time", field]].dropna().to_csv(index=False),
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv"
            )

        with col2:
            st.markdown("#### 📈 Plot")

            # Coerce numeric for safer plotting
            df[field] = pd.to_numeric(df[field], errors="coerce")
            plot_data = df[["timestamp", field]].dropna()

            excluded_points = 0
            if field == "harvesting_efficiency":
                excluded_points = (plot_data[field] > 50).sum()
                plot_data = plot_data[plot_data[field] <= 50]

            if plot_data.empty:
                st.warning(f"⚠️ No data available to plot for {field}.")
                continue

            # Energy per liter stays hourly bars (already aggregated meaningfully)
            if field == "energy_per_liter (kWh/L)":
                plot_data["Hour"] = plot_data["timestamp"].dt.floor("H")
                hourly_plot = (
                    plot_data.groupby("Hour")[field]
                    .mean()
                    .reset_index()
                    .rename(columns={"Hour": "timestamp"})
                )

                chart = alt.Chart(hourly_plot).mark_bar().encode(
                    x=alt.X("timestamp:T", title="Hour", axis=alt.Axis(format="%Y-%m-%d %H:%M")),
                    y=alt.Y(field, title="Energy per Liter (kWh/L)"),
                    tooltip=["timestamp", field]
                ).properties(width="container", height=300)

                st.altair_chart(chart, use_container_width=True)

            else:
                # Apply optional downsampling for this field
                plot_data = downsample_for_field(plot_data, field)

                y_axis = alt.Y(
                    field,
                    title=field,
                    scale=alt.Scale(domain=[0, 30]) if field == "harvesting_efficiency" else alt.Undefined
                )

                chart = alt.Chart(plot_data).mark_circle(size=36).encode(
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
