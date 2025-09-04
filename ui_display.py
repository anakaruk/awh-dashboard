import streamlit as st
import pandas as pd

try:
    import altair as alt
    _ALT_OK = True
except Exception:
    _ALT_OK = False


def render_controls(station_list):
    st.sidebar.header("🔧 Controls")

    # --- Station select with placeholder ---
    STN_PLACEHOLDER = "— Please select station —"
    station = st.sidebar.selectbox(
        "📍 Select Station",
        options=[STN_PLACEHOLDER] + list(station_list),
        index=0,
    )
    selected_station_name = None if station == STN_PLACEHOLDER else station

    # --- Intake area with placeholder ---
    intake_area_options = {
        "AquaPars 1: 0.12 m²": 0.12,
        "DewStand 1: 0.04 m²": 0.04,
        "T50 1: 0.18 m²": 0.18,
    }
    AREA_PLACEHOLDER = "— Please select air intake area —"
    area_label = st.sidebar.selectbox(
        "🧲 Intake Area (m²)",
        options=[AREA_PLACEHOLDER] + list(intake_area_options.keys()),
        index=0,
    )
    intake_area = None if area_label == AREA_PLACEHOLDER else float(intake_area_options[area_label])

    # --- Date period (same as before) ---
    st.sidebar.subheader("📅 Date period")
    today = pd.Timestamp.now().date()
    picked = st.sidebar.date_input("Select date range", value=(today, today))
    if isinstance(picked, (list, tuple)) and len(picked) == 2:
        start_date, end_date = picked
    else:
        start_date = end_date = picked

    # --- Fields (same as before) ---
    field_options = [
        ("❄️ Harvesting Efficiency (%)", "harvesting_efficiency"),
        ("💧 Water Production (L)", "water_production"),
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
    ]
    selected_fields = ["timestamp"]
    for label, col in field_options:
        if st.sidebar.checkbox(label, value=(col == "harvesting_efficiency")):
            selected_fields.append(col)

    if not _ALT_OK:
        st.sidebar.warning("Altair not installed — using fallback charts.")

    controls = {
        "lag_steps": 10,
        "apply_reset": False,
        "apply_pause": False,
        "apply_freeze": False,
    }

    # NOTE: we now return None for station/intake_area until user selects them
    return selected_station_name, selected_fields, intake_area, (start_date, end_date), controls
