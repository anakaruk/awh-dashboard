import pandas as pd
import math
import numpy as np

# -----------------------------
# Core calculations
# -----------------------------

def calculate_absolute_humidity(temp_c, rel_humidity):
    try:
        numerator = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5)) * rel_humidity * 2.1674
        denominator = 273.15 + temp_c
        return round(numerator / denominator, 2)
    except Exception:
        return None


def calculate_water_production(weight_series: pd.Series) -> pd.Series:
    """Accumulate produced water in liters from balance trace (with occasional reset)."""
    total, prev = 0.0, None
    result = []
    for w in weight_series:
        if pd.isnull(w):
            result.append(None)
            continue
        w = float(w)
        if prev is None:
            total = w
        elif w >= prev:
            total += (w - prev)
        prev = w
        result.append(total / 1000.0)  # g → L
    return pd.Series(result, index=weight_series.index)


# -----------------------------
# Public API
# -----------------------------

def process_data(df: pd.DataFrame, intake_area: float = 1.0, lag_steps: int = 10) -> pd.DataFrame:
    df = df.copy()

    # --- timestamps ---
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        df["sample_interval"] = df["timestamp"].diff().dt.total_seconds().fillna(30)

    # --- rename standard columns ---
    rename_map = {
        "velocity": "intake_air_velocity (m/s)",
        "temperature": "intake_air_temperature (C)",
        "humidity": "intake_air_humidity (%)",
        "outtake_velocity": "outtake_air_velocity (m/s)",
        "outtake_temperature": "outtake_air_temperature (C)",
        "outtake_humidity": "outtake_air_humidity (%)",
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # --- absolute humidity ---
    if {"intake_air_temperature (C)", "intake_air_humidity (%)"}.issubset(df.columns):
        df["absolute_intake_air_humidity"] = df.apply(
            lambda r: calculate_absolute_humidity(r["intake_air_temperature (C)"], r["intake_air_humidity (%)"]),
            axis=1,
        )
    if {"outtake_air_temperature (C)", "outtake_air_humidity (%)"}.issubset(df.columns):
        df["absolute_outtake_air_humidity"] = df.apply(
            lambda r: calculate_absolute_humidity(r["outtake_air_temperature (C)"], r["outtake_air_humidity (%)"]),
            axis=1,
        )

    # --- intake water step (L) ---
    if {"absolute_intake_air_humidity", "intake_air_velocity (m/s)", "sample_interval"}.issubset(df.columns):
        df["intake_step (L)"] = (
            df["absolute_intake_air_humidity"] * df["intake_air_velocity (m/s)"] * intake_area * df["sample_interval"] / 1000.0
        )
    else:
        df["intake_step (L)"] = 0.0

    # --- energy step (kWh) ---
    if {"power", "sample_interval"}.issubset(df.columns):
        df["energy_step (kWh)"] = df["power"] * (df["sample_interval"] / 3600.0) / 1000.0
    else:
        df["energy_step (kWh)"] = 0.0

    # --- water production (from balance weight) ---
    if "weight" in df.columns:
        df["water_production"] = calculate_water_production(df["weight"])
    else:
        df["water_production"] = np.nan

    # --- cumulative sums ---
    df["accumulated_intake_water"] = df["intake_step (L)"].cumsum().round(3)
    df["accumulated_energy (kWh)"] = df["energy_step (kWh)"].cumsum().round(6)

    # --- harvesting efficiency (rolling) ---
    if {"intake_step (L)", "water_production"}.issubset(df.columns):
        win = max(int(lag_steps), 1)
        intake_roll = df["intake_step (L)"].rolling(window=win, min_periods=1).sum()
        prod_roll = df["water_production"].diff().rolling(window=win, min_periods=1).sum()
        df["harvesting_efficiency"] = (100.0 * prod_roll / intake_roll).round(2)
    else:
        df["harvesting_efficiency"] = np.nan

    return df
