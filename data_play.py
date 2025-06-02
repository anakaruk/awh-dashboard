import pandas as pd
import math

def calculate_absolute_humidity(temp_c, rel_humidity):
    try:
        numerator = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5)) * rel_humidity * 2.1674
        denominator = 273.15 + temp_c
        abs_humidity = numerator / denominator
        return round(abs_humidity, 2)
    except Exception as e:
        print(f"Error calculating AH: {e}")
        return None

def calculate_water_production(weight_series):
    water_production = []
    total = 0
    prev = None

    for weight in weight_series:
        if pd.isnull(weight):
            water_production.append(None)
            continue

        if prev is None:
            total = weight
        elif weight >= prev:
            total += (weight - prev)
        else:
            # Reset detected, do not add anything
            pass

        water_production.append(total / 1000)  # Convert from grams to liters
        prev = weight

    return water_production

def process_data(df, intake_area=1.0):
    df = df.copy()

    print("📋 Original columns:", df.columns.tolist())

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")
        df["sample_interval"] = df["timestamp"].diff().dt.total_seconds()
        df["sample_interval"] = df["sample_interval"].fillna(method="bfill").fillna(method="ffill")

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

    df["absolute_intake_air_humidity"] = None
    df["absolute_outtake_air_humidity"] = None
    df["accumulated_intake_water"] = None
    df["collected_velocity (m/s)"] = None

    if "intake_air_temperature (C)" in df.columns and "intake_air_humidity (%)" in df.columns:
        df["absolute_intake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(
                row.get("intake_air_temperature (C)"),
                row.get("intake_air_humidity (%)")
            ) if pd.notnull(row.get("intake_air_temperature (C)")) and pd.notnull(row.get("intake_air_humidity (%)"))
            else None,
            axis=1
        )

    if "outtake_air_temperature (C)" in df.columns and "outtake_air_humidity (%)" in df.columns:
        df["absolute_outtake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(
                row.get("outtake_air_temperature (C)"),
                row.get("outtake_air_humidity (%)")
            ) if pd.notnull(row.get("outtake_air_temperature (C)")) and pd.notnull(row.get("outtake_air_humidity (%)"))
            else None,
            axis=1
        )

    if "weight" in df.columns:
        df["water_production"] = calculate_water_production(df["weight"])
    else:
        print("⚠️ No 'weight' column found for water production")

    if all(col in df.columns for col in ["absolute_intake_air_humidity", "intake_air_velocity (m/s)", "sample_interval"]):
        intake_steps = []
        accumulated = 0

        for _, row in df.iterrows():
            ah = row["absolute_intake_air_humidity"]
            vel = row["intake_air_velocity (m/s)"]
            interval = row["sample_interval"]

            if pd.notnull(ah) and pd.notnull(vel) and vel > 0 and pd.notnull(interval):
                intake_L = ah * vel * intake_area * interval / 1000  # Convert g to L
                accumulated += intake_L
                intake_steps.append(accumulated)
            else:
                intake_steps.append(None)

        df["accumulated_intake_water"] = intake_steps

    if "timestamp" in df.columns and "power" in df.columns:
        try:
            df = df.sort_values("timestamp")
            frequency = df["timestamp"].diff().median()
            if pd.notnull(frequency):
                freq_hours = frequency.total_seconds() / 3600
                df["energy_step (kWh)"] = (df["power"] * freq_hours) / 1000
                df["accumulated_energy (kWh)"] = df["energy_step (kWh)"].cumsum()
            else:
                print("⚠️ Could not determine timestamp frequency.")
        except Exception as e:
            print(f"❌ Error calculating energy: {e}")

    if "accumulated_energy (kWh)" in df.columns and "water_production" in df.columns:
        df["energy_per_liter (kWh/L)"] = df.apply(
            lambda row: round((row["accumulated_energy (kWh)"] * 1000 / row["water_production"]), 5)
            if pd.notnull(row["accumulated_energy (kWh)"]) and 
               pd.notnull(row["water_production"]) and 
               row["water_production"] > 0
            else 0,
            axis=1
        )

    return df
