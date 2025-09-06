import pandas as pd
import numpy as np
import math

# -----------------------------
# Helpers
# -----------------------------

def calculate_absolute_humidity(temp_c: float, rel_humidity: float) -> float | None:
    """g/m^3, rounded to 2 decimals."""
    try:
        num = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5)) * rel_humidity * 2.1674
        den = 273.15 + temp_c
        return round(num / den, 2)
    except Exception:
        return None


def calculate_water_production(weight_series: pd.Series) -> pd.Series:
    """
    Accumulate produced water (L) from balance trace, allowing resets.
    Assumes 'weight' is in grams and never decreases except when reset.
    """
    total, prev = 0.0, None
    out = []
    for w in weight_series:
        if pd.isna(w):
            out.append(np.nan)
            continue
        w = float(w)
        if prev is None:
            total = w
        elif w >= prev:
            total += (w - prev)
        prev = w
        out.append(total / 1000.0)  # g → L
    return pd.Series(out, index=weight_series.index)


# -----------------------------
# Main processing
# -----------------------------

def process_data(
    df: pd.DataFrame,
    *,
    intake_area: float = 1.0,      # m^2
    lag_steps: int = 10,           # rolling window for efficiency
    min_intake_L: float = 0.02,    # minimum intake in window to trust (% denom)
    min_prod_L: float = 0.005,     # minimum production in window to call pump "ON"
    eff_max: float = 120.0,        # drop efficiency outside [0, eff_max]
    power_on_threshold: float | None = None,  # optional gating by power (W)
    pump_on_col: str = "pump_on",  # optional boolean column if you have it
) -> pd.DataFrame:

    df = df.copy()

    # ----- timestamps & sample interval -----
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        dt = df["timestamp"].diff().dt.total_seconds()
        med = dt.iloc[1:].median() if len(dt) > 1 else 30
        if pd.isna(med) or med <= 0:
            med = 30
        df["sample_interval"] = dt.fillna(med).clip(lower=max(1, med / 3))

    # ----- rename incoming fields to your final schema -----
    rename_map = {
        "velocity": "intake_air_velocity (m/s)",
        "temperature": "intake_air_temperature (C)",
        "humidity": "intake_air_humidity (%)",
        "outtake_velocity": "outtake_air_velocity (m/s)",
        "outtake_temperature": "outtake_air_temperature (C)",
        "outtake_humidity": "outtake_air_humidity (%)",
    }
    for old, new in rename_map.items():
        if old in df.columns:
            df.rename(columns={old: new}, inplace=True)

    # ----- absolute humidity (g/m^3) -----
    if {"intake_air_temperature (C)", "intake_air_humidity (%)"}.issubset(df.columns):
        df["absolute_intake_air_humidity"] = df.apply(
            lambda r: calculate_absolute_humidity(
                r["intake_air_temperature (C)"], r["intake_air_humidity (%)"]
            ),
            axis=1,
        )

    if {"outtake_air_temperature (C)", "outtake_air_humidity (%)"}.issubset(df.columns):
        df["absolute_outtake_air_humidity"] = df.apply(
            lambda r: calculate_absolute_humidity(
                r["outtake_air_temperature (C)"], r["outtake_air_humidity (% )"]
            ),
            axis=1,
        )

    # ----- intake step per sample (L) -----
    if {"absolute_intake_air_humidity", "intake_air_velocity (m/s)", "sample_interval"}.issubset(df.columns):
        df["intake_step (L)"] = (
            df["absolute_intake_air_humidity"].fillna(0)
            * df["intake_air_velocity (m/s)"].clip(lower=0).fillna(0)
            * float(intake_area)
            * df["sample_interval"].fillna(0)
            / 1000.0  # g → kg ~ L
        ).clip(lower=0)
    else:
        df["intake_step (L)"] = 0.0

    # ----- energy step (kWh) -----
    if {"power", "sample_interval"}.issubset(df.columns):
        df["energy_step (kWh)"] = (df["power"].fillna(0) * (df["sample_interval"] / 3600.0) / 1000.0)
    else:
        df["energy_step (kWh)"] = 0.0

    # ----- water production from balance (L) -----
    if "weight" in df.columns:
        df["water_production"] = calculate_water_production(df["weight"])
    else:
        df["water_production"] = np.nan

    # ----- cumulative views -----
    df["accumulated_intake_water"] = df["intake_step (L)"].cumsum().round(3)
    df["accumulated_energy (kWh)"] = df["energy_step (kWh)"].cumsum().round(6)

    # ----- energy per liter -----
    wp = df["water_production"].astype(float)
    df["energy_per_liter (kWh/L)"] = np.where(
        (wp > 0) & np.isfinite(wp),
        (df["accumulated_energy (kWh)"] / wp).round(5),
        np.nan,
    )

    # =============================
    # Harvesting efficiency (fixed)
    # =============================
    win = max(int(lag_steps), 1)

    prod_step = df["water_production"].diff().clip(lower=0)          # L/sample
    prod_roll = prod_step.rolling(window=win, min_periods=1).sum()   # L over window
    intake_roll = df["intake_step (L)"].rolling(window=win, min_periods=1).sum()  # L over window

    # Pump ON gate:
    if pump_on_col in df.columns:
        pump_on_win = df[pump_on_col].astype(bool).rolling(window=win, min_periods=1).mean() >= 0.5
    elif (power_on_threshold is not None) and ("power" in df.columns):
        pump_on_win = (df["power"] > float(power_on_threshold)).rolling(window=win, min_periods=1).mean() >= 0.5
    else:
        # default: if we actually produced water in the window
        pump_on_win = prod_roll > float(min_prod_L)

    with np.errstate(divide="ignore", invalid="ignore"):
        eff_raw = 100.0 * (prod_roll / intake_roll)

    good_den = intake_roll >= float(min_intake_L)
    good_num = prod_roll >= float(min_prod_L)
    in_range = (eff_raw >= 0.0) & (eff_raw <= float(eff_max))

    keep = pump_on_win & good_den & good_num & in_range
    df["harvesting_efficiency"] = eff_raw.where(keep, np.nan).round(2)

    return df
