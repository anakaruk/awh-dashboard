import streamlit as st
import pandas as pd
import altair as alt

def render_controls(station_list):
    st.sidebar.header("\ud83d\udd27 Controls")
    selected_station_name = st.sidebar.selectbox("\ud83d\udccd Select Station", station_list)

    intake_area_options = {
        "DewStand 1: 0.04 m\u00b2": 0.04,
        "T50 1: 0.18 m\u00b2": 0.18
    }

    intake_area_label = st.sidebar.selectbox("\ud83e\uddf2 Intake Area (m\u00b2)", list(intake_area_options.keys()))
    intake_area = intake_area_options[intake_area_label]

    field_options = [
        ("\u2744\ufe0f Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("\ud83d\udca7 Water Production (L)", "water_production"),
        ("\ud83d\udd0b Energy Per Liter (kW.hr/L)", "energy_per_liter (kWh/L)"),
        ("\ud83d\udd0b Power Consumption (kW.hr)", "accumulated_energy (kWh)"),
        ("\ud83c\udf2b\ufe0f Abs. Intake humidity (g/m3)", "absolute_intake_air_humidity"),
        ("\ud83c\udf2b\ufe0f Abs. Outtake humidity (g/m3)", "absolute_outtake_air_humidity"),
        ("\ud83c\udf2b\ufe0f Adjust Abs. Outtake humidity (g/m3)", "calibrated_outtake_air_humidity"),
        ("\ud83c\udf21\ufe0f Intake temperature (\u00b0C)", "intake_air_temperature (C)"),
        ("\ud83d\udca8 Intake humidity (%)", "intake_air_humidity (%)"),
        ("\u2198 Intake velocity (m/s)", "intake_air_velocity (m/s)"),
        ("\ud83d\udd25 Outtake temperature (\u00b0C)", "outtake_air_temperature (C)"),
        ("\ud83d\udca8 Outtake humidity (%)", "outtake_air_humidity (%)"),
        ("\u2197 Outtake velocity (m/s)", "outtake_air_velocity (m/s)"),
        ("\ud83d\udd0c Current (A)", "current"),
        ("\u26a1 Power (W)", "power"),
    ]

    selected_fields = ["timestamp"]
    for label, col in field_options:
        if st.sidebar.checkbox(label, value=(col == "harvesting_efficiency")):
            selected_fields.append(col)

    return selected_station_name, selected_fields, intake_area

def render_data_section(df, station_name, selected_fields):
    st.title(f"\ud83d\udcca AWH Dashboard \u2013 {station_name}")

    if df.empty:
        st.warning("No data found for this station.")
        return

    available_fields = [col for col in selected_fields if col in df.columns and col != "timestamp"]

    df_sorted = df.sort_values("timestamp").copy()
    df_sorted["Date"] = df_sorted["timestamp"].dt.date
    df_sorted["Time"] = df_sorted["timestamp"].dt.strftime("%H:%M:%S")

    unique_dates = df_sorted["timestamp"].dt.normalize().drop_duplicates()
    tick_times = []
    for d in unique_dates:
        tick_times += [
            pd.Timestamp(f"{d.date()} 06:00"),
            pd.Timestamp(f"{d.date()} 12:00"),
            pd.Timestamp(f"{d.date()} 18:00"),
            pd.Timestamp(f"{(d + pd.Timedelta(days=1)).date()} 00:00")
        ]

    for field in available_fields:
        st.subheader(f"\ud83d\udcca `{field}` Overview")

        col1, col2 = st.columns([1, 2], gap="large")

        with col1:
            st.markdown("#### \ud83d\udccb Table")
            st.dataframe(df_sorted[["Date", "Time", field]], use_container_width=True)

            st.download_button(
                label=f"\u2b07\ufe0f Download `{field}` CSV",
                data=df_sorted[["Date", "Time", field]].to_csv(index=False),
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv"
            )

        with col2:
            st.markdown("#### \ud83d\udcc8 Plot")

            df_sorted[field] = pd.to_numeric(df_sorted[field], errors="coerce")
            plot_data = df_sorted[["timestamp", field]].dropna()

            excluded_points = 0
            if field == "harvesting_efficiency":
                excluded_points = (plot_data[field] > 50).sum()
                plot_data = plot_data[plot_data[field] <= 50]

            if plot_data.empty:
                st.warning(f"\u26a0\ufe0f No data available to plot for `{field}`.")
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
                        axis=alt.Axis(
                            format="%m-%d %H:%M",
                            values=tick_times,
                            labelAngle=-45,
                            labelOverlap="parity",
                            tickCount="day"
                        )
                    ),
                    y=y_axis,
                    tooltip=["timestamp", field]
                ).properties(width="container", height=300)

                st.altair_chart(chart, use_container_width=True)

            if excluded_points > 0:
                st.caption(f"\u26a0\ufe0f {excluded_points} point(s) above 50% were excluded from the plot.")
