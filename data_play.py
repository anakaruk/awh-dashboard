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
        prev = weight

        water_production.append(total / 1000)  # Convert g to L

    return water_production

def process_data(df, intake_area=1.0):
    df = df.copy()

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp").reset_index(drop=True)
        df["sample_interval"] = df["timestamp"].diff().dt.total_seconds()
        median_interval = df["sample_interval"].iloc[1:].median()
        df["sample_interval"] = df["sample_interval"].fillna(median_interval or 10)

    # Rename raw fields
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

    # Calculate absolute humidity
    if "intake_air_temperature (C)" in df.columns and "intake_air_humidity (%)" in df.columns:
        df["absolute_intake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(
                row["intake_air_temperature (C)"],
                row["intake_air_humidity (%)"]
            ) if pd.notnull(row["intake_air_temperature (C)"]) and pd.notnull(row["intake_air_humidity (%)"])
            else None,
            axis=1
        )

    if "outtake_air_temperature (C)" in df.columns and "outtake_air_humidity (%)" in df.columns:
        df["absolute_outtake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(
                row["outtake_air_temperature (C)"],
                row["outtake_air_humidity (%)"]
            ) if pd.notnull(row["outtake_air_temperature (C)"]) and pd.notnull(row["outtake_air_humidity (%)"])
            else None,
            axis=1
        )

    # Water production
    if "weight" in df.columns:
        df["water_production"] = calculate_water_production(df["weight"])
    else:
        print("⚠️ No 'weight' column found for water production")

    # Intake water calculation
    if all(col in df.columns for col in ["absolute_intake_air_humidity", "intake_air_velocity (m/s)", "sample_interval"]):
        accumulated = 0
        intake_water_list = []
        for _, row in df.iterrows():
            ah = row["absolute_intake_air_humidity"]
            vel = row["intake_air_velocity (m/s)"]
            interval = row["sample_interval"]

            if pd.notnull(ah) and pd.notnull(vel) and pd.notnull(interval):
                intake = ah * vel * intake_area * interval / 1000 if vel > 0 else 0
                accumulated += intake
            intake_water_list.append(round(accumulated, 3))

        df["accumulated_intake_water"] = intake_water_list

    # Power and energy calculations
    if "power" in df.columns and "timestamp" in df.columns:
        try:
            freq_seconds = df["timestamp"].diff().dt.total_seconds().median()
            freq_hours = freq_seconds / 3600 if pd.notnull(freq_seconds) else 0
            df["energy_step (kWh)"] = (df["power"] * freq_hours) / 1000
            df["accumulated_energy (kWh)"] = df["energy_step (kWh)"].cumsum()
        except Exception as e:
            print(f"❌ Error calculating energy: {e}")

    # Energy per liter
    if "accumulated_energy (kWh)" in df.columns and "water_production" in df.columns:
        df["energy_per_liter (kWh/L)"] = df.apply(
            lambda row: round((row["accumulated_energy (kWh)"] / row["water_production"]), 5)
            if pd.notnull(row["accumulated_energy (kWh)"]) and 
               pd.notnull(row["water_production"]) and 
               row["water_production"] > 0
            else 0,
            axis=1
        )

    # Harvesting Efficiency (%)
    if "accumulated_intake_water" in df.columns and "water_production" in df.columns:
        df["intake_step"] = df["accumulated_intake_water"].diff()
        df["production_step"] = df["water_production"].diff()

        df["harvesting_efficiency"] = df.apply(
            lambda row: round((row["production_step"] / row["intake_step"]) * 100, 2)
            if pd.notnull(row["production_step"]) and pd.notnull(row["intake_step"]) and row["intake_step"] > 0
            else 0.0,
            axis=1
        )

    return df
