import pandas as pd
import math

def calculate_absolute_humidity(temp_c, rel_humidity):
    try:
        exponent = (17.67 * temp_c) / (temp_c + 243.5)
        sat_vapor_pressure = 6.112 * math.exp(exponent)
        vapor_pressure = rel_humidity / 100 * sat_vapor_pressure
        abs_humidity = (vapor_pressure * 2.1674) / (273.15 + temp_c)
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

        water_production.append(total)
        prev = weight

    return water_production

def process_data(df, intake_area=1.0):
    df = df.copy()

    print("📋 Original columns:", df.columns.tolist())

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("timestamp")

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

    print("✅ Renamed columns:", df.columns.tolist())

    # Init calculated fields
    df["absolute_intake_air_humidity"] = None
    df["absolute_outtake_air_humidity"] = None
    df["accumulated_intake_water"] = None
    df["harvesting_efficiency"] = None

    # Absolute humidity (intake)
    if "intake_air_temperature (C)" in df.columns and "intake_air_humidity (%)" in df.columns:
        df["absolute_intake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(
                float(row["intake_air_temperature (C)"]),
                float(row["intake_air_humidity (%)"])
            ) if pd.notnull(row["intake_air_temperature (C)"]) and pd.notnull(row["intake_air_humidity (%)"])
            else None,
            axis=1
        )

    # Absolute humidity (outtake)
    if "outtake_air_temperature (C)" in df.columns and "outtake_air_humidity (%)" in df.columns:
        df["absolute_outtake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(
                float(row["outtake_air_temperature (C)"]),
                float(row["outtake_air_humidity (%)"])
            ) if pd.notnull(row["outtake_air_temperature (C)"]) and pd.notnull(row["outtake_air_humidity (%)"])
            else None,
            axis=1
        )

    # Water production
    if "weight" in df.columns:
        df["water_production"] = calculate_water_production(df["weight"])
    else:
        print("⚠️ No 'weight' column found for water production")

    # Intake water accumulation
    if "absolute_intake_air_humidity" in df.columns and "intake_air_velocity (m/s)" in df.columns:
        intake_water = []
        accumulated = 0

        for _, row in df.iterrows():
            ah = row.get("absolute_intake_air_humidity")
            vel = row.get("intake_air_velocity (m/s)")

            if pd.notnull(ah) and pd.notnull(vel) and vel > 0:
                vel_m_s = vel / 3.6  # Convert km/h to m/s if needed
                intake = ah * vel_m_s * intake_area * 0.3  # 0.3 = estimated sampling time window (s)
                accumulated += intake
                intake_water.append(accumulated)
            else:
                intake_water.append(None)

        df["accumulated_intake_water"] = intake_water

    # Harvesting efficiency
    if "water_production" in df.columns and "accumulated_intake_water" in df.columns:
        df["harvesting_efficiency"] = df.apply(
            lambda row: round((row["water_production"] / row["accumulated_intake_water"]) / 100, 5)
            if pd.notnull(row["water_production"]) and
               pd.notnull(row["accumulated_intake_water"]) and
               row["accumulated_intake_water"] > 0
            else None,
            axis=1
        )

    # Normalize and accumulate power data in kWh
    if "timestamp" in df.columns and "power" in df.columns:
        try:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
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

    # Energy per liter (kWh/L)
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
