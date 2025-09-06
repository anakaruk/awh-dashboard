# data_play.py — classic harvesting efficiency (time-based 5-min lag), Py3.8-safe
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
    """
    Accumulate produced water (L) from a balance trace in grams.
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
        out.append(total / 1000.0)  # g → L
    return pd.Series(out, index=weight_series.index)


# -----------------------------
# Main processing
# -----------------------------
def process_data(df: pd.DataFrame, intake_area: float = 1.0, lag_steps: int = 10) -> pd.DataFrame:
    """
    Processes raw station dataframe into derived metrics used by the dashboard.

    Key outputs:
      - intake_step (L)                    : per-sample intake water (L)
      - accumulated_intake_water           : cumulative intake (L)
      - water_production                   : cumulative produced water (L)
      - energy_step / accumulated_energy   : kWh per step / cumulative kWh
      - energy_per_liter (kWh/L)           : cumulative energy per produced liter
      - harvesting_efficiency              : 100 * prod_step_lagged / intake_step
                                             with a time-based ~5 minute lag
      - flow_rate (L/min), flow_total (L)  : if flow signals available
      - pump_status, pump_on               : if pump status provided (not used in HE)
    """
    df = df.copy()

    # --- timestamps & sample interval ---
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        dt = df["timestamp"].diff().dt.total_seconds()
        med = dt.iloc[1:].median() if len(dt) > 1 else 30
        if pd.isna(med) or med <= 0:
            med = 30
        # Fill NaN with median; avoid zeros/negatives
        df["sample_interval"] = dt.fillna(med).clip(lower=max(1.0, med / 3.0))

    # --- normalize input names to the final schema (if alternate names appear) ---
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

    # --- absolute humidity (g/m^3) for intake/outtake ---
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
            / 1000.0  # g → kg ~ L
        ).clip(lower=0)
    else:
        df["intake_step (L)"] = 0.0

    # --- energy step (kWh) ---
    if {"power", "sample_interval"}.issubset(df.columns):
        df["energy_step (kWh)"] = (df["power"].fillna(0) * (df["sample_interval"] / 3600.0) / 1000.0)
    else:
        df["energy_step (kWh)"] = 0.0

    # --- water production (cumulative L) from balance weight (g) ---
    if "weight" in df.columns:
        df["water_production"] = calculate_water_production(df["weight"])
    else:
        df["water_production"] = np.nan

    # --- flow & pump status (optional, for plotting only; not used in HE) ---
    # Flow total (L)
    if "flow_total" in df.columns:
        df["flow_total (L)"] = pd.to_numeric(df["flow_total"], errors="coerce")
    else:
        df["flow_total (L)"] = pd.Series(np.nan, index=df.index, dtype="float64")

    # Flow rate (L/min)
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

    # If total missing but rate exists, integrate to get total
    if df["flow_total (L)"].isna().all() and "sample_interval" in df.columns:
        step_L = (df["flow_rate (L/min)"].fillna(0) / 60.0) * df["sample_interval"].fillna(0)
        df["flow_total (L)"] = step_L.cumsum()

    # Pump status (optional)
    if "pump_status" in df.columns:
        df["pump_status"] = pd.to_numeric(df["pump_status"], errors="coerce").fillna(0).astype(int).clip(0, 1)
        df["pump_on"] = df["pump_status"] == 1
    else:
        df["pump_on"] = pd.Series(np.nan, index=df.index)  # present but unused

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

    # =============================
    # Harvesting efficiency — classic method with time-based 5-minute lag
    #   HE = 100 * production_step_lagged / intake_step
    #   * production_step from balance (nonnegative)
    #   * intake_step is raw per-sample intake (stable denominator)
    #   * lag is computed from the true sampling period
    # =============================
    # per-sample production (L)
    production_step = df["water_production"].diff().clip(lower=0)

    # compute how many rows ≈ 5 minutes
    lag_seconds = 300  # 5 minutes
    med_dt = df["sample_interval"].iloc[1:].median() if "sample_interval" in df.columns else 30
    if pd.isna(med_dt) or med_dt <= 0:
        med_dt = 30
    lag_n = max(1, int(round(lag_seconds / med_dt)))

    production_step_lagged = production_step.shift(-lag_n)

    # avoid divide-by-zero with a tiny intake floor only for numerical stability (no capping)
    denom = df["intake_step (L)"].replace(0, np.nan)
    with np.errstate(divide="ignore", invalid="ignore"):
        he = 100.0 * (production_step_lagged / denom)

    df["harvesting_efficiency"] = he.round(2)

    return df
