import pandas as pd
import math

def calculate_absolute_humidity(temp_c, rel_humidity):
    """
    Calculate absolute humidity (g/m³) from temperature (°C) and relative humidity (%)
    """
    try:
        exponent = (17.67 * temp_c) / (temp_c + 243.5)
        sat_vapor_pressure = 6.112 * math.exp(exponent)
        vapor_pressure = rel_humidity / 100 * sat_vapor_pressure
        abs_humidity = (vapor_pressure * 2.1674) / (273.15 + temp_c)
        return round(abs_humidity, 2)
    except Exception as e:
        print(f"Error calculating AH: {e}")
        return None

def process_data(df):
    df = df.copy()

    print("📋 Original columns:", df.columns.tolist())

    # Convert timestamp to datetime and sort
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

    # Rename columns to standard display names
    rename_map = {
        "velocity": "intake_air_velocity (m/s)",
        "temperature": "intake_air_temperature (C)",
        "humidity": "intake_air_humidity (%)",
        "outtake_velocity": "outtake_air_velocity (m/s)",
        "outtake_temperature": "outtake_air_temperature (C)",
        "outtake_humidity": "outtake_air_humidity (%)"
    }

    for old_col, new_col in rename_map.items():
        if old_col in df.columns:
            df.rename(columns={old_col: new_col}, inplace=True)

    print("✅ Renamed columns:", df.columns.tolist())

    # Add placeholder columns
    df["harvesting_efficiency"] = None
    df["water_production"] = None
    df["absolute_intake_air_humidity"] = None
    df["absolute_outtake_air_humidity"] = None

    # Calculate absolute intake air humidity
    if "intake_air_temperature (C)" in df.columns and "intake_air_humidity (%)" in df.columns:
        df["absolute_intake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(float(row["intake_air_temperature (C)"]),
                                                    float(row["intake_air_humidity (%)"]))
            if pd.notnull(row["intake_air_temperature (C)"]) and pd.notnull(row["intake_air_humidity (%)"])
            else None,
            axis=1
        )
    else:
        print("⚠️ Intake air temp/humidity columns missing")

    # Calculate absolute outtake air humidity
    if "outtake_air_temperature (C)" in df.columns and "outtake_air_humidity (%)" in df.columns:
        df["absolute_outtake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(float(row["outtake_air_temperature (C)"]),
                                                    float(row["outtake_air_humidity (%)"]))
            if pd.notnull(row["outtake_air_temperature (C)"]) and pd.notnull(row["outtake_air_humidity (%)"])
            else None,
            axis=1
        )
    else:
        print("⚠️ Outtake air temp/humidity columns missing")

    return df
