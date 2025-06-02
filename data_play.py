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
            total += weight  # Reset detected; treat as new cycle and add directly

        water_production.append(total)
        prev = weight

    return water_production

def calculate_harvesting_efficiency(abs_in, abs_out):
    try:
        return round(((abs_in - abs_out) / abs_in) * 100, 2) if abs_in else None
    except Exception as e:
        print(f"Error calculating harvesting efficiency: {e}")
        return None

def process_data(df, intake_area=1.0):
    df = df.copy()

    df["absolute_intake_air_humidity"] = df.apply(
        lambda row: calculate_absolute_humidity(row["intake_air_temperature (C)"], row["intake_air_humidity (%)"]),
        axis=1
    )

    df["absolute_outtake_air_humidity"] = df.apply(
        lambda row: calculate_absolute_humidity(row["outtake_air_temperature (C)"], row["outtake_air_humidity (%)"]),
        axis=1
    )

    df["harvesting_efficiency"] = df.apply(
        lambda row: calculate_harvesting_efficiency(
            row["absolute_intake_air_humidity"],
            row["absolute_outtake_air_humidity"]
        ),
        axis=1
    )

    if "weight" in df.columns:
        df["water_production"] = calculate_water_production(df["weight"])
    else:
        df["water_production"] = None

    return df
