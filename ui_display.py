import streamlit as st
import pandas as pd
import altair as alt


def render_controls(station_list):
    st.sidebar.header("Controls")

    # Station selector
    selected_station_name = st.sidebar.selectbox("Select Station", station_list)

    # Intake area options
    intake_area_options = {
        "AquaPars 1: 0.12 m²": 0.12,
        "DewStand 1: 0.04 m²": 0.04,
        "T50 1: 0.18 m²": 0.18,
    }
    intake_area_label = st.sidebar.selectbox("Intake Area (m²)", list(intake_area_options.keys()))
    intake_area = intake_area_options[intake_area_label]

    # Field selection
    field_options = [
        ("Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("Water Production (L)", "water_production"),
        ("Energy Per Liter (kWh/L)", "energy_per_liter (kWh/L)"),
        ("Power Consumption (kWh)", "accumulated_energy (kWh)"),
        ("Abs. Intake humidity (g/m³)", "absolute_intake_air_humidity"),
        ("Abs. Outtake humidity (g/m³)", "absolute_outtake_air_humidity"),
        ("Adjusted Abs. Outtake humidity (g/m³)", "calibrated_outtake_air_humidity"),
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

    # Compute Date/Time columns for all tables
    df_sorted = df.sort_values("timestamp").copy()
    df_sorted["Date"] = df_sorted["timestamp"].dt.strftime("%Y-%m-%d")
    df_sorted["Time"] = df_sorted["timestamp"].dt.strftime("%H:%M:%S")

    # Only plot fields that exist
    available_fields = [c for c in selected_fields if c in df_sorted.columns and c != "timestamp"]

    for field in available_fields:
        st.subheader(f"{field} Overview")

        col1, col2 = st.columns([1, 2], gap="large")

        # ---- Table ----
        with col1:
            st.markdown("**Table**")
            st.dataframe(df_sorted[["Date", "Time", field]], use_container_width=True)
            st.download_button(
                label=f"Download {field} CSV",
                data=df_sorted[["Date", "Time", field]].to_csv(index=False),
                file_name=f"{station_name}_{field.replace(' ', '_')}.csv",
                mime="text/csv",
            )

        # ---- Plot ----
        with col2:
            st.markdown("**Plot**")

            # Make sure y is numeric
            num = pd.to_numeric(df_sorted[field], errors="coerce")
            plot_data = df_sorted.loc[num.notna(), ["timestamp", field]].copy()
            if plot_data.empty:
                st.warning(f"No data available to plot for {field}.")
                continue

            # Special handling for energy per liter: hourly averages as bars
            if field == "energy_per_liter (kWh/L)":
                plot_data["Hour"] = plot_data["timestamp"].dt.floor("H")
                hourly = (
                    plot_data.groupby("Hour")[field]
                    .mean()
                    .reset_index()
                    .rename(columns={"Hour": "timestamp"})
                )
                chart = (
                    alt.Chart(hourly)
                    .mark_bar()
                    .encode(
                        x=alt.X("timestamp:T", title="Hour", axis=alt.Axis(format="%H:%M")),
                        y=alt.Y(field, title="Energy per Liter (kWh/L)"),
                        tooltip=["timestamp:T", field],
                    )
                    .properties(width="container", height=300)
                )
                st.altair_chart(chart, use_container_width=True)

            else:
                # Optional clamp for harvesting_efficiency spikes > 50
                y = alt.Y(
                    field,
                    title=field,
                    scale=alt.Scale(domain=[0, 50]) if field == "harvesting_efficiency" else alt.Undefined,
                )
                chart = (
                    alt.Chart(plot_data)
                    .mark_circle(size=60)
                    .encode(
                        x=alt.X(
                            "timestamp:T",
                            title="Date & Time",
                            axis=alt.Axis(format="%Y-%m-%d %H:%M", labelAngle=-45),
                        ),
                        y=y,
                        tooltip=["timestamp:T", field],
                    )
                    .properties(width="container", height=300)
                )
                st.altair_chart(chart, use_container_width=True)
