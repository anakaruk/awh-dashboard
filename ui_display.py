import streamlit as st
import pandas as pd
import altair as alt

def render_controls(station_list):
    st.sidebar.header("Controls")
    selected_station_name = st.sidebar.selectbox("Select Station", station_list)

    intake_area_options = {
        "DewStand 1: 0.04 m²": 0.04,
        "T50 1: 0.18 m²": 0.18
    }

    intake_area_label = st.sidebar.selectbox("Intake Area (m²)", list(intake_area_options.keys()))
    intake_area = intake_area_options[intake_area_label]

    field_options = [
        ("Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("Water Production (L)", "water_production"),
        ("Energy Per Liter (kW.hr/L)", "energy_per_liter (kWh/L)"),
        ("Power Consumption (kW.hr)", "accumulated_energy (kWh)"),
        ("Abs. Intake humidity (g/m3)", "absolute_intake_air_humidity"),
        ("Abs. Outtake humidity (g/m3)", "absolute_outtake_air_humidity"),
        ("Adjust Abs. Outtake humidity (g/m3)", "calibrated_outtake_air_humidity"),
        ("Intake temperature (°C)", "intake_air_temperature (C)"),
        ("Intake humidity (%)", "intake_air_humidity (%)"),
        ("Intake velocity (m/s)", "intake_air_velocity (m/s)"),
        ("Outtake temperature (°C)", "outtake_air_temperature (C)"),
        ("Outtake humidity (%)", "outtake_air_humidity (%)"),
        ("Outtake velocity (m/s)", "outtake_air_velocity (m/s)"),
        ("Current (A)", "current"),
        ("Power (W)", "power"),
    ]

    selected_fields = ["timestamp"]
    for label, col in field_options:
        if st.sidebar.checkbox(label, value=(col == "harvesting_efficiency")):
            selected_fields.append(col)

    return selected_station_name, selected_fields, intake_area

def render_data_section(df, station_name, selected_fields):
    st.title(f"AWH Dashboard – {station_name}")

    if df.empty:
        st.warning("No data found for this station.")
        return

    available_fields = [col for col in selected_fields if col in df.columns and col != "timestamp"]

    df_sorted = df.sort_values("timestamp").copy()
    df_sorted["Date"] = df_sorted["timestamp"].dt.date
    df_sorted["Time"] = df_sorted["timestamp"].dt.strftime("%H:%M:%S")

    # Compute 6-hour interval ticks
    start_time = df_sorted["timestamp"].min()
    end_time = df_sorted["timestamp"].max()

    start_hour = (start_time.hour // 6) * 6
    adjusted_start = pd.Timestamp(start_time.date()) + pd.Timedelta(hours=start_hour)

    tick_times = pd.date_range(start=adjusted_start, end=end_time + pd.Timedelta(hours=6), freq="6H").to_list()

    for field in available_fields:
        st.subheader(f"{field} Overview")

        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### Table")
            st.dataframe(df_sorted[["Date", "Time", field]], use_container_width=True)

            st.download_button(
                label=f"Download `{field}` CSV",
                data=df_sorted[["Date", "Time", field]].to_csv(index=False),
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv"
            )

        with col2:
            st.markdown("#### Plot")

            df_sorted[field] = pd.to_numeric(df_sorted[field], errors="coerce")
            plot_data = df_sorted[["timestamp", field]].dropna()

            excluded_points = 0
            if field == "harvesting_efficiency":
                excluded_points = (plot_data[field] > 50).sum()
                plot_data = plot_data[plot_data[field] <= 50]

            axis_config = alt.Axis(
                format="%m-%d %H:%M",
                values=tick_times,
                labelAngle=-45,
                labelOverlap=False,
                title="Date & Time"
            )

            if plot_data.empty:
                st.warning(f"No data available to plot for `{field}`.")

                dummy_df = pd.DataFrame({"timestamp": tick_times, field: [None] * len(tick_times)})

                chart = alt.Chart(dummy_df).mark_point(opacity=0).encode(
                    x=alt.X("timestamp:T", axis=axis_config),
                    y=alt.Y(field, title=field)
                ).properties(width="container", height=300)

                st.altair_chart(chart, use_container_width=True)
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
                chart = alt.Chart(plot_data).mark_circle(size=60).encode(
                    x=alt.X("timestamp:T", axis=axis_config),
                    y=alt.Y(field, title=field),
                    tooltip=["timestamp", field]
                ).properties(width="container", height=300)

                st.altair_chart(chart, use_container_width=True)

            if excluded_points > 0:
                st.caption(f"{excluded_points} point(s) above 50% were excluded from the plot.")
