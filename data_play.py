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

    # Ensure timestamp is datetime and sort
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

    # Rename columns
    df.rename(columns={
        "velocity": "intake_air_velocity (m/s)",
        "temperature": "intake_air_temperature (C)",
        "humidity": "intake_air_humidity (%)",
        "env_velocity": "outtake_air_velocity (m/s)",
        "env_temperature": "outtake_air_temperature (C)",
        "env_humidity": "outtake_air_humidity (%)"
    }, inplace=True)

    print("✅ Columns after renaming:", df.columns.tolist())

    # Add placeholder columns
    df["harvesting_efficiency"] = None
    df["water_production"] = None
    df["absolute_intake_air_humidity"] = None
    df["absolute_outtake_air_humidity"] = None

    # Calculate absolute intake humidity
    if "intake_air_temperature (C)" in df.columns and "intake_air_humidity (%)" in df.columns:
        valid_rows = df["intake_air_temperature (C)"].notnull() & df["intake_air_humidity (%)"].notnull()
        df.loc[valid_rows, "absolute_intake_air_humidity"] = df.loc[valid_rows].apply(
            lambda row: calculate_absolute_humidity(float(row["intake_air_temperature (C)"]),
                                                    float(row["intake_air_humidity (%)"])),
            axis=1
        )
    else:
        print("⚠️ Intake air columns not found. Skipping intake absolute humidity.")

    # Calculate absolute outtake humidity
    if "outtake_air_temperature (C)" in df.columns and "outtake_air_humidity (%)" in df.columns:
        print("\n🧪 DEBUG outtake data preview:")
        print(df[["outtake_air_temperature (C)", "outtake_air_humidity (%)"]].head(10))
        print("Non-null counts:")
        print(df[["outtake_air_temperature (C)", "outtake_air_humidity (%)"]].notnull().sum())

        valid_rows = df["outtake_air_temperature (C)"].notnull() & df["outtake_air_humidity (%)"].notnull()
        df.loc[valid_rows, "absolute_outtake_air_humidity"] = df.loc[valid_rows].apply(
            lambda row: calculate_absolute_humidity(float(row["outtake_air_temperature (C)"]),
                                                    float(row["outtake_air_humidity (%)"])),
            axis=1
        )
    else:
        print("⚠️ Outtake air columns not found. Skipping outtake absolute humidity.")

    return df
