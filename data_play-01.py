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

def process_data(
    df: pd.DataFrame,
    intake_area: float = 1.0,
    lag_steps: int = 10,
    *,
    # masks to keep efficiency only when it is meaningful/stable
    min_intake_L: float = 0.02,     # minimum intake over the window (L) to trust denominator
    min_prod_L: float = 0.005,      # minimum production over the window (L) to call the pump "ON"
    eff_max: float = 120.0,         # drop efficiency outside [0, eff_max]
    power_on_threshold: float | None = None  # optional: if provided and 'power' exists, treat pump ON when power > threshold
) -> pd.DataFrame:

    df = df.copy()

    # --- timestamps ---
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        # robust sample interval (fallback to median if first is NaN/0)
        dt = df["timestamp"].diff().dt.total_seconds()
        med = dt.iloc[1:].median() if len(dt) > 1 else 30
        med = 30 if pd.isna(med) or med <= 0 else med
        df["sample_interval"] = dt.fillna(med).clip(lower=med/3)

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
            df["absolute_intake_air_humidity"]
            * df["intake_air_velocity (m/s)"].clip(lower=0)
            * float(intake_area)
            * df["sample_interval"]
            / 1000.0
        ).fillna(0.0).clip(lower=0.0)
    else:
        df["intake_step (L)"] = 0.0

    # --- energy step (kWh) ---
    if {"power", "sample_interval"}.issubset(df.columns):
        df["energy_step (kWh)"] = (df["power"].fillna(0) * (df["sample_interval"] / 3600.0) / 1000.0)
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

    # --- energy per liter ---
    if "water_production" in df.columns:
        wp = df["water_production"].astype(float)
        df["energy_per_liter (kWh/L)"] = np.where(
            (wp > 0) & np.isfinite(wp),
            (df["accumulated_energy (kWh)"] / wp).round(5),
            np.nan,
        )
    else:
        df["energy_per_liter (kWh/L)"] = np.nan

    # -----------------------------
    # Harvesting efficiency (pump-aware, spike-resistant)
    # -----------------------------
    win = max(int(lag_steps), 1)

    # production increment per sample (never negative)
    prod_step = df["water_production"].diff().clip(lower=0)
    prod_roll = prod_step.rolling(window=win, min_periods=1).sum()

    # intake over window
    intake_roll = df["intake_step (L)"].rolling(window=win, min_periods=1).sum()

    # Determine when pump is "ON"
    if "pump_on" in df.columns:
        # user-provided boolean column (preferred if present)
        pump_flag = df["pump_on"].astype(bool)
        pump_on_win = pump_flag.rolling(window=win, min_periods=1).mean() >= 0.5
    elif power_on_threshold is not None and "power" in df.columns:
        pump_on_win = (df["power"].astype(float) > float(power_on_threshold)).rolling(window=win, min_periods=1).mean() >= 0.5
    else:
        # default: treat "pump ON" as "we actually discharged water in this window"
        pump_on_win = prod_roll > float(min_prod_L)

    # raw efficiency
    with np.errstate(divide="ignore", invalid="ignore"):
        eff_raw = 100.0 * (prod_roll / intake_roll)

    # Masks to keep only meaningful, stable values
    good_den = intake_roll >= float(min_intake_L)
    good_num = prod_roll >= float(min_prod_L)
    in_range = (eff_raw >= 0.0) & (eff_raw <= float(eff_max))

    keep = pump_on_win & good_den & good_num & in_range

    eff = eff_raw.where(keep, np.nan).round(2)
    df["harvesting_efficiency"] = eff

    return df
