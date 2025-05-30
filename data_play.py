import pandas as pd
import math

def calculate_absolute_humidity(temp_c, rel_humidity):
    try:
        exponent = (17.67 * temp_c) / (temp_c + 243.5)
        saturation_vapor_pressure = 6.112 * math.exp(exponent)
        vapor_pressure = rel_humidity / 100 * saturation_vapor_pressure
        abs_humidity = (vapor_pressure * 2.1674) / (273.15 + temp_c)
        return round(abs_humidity, 2)
    except Exception as e:
        print(f"❌ Error in calculate_absolute_humidity: {e}")
        return None

def process_data(df):
    df = df.copy()

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

    df.rename(columns={
        "velocity": "intake_air_velocity (m/s)",
        "temperature": "intake_air_temperature (C)",
        "humidity": "intake_air_humidity (%)",
        "env_velocity": "outtake_air_velocity (m/s)",
        "env_temperature": "outtake_air_temperature (C)",
        "env_humidity": "outtake_air_humidity (%)"
    }, inplace=True)

    print("📋 Columns after rename:", df.columns.tolist())

    df["harvesting_efficiency"] = None
    df["water_production"] = None
    df["absolute_intake_air_humidity"] = None
    df["absolute_outtake_air_humidity"] = None

    # Intake absolute humidity
    if "intake_air_temperature (C)" in df.columns and "intake_air_humidity (%)" in df.columns:
        valid_intake = df["intake_air_temperature (C)"].notnull() & df["intake_air_humidity (%)"].notnull()
        df.loc[valid_intake, "absolute_intake_air_humidity"] = df.loc[valid_intake].apply(
            lambda row: calculate_absolute_humidity(float(row["intake_air_temperature (C)"]),
                                                    float(row["intake_air_humidity (%)"])),
            axis=1
        )

    # Outtake absolute humidity with full debug
    if "outtake_air_temperature (C)" in df.columns and "outtake_air_humidity (%)" in df.columns:
        for i, row in df.iterrows():
            temp = row["outtake_air_temperature (C)"]
            rh = row["outtake_air_humidity (%)"]
            if pd.notnull(temp) and pd.notnull(rh):
                try:
                    temp_val = float(temp)
                    rh_val = float(rh)
                    ah = calculate_absolute_humidity(temp_val, rh_val)
                    df.at[i, "absolute_outtake_air_humidity"] = ah
                    print(f"✅ Row {i}: Temp={temp_val} RH={rh_val} → AH={ah}")
                except Exception as e:
                    print(f"❌ Row {i}: Error calculating AH with Temp={temp}, RH={rh}: {e}")
            else:
                print(f"⚠️ Row {i}: Skipping due to null values — Temp={temp}, RH={rh}")
    else:
        print("❌ Missing outtake temperature or humidity columns.")

    return df
