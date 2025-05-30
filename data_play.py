import pandas as pd
import math

def calculate_absolute_humidity(temp_c, rel_humidity):
    """
    Calculate absolute humidity (g/m³) from temperature (°C) and relative humidity (%)
    """
    try:
        exponent = (17.67 * temp_c) / (temp_c + 243.5)
        saturation_vapor_pressure = 6.112 * math.exp(exponent)
        vapor_pressure = rel_humidity / 100 * saturation_vapor_pressure
        abs_humidity = (vapor_pressure * 2.1674) / (273.15 + temp_c)
        return round(abs_humidity, 2)
    except Exception as e:
        print(f"Error in calculate_absolute_humidity: {e}")
        return None

def process_data(df):
    df = df.copy()

    # Sort and ensure timestamp format
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

    # ✅ Rename fields for clarity
    df.rename(columns={
        "velocity": "intake_air_velocity (m/s)",
        "temperature": "intake_air_temperature (C)",
        "humidity": "intake_air_humidity (%)",
        "env_velocity": "outtake_air_velocity (m/s)",
        "env_temperature": "outtake_air_temperature (C)",
        "env_humidity": "outtake_air_humidity (%)"
    }, inplace=True)

    # Debug column names
    print("Renamed columns:", df.columns.tolist())

    # 🧪 Placeholder columns
    df["harvesting_efficiency"] = None
    df["water_production"] = None
    df["absolute_intake_air_humidity"] = None
    df["absolute_outtake_air_humidity"] = None

    # 🔹 Calculate absolute intake humidity
    if "intake_air_temperature (C)" in df.columns and "intake_air_humidity (%)" in df.columns:
        df["absolute_intake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(row["intake_air_temperature (C)"], row["intake_air_humidity (%)"])
            if pd.notnull(row["intake_air_temperature (C)"]) and pd.notnull(row["intake_air_humidity (%)"])
            else None,
            axis=1
        )
    else:
        print("Missing intake air columns; skipping absolute_intake_air_humidity calculation.")

    # 🔹 Calculate absolute outtake humidity
    if "outtake_air_temperature (C)" in df.columns and "outtake_air_humidity (%)" in df.columns:
        df["absolute_outtake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(row["outtake_air_temperature (C)"], row["outtake_air_humidity (%)"])
            if pd.notnull(row["outtake_air_temperature (C)"]) and pd.notnull(row["outtake_air_humidity (%)"])
            else None,
            axis=1
        )
    else:
        print("Missing outtake air columns; skipping absolute_outtake_air_humidity calculation.")

    return df
