# data_play.py  — flow & pump fields + spike-safe efficiency (Py3.8-safe)
import math
from typing import Optional

import numpy as np
import pandas as pd


# -----------------------------
# Helpers
# -----------------------------
def calculate_absolute_humidity(temp_c: float, rel_humidity: float) -> Optional[float]:
    """Return absolute humidity (g/m^3), rounded to 2 decimals."""
    try:
        num = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5)) * rel_humidity * 2.1674
        den = 273.15 + temp_c
        return round(num / den, 2)
    except Exception:
        return None


def calculate_water_production(weight_series: pd.Series) -> pd.Series:
    """Accumulate produced water in liters from balance trace (with occasional reset)."""
    total = 0.0
    prev = None
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
    intake_area: float = 1.0,      # m^2
    lag_steps: int = 10,           # rolling window length (samples)
    min_intake_L: float = 0.02,    # min intake in window to trust denominator
    min_prod_L: float = 0.005,     # min production in window to call pump "ON"
    eff_max: float = 120.0,        # keep efficiency within [0, eff_max]
    power_on_threshold: Optional[float] = None,  # optional gating by power (W)
    pump_on_col: str = "pump_on",               # optional boolean column name
) -> pd.DataFrame:

    df = df.copy()

    # --- timestamps & sample interval ---
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        dt = df["timestamp"].diff().dt.total_seconds()
        med = dt.iloc[1:].median() if len(dt) > 1 else 30
        if pd.isna(med) or med <= 0:
            med = 30
        df["sample_interval"] = dt.fillna(med).clip(lower=max(1.0, med / 3.0))

    # --- rename incoming fields to final schema ---
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

    # --- absolute humidity (g/m^3) ---
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
                r["outtake_air_temperature (C)"], r["outtake_air_humidity (%)"]
            ),
            axis=1,
        )

    # --- intake step per sample (L) ---
    if {"absolute_intake_air_humidity", "intake_air_velocity (m/s)", "sample_interval"}.issubset(df.columns):
        df["intake_step (L)"] = (
            df["absolute_intake_air_humidity"].fillna(0)
            * df["intake_air_velocity (m/s)"].clip(lower=0).fillna(0)
            * float(intake_area)
            * df["sample_interval"].fillna(0)
            / 1000.0
        ).clip(lower=0)
    else:
        df["intake_step (L)"] = 0.0

    # --- energy step (kWh) ---
    if {"power", "sample_interval"}.issubset(df.columns):
        df["energy_step (kWh)"] = (df["power"].fillna(0) * (df["sample_interval"] / 3600.0) / 1000.0)
    else:
        df["energy_step (kWh)"] = 0.0

    # --- water production from balance (L) ---
    if "weight" in df.columns:
        df["water_production"] = calculate_water_production(df["weight"])
    else:
        df["water_production"] = np.nan

    # ===== FLOW & PUMP STATUS (robust pandas-only) =====
    # 1) Flow total (L)
    if "flow_total" in df.columns:
        df["flow_total (L)"] = pd.to_numeric(df["flow_total"], errors="coerce")
    else:
        df["flow_total (L)"] = pd.Series(np.nan, index=df.index, dtype="float64")

    # 2) Flow rate (L/min)
    flow_rate = pd.Series(np.nan, index=df.index, dtype="float64")

    if "flow_lmin" in df.columns:
        flow_rate = pd.to_numeric(df["flow_lmin"], errors="coerce")

    if "flow_hz" in df.columns:
        guess_from_hz = pd.to_numeric(df["flow_hz"], errors="coerce") / 38.0
        # fill where current rate is NaN or <= 0
        need_fill = (~pd.notna(flow_rate)) | (flow_rate <= 0)
        flow_rate = flow_rate.where(~need_fill, guess_from_hz)

    if "sample_interval" in df.columns and df["flow_total (L)"].notna().any():
        d_total = df["flow_total (L)"].diff()
        d_total = d_total.where(d_total >= 0, 0.0)  # avoid negatives on resets
        rate_from_total = (d_total / df["sample_interval"].replace(0, np.nan)) * 60.0
        need_fill = (~pd.notna(flow_rate)) | (flow_rate <= 0)
        flow_rate = flow_rate.where(~need_fill, rate_from_total)

    df["flow_rate (L/min)"] = pd.to_numeric(flow_rate, errors="coerce")
    df["flow_rate (L/min)"] = df["flow_rate (L/min)"].clip(lower=0)

    # If total missing but rate exists, integrate to get total
    if df["flow_total (L)"].isna().all() and "sample_interval" in df.columns:
        step_L = (df["flow_rate (L/min)"].fillna(0) / 60.0) * df["sample_interval"].fillna(0)
        df["flow_total (L)"] = step_L.cumsum()

    # 3) Pump status (0/1 + bool + text)
    if "pump_status" in df.columns:
        df["pump_status"] = pd.to_numeric(df["pump_status"], errors="coerce").fillna(0).astype(int).clip(0, 1)
        df["pump_on"] = df["pump_status"] == 1
    else:
        df["pump_status"] = pd.Series(np.nan, index=df.index)
        df["pump_on"] = False

    df["pump_status_text"] = np.where(df["pump_on"], "ON", "OFF")

    # --- cumulative views (existing) ---
    df["accumulated_intake_water"] = df["intake_step (L)"].cumsum().round(3)
    df["accumulated_energy (kWh)"] = df["energy_step (kWh)"].cumsum().round(6)

    # --- energy per liter ---
    wp = df["water_production"].astype(float)
    df["energy_per_liter (kWh/L)"] = np.where(
        (wp > 0) & np.isfinite(wp),
        (df["accumulated_energy (kWh)"] / wp).round(5),
        np.nan,
    )

    # =============================
    # Harvesting efficiency (pump-aware, spike-resistant)
    # =============================
    win = max(int(lag_steps), 1)

    prod_step = df["water_production"].diff().clip(lower=0)            # L/sample
    prod_roll = prod_step.rolling(window=win, min_periods=1).sum()     # L over window
    intake_roll = df["intake_step (L)"].rolling(window=win, min_periods=1).sum()

    # Pump ON gating priority: explicit pump_on column -> power threshold -> production-based
    if pump_on_col in df.columns and df[pump_on_col].any():
        pump_on_win = df[pump_on_col].astype(bool).rolling(window=win, min_periods=1).mean() >= 0.5
    elif (power_on_threshold is not None) and ("power" in df.columns):
        pump_on_win = (df["power"] > float(power_on_threshold)).rolling(window=win, min_periods=1).mean() >= 0.5
    else:
        pump_on_win = prod_roll > float(min_prod_L)

    with np.errstate(divide="ignore", invalid="ignore"):
        eff_raw = 100.0 * (prod_roll / intake_roll)

    good_den = intake_roll >= float(min_intake_L)
    good_num = prod_roll >= float(min_prod_L)
    in_range = (eff_raw >= 0.0) & (eff_raw <= float(eff_max))

    keep = pump_on_win & good_den & good_num & in_range
    df["harvesting_efficiency"] = eff_raw.where(keep, np.nan).round(2)

    return df
