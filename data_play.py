# data_play.py — Classic HE with time-based 5-min lag + short-window aggregation (Py3.8-safe)
import math
from typing import Optional

import numpy as np
import pandas as pd


# -----------------------------
# Helpers
# -----------------------------
def calculate_absolute_humidity(temp_c: float, rel_humidity: float) -> Optional[float]:
    """Absolute humidity in g/m^3 (rounded to 2 decimals)."""
    try:
        num = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5)) * rel_humidity * 2.1674
        den = 273.15 + temp_c
        return round(num / den, 2)
    except Exception:
        return None


def calculate_water_production(weight_series: pd.Series) -> pd.Series:
    """
    Accumulate produced water (L) from a weight trace in grams.
    Allows resets: only nonnegative deltas add to total.
    """
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
        out.append(total / 1000.0)  # g -> L
    return pd.Series(out, index=weight_series.index)


def _remove_spikes(series: pd.Series, window: int = 10, threshold: float = 0.6) -> pd.Series:
    """
    Replace spikes with NaN if they are more than `threshold` (e.g., 0.6 = 60%)
    above the rolling mean of the previous `window` points.
    """
    s = pd.to_numeric(series, errors="coerce")
    roll_mean = s.rolling(window=window, min_periods=1).mean().shift(1)  # past window
    mask = s > (1 + threshold) * roll_mean
    return s.where(~mask, np.nan)


# -----------------------------
# Main processing
# -----------------------------
def process_data(df: pd.DataFrame, intake_area: float = 1.0, lag_steps: int = 10) -> pd.DataFrame:
    """
    Produces derived metrics used by the dashboard.
    """
    df = df.copy()

    # --- timestamps & sample interval ---
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        dt = df["timestamp"].diff().dt.total_seconds()
        med = dt.iloc[1:].median() if len(dt) > 1 else 30.0
        if pd.isna(med) or med <= 0:
            med = 30.0
        df["sample_interval"] = dt.fillna(med).clip(lower=max(1.0, med / 3.0))

    # --- normalize incoming names to the final schema ---
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

    # --- remove spikes dynamically ---
    # Humidity: >60% above last-10 average
    if "intake_air_humidity (%)" in df.columns:
        df["intake_air_humidity (%)"] = _remove_spikes(df["intake_air_humidity (%)"], window=10, threshold=0.6)
    if "outtake_air_humidity (%)" in df.columns:
        df["outtake_air_humidity (%)"] = _remove_spikes(df["outtake_air_humidity (%)"], window=10, threshold=0.6)

    # Velocity: >200% above last-10 average
    if "intake_air_velocity (m/s)" in df.columns:
        df["intake_air_velocity (m/s)"] = _remove_spikes(df["intake_air_velocity (m/s)"], window=10, threshold=2.0)
    if "outtake_air_velocity (m/s)" in df.columns:
        df["outtake_air_velocity (m/s)"] = _remove_spikes(df["outtake_air_velocity (m/s)"], window=10, threshold=2.0)

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

    # --- per-sample intake (L) ---
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

    # --- water production from balance ---
    if "weight" in df.columns:
        df["water_production"] = calculate_water_production(df["weight"])
    else:
        df["water_production"] = np.nan

    # --- optional flow & pump ---
    if "flow_total" in df.columns:
        df["flow_total (L)"] = pd.to_numeric(df["flow_total"], errors="coerce")
    else:
        df["flow_total (L)"] = pd.Series(np.nan, index=df.index, dtype="float64")

    flow_rate = pd.Series(np.nan, index=df.index, dtype="float64")
    if "flow_lmin" in df.columns:
        flow_rate = pd.to_numeric(df["flow_lmin"], errors="coerce")
    if "flow_hz" in df.columns:
        guess_from_hz = pd.to_numeric(df["flow_hz"], errors="coerce") / 38.0
        need_fill = (~pd.notna(flow_rate)) | (flow_rate <= 0)
        flow_rate = flow_rate.where(~need_fill, guess_from_hz)
    if "sample_interval" in df.columns and df["flow_total (L)"].notna().any():
        d_total = df["flow_total (L)"].diff()
        d_total = d_total.where(d_total >= 0, 0.0)
        rate_from_total = (d_total / df["sample_interval"].replace(0, np.nan)) * 60.0
        need_fill = (~pd.notna(flow_rate)) | (flow_rate <= 0)
        flow_rate = flow_rate.where(~need_fill, rate_from_total)
    df["flow_rate (L/min)"] = pd.to_numeric(flow_rate, errors="coerce").clip(lower=0)

    if df["flow_total (L)"].isna().all() and "sample_interval" in df.columns:
        step_L = (df["flow_rate (L/min)"].fillna(0) / 60.0) * df["sample_interval"].fillna(0)
        df["flow_total (L)"] = step_L.cumsum()

    if "pump_status" in df.columns:
        df["pump_status"] = pd.to_numeric(df["pump_status"], errors="coerce").fillna(0).astype(int).clip(0, 1)
        df["pump_on"] = df["pump_status"] == 1
    else:
        df["pump_on"] = pd.Series(np.nan, index=df.index)

    # --- cumulative views ---
    df["accumulated_intake_water"] = df["intake_step (L)"].cumsum().round(3)
    df["accumulated_energy (kWh)"] = df["energy_step (kWh)"].cumsum().round(6)

    # --- energy per liter (cumulative) ---
    wp = df["water_production"].astype(float)
    df["energy_per_liter (kWh/L)"] = np.where(
        (wp > 0) & np.isfinite(wp),
        (df["accumulated_energy (kWh)"] / wp).round(5),
        np.nan,
    )

    # --- harvesting efficiency ---
    production_step = df["water_production"].diff().clip(lower=0)
    lag_seconds = 300  # 5 minutes
    med_dt = df["sample_interval"].iloc[1:].median() if "sample_interval" in df.columns else 30.0
    if pd.isna(med_dt) or med_dt <= 0:
        med_dt = 30.0
    lag_n = max(1, int(round(lag_seconds / med_dt)))

    denom_raw = df["intake_step (L)"].replace(0, np.nan)
    he_raw = 100.0 * (production_step.shift(-lag_n) / denom_raw)
    df["harvesting_efficiency_raw"] = he_raw.round(2)

    window_seconds = 120
    win_n = max(1, int(round(window_seconds / med_dt)))
    min_periods = max(1, win_n // 2)

    intake_win = df["intake_step (L)"].rolling(win_n, min_periods=min_periods).sum()
    prod_win = production_step.rolling(win_n, min_periods=min_periods).sum()
    prod_win_lagged = prod_win.shift(-lag_n)

    min_intake_window_L = 0.01
    denom = intake_win.where(intake_win >= min_intake_window_L)
    with np.errstate(divide="ignore", invalid="ignore"):
        he_windowed = 100.0 * (prod_win_lagged / denom)

    he_smooth = he_windowed.rolling(max(3, win_n // 2), min_periods=1, center=True).median()

    df["harvesting_efficiency"] = he_windowed.round(2)
    df["harvesting_efficiency_smooth"] = he_smooth.round(2)

    return df
