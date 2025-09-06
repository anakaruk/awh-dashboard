# data_play.py — back to the classic harvesting calc (5-min lag, no pump gating)
import math
from typing import Optional
import numpy as np
import pandas as pd


def calculate_absolute_humidity(temp_c: float, rel_humidity: float) -> Optional[float]:
    try:
        num = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5)) * rel_humidity * 2.1674
        den = 273.15 + temp_c
        return round(num / den, 2)
    except Exception:
        return None


def calculate_water_production(weight_series: pd.Series) -> pd.Series:
    """Accumulate produced water (L) from balance (g), allowing resets."""
    total, prev = 0.0, None
    out = []
    for w in weight_series:
        if pd.isna(w):
            out.append(np.nan); continue
        w = float(w)
        if prev is None:
            total = w
        elif w >= prev:
            total += (w - prev)
        prev = w
        out.append(total / 1000.0)  # g → L
    return pd.Series(out, index=weight_series.index)


def process_data(df: pd.DataFrame, intake_area: float = 1.0, lag_steps: int = 10) -> pd.DataFrame:
    df = df.copy()

    # --- timestamps & sample interval ---
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        dt = df["timestamp"].diff().dt.total_seconds()
        med = dt.iloc[1:].median() if len(dt) > 1 else 30
        if pd.isna(med) or med <= 0: med = 30
        df["sample_interval"] = dt.fillna(med).clip(lower=max(1.0, med / 3.0))

    # --- rename incoming fields to final schema (if needed) ---
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

    # --- flow fields left intact for plotting if you need them ---
    if "flow_total" in df.columns:
        df["flow_total (L)"] = pd.to_numeric(df["flow_total"], errors="coerce")
    else:
        df["flow_total (L)"] = pd.Series(np.nan, index=df.index, dtype="float64")

    flow_rate = pd.Series(np.nan, index=df.index, dtype="float64")
    if "flow_lmin" in df.columns:
        flow_rate = pd.to_numeric(df["flow_lmin"], errors="coerce")
    if "flow_hz" in df.columns:
        guess_from_hz = pd.to_numeric(df["flow_hz"], errors="coerce") / 38.0
        need = (~pd.notna(flow_rate)) | (flow_rate <= 0)
        flow_rate = flow_rate.where(~need, guess_from_hz)
    if "sample_interval" in df.columns and df["flow_total (L)"].notna().any():
        d_total = df["flow_total (L)"].diff().clip(lower=0)
        rate_from_total = (d_total / df["sample_interval"].replace(0, np.nan)) * 60.0
        need = (~pd.notna(flow_rate)) | (flow_rate <= 0)
        flow_rate = flow_rate.where(~need, rate_from_total)
    df["flow_rate (L/min)"] = pd.to_numeric(flow_rate, errors="coerce").clip(lower=0)
    if df["flow_total (L)"].isna().all() and "sample_interval" in df.columns:
        step_L = (df["flow_rate (L/min)"].fillna(0) / 60.0) * df["sample_interval"].fillna(0)
        df["flow_total (L)"] = step_L.cumsum()

    # --- cumulative views ---
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
    # Harvesting efficiency — classic method
    #   1) step from cumulative series
    #   2) apply 5-minute lag (shift -12 samples)
    #   3) HE = 100 * production_step_lagged / intake_step
    # =============================
    df["intake_step"] = df["accumulated_intake_water"].diff()
    df["production_step"] = df["water_production"].diff()

    # 5-minute lag (historical assumption of ~12 samples ≈ 5 min)
    df["production_step_lagged"] = df["production_step"].shift(-12)

    with np.errstate(divide="ignore", invalid="ignore"):
        he = 100.0 * (df["production_step_lagged"] / df["intake_step"])

    # keep NaN when denom <= 0 or any side missing
    valid = (df["intake_step"] > 0) & pd.notna(df["production_step_lagged"])
    df["harvesting_efficiency"] = he.where(valid).round(2)

    return df
