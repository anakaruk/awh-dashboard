import pandas as pd
import math
import numpy as np
from typing import Optional

# -----------------------------
# Helper utilities
# -----------------------------

def _block_ids_from_resets(reset_flags: pd.Series) -> pd.Series:
    """Create monotonically increasing block ids that increment when reset flag is True."""
    if not isinstance(reset_flags, pd.Series):
        raise TypeError("reset_flags must be a pandas Series")
    rf = reset_flags.fillna(False).astype(bool)
    # cumsum starts at 0; when rf=True at a row, block id increments from that row onward
    return rf.astype(int).cumsum()


def _freeze_after_flag(series: pd.Series, freeze: Optional[pd.Series]) -> pd.Series:
    """Freeze (carry forward) cumulative series after the first True in freeze flag."""
    if freeze is None:
        return series
    f = freeze.fillna(False).astype(bool)
    if not f.any():
        return series.copy()
    out = series.copy()
    first_idx = f[f].index.min()
    if pd.isna(first_idx):
        return out
    # value to carry forward
    if first_idx > out.index.min():
        last_val = out.loc[first_idx - 1]
    else:
        last_val = out.loc[first_idx]
    out.loc[first_idx:] = last_val
    return out


def _apply_pause_mask(values: pd.Series, counting: Optional[pd.Series]) -> pd.Series:
    """Zero-out values where counting flag is False (paused). NaN treated as True."""
    if counting is None:
        return values
    keep = counting.fillna(True).astype(bool)
    return values.where(keep, 0)


def _safe_median(x: pd.Series, fallback: float) -> float:
    """Return median or a fallback if median is NaN/inf or series is empty."""
    if x is None or len(x) == 0:
        return fallback
    m = float(x.median())
    if np.isnan(m) or not np.isfinite(m):
        return fallback
    return m


# -----------------------------
# Core calculations
# -----------------------------

def calculate_absolute_humidity(temp_c, rel_humidity):
    try:
        numerator = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5)) * rel_humidity * 2.1674
        denominator = 273.15 + temp_c
        abs_humidity = numerator / denominator
        return round(abs_humidity, 2)
    except Exception as e:
        print(f"Error calculating AH: {e}")
        return None


def calculate_water_production(weight_series: pd.Series) -> pd.Series:
    """
    Accumulate produced water in liters from a balance trace that occasionally resets down.
    Stateless; resets are handled later by block-wise regrouping.
    """
    water_production = []
    total = 0.0
    prev = None

    for weight in weight_series:
        if pd.isnull(weight):
            water_production.append(None)
            continue

        w = float(weight)
        if prev is None:
            total = w
        elif w >= prev:
            total += (w - prev)
        prev = w
        water_production.append(total / 1000.0)  # g -> L

    return pd.Series(water_production, index=weight_series.index)


# -----------------------------
# Public API
# -----------------------------

def process_data(
    df: pd.DataFrame,
    intake_area: float = 1.0,
    lag_steps: int = 10,
    reset_col: Optional[str] = None,      # Boolean column: True where a new setup starts → reset accumulators
    count_col: Optional[str] = None,      # Boolean column: True = count, False = pause (stop counting)
    freeze_col: Optional[str] = None,     # Boolean column: when becomes True, freeze the cumulative outputs thereafter
    session_col: Optional[str] = None,    # Optional grouping key; accumulations are independent per session id
) -> pd.DataFrame:

    df = df.copy()

    # ---------------- Timestamp handling & interval ----------------
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        df["sample_interval"] = df["timestamp"].diff().dt.total_seconds()
        # use safe fallback 30s if median is NaN/invalid
        median_interval = _safe_median(df["sample_interval"].iloc[1:], 30.0)
        df["sample_interval"] = df["sample_interval"].fillna(median_interval)
        df.loc[df["sample_interval"] < 0, "sample_interval"] = median_interval

    # ---------------- Rename ingress/egress columns ----------------
    rename_map = {
        "velocity": "intake_air_velocity (m/s)",
        "temperature": "intake_air_temperature (C)",
        "humidity": "intake_air_humidity (%)",
        "outtake_velocity": "outtake_air_velocity (m/s)",
        "outtake_temperature": "outtake_air_temperature (C)",
        "outtake_humidity": "outtake_air_humidity (%)",
    }
    for old_col, new_col in rename_map.items():
        if old_col in df.columns:
            df.rename(columns={old_col: new_col}, inplace=True)

    # ---------------- Absolute humidity ----------------
    if {"intake_air_temperature (C)", "intake_air_humidity (%)"}.issubset(df.columns):
        df["absolute_intake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(
                row["intake_air_temperature (C)"], row["intake_air_humidity (%)"]
            ) if pd.notnull(row["intake_air_temperature (C)"]) and pd.notnull(row["intake_air_humidity (%)"]) else None,
            axis=1,
        )

    if {"outtake_air_temperature (C)", "outtake_air_humidity (%)"}.issubset(df.columns):
        df["absolute_outtake_air_humidity"] = df.apply(
            lambda row: calculate_absolute_humidity(
                row["outtake_air_temperature (C)"], row["outtake_air_humidity (%)"]
            ) if pd.notnull(row["outtake_air_temperature (C)"]) and pd.notnull(row["outtake_air_humidity (%)"]) else None,
            axis=1,
        )

    # ---------------- Internal calibration ----------------
    if {"absolute_intake_air_humidity", "absolute_outtake_air_humidity"}.issubset(df.columns):
        calibration_condition = ((df.index < 10) | (df.get("current", 0) < 2))
        if calibration_condition.sum() > 0:
            offset = (
                df.loc[calibration_condition, "absolute_intake_air_humidity"]
                - df.loc[calibration_condition, "absolute_outtake_air_humidity"]
            ).mean()
        else:
            offset = 0
        df["calibrated_outtake_air_humidity"] = df["absolute_outtake_air_humidity"] + offset

    # ---------------- Step terms ----------------
    # Intake water step (L)
    if {"absolute_intake_air_humidity", "intake_air_velocity (m/s)", "sample_interval"}.issubset(df.columns):
        step_intake = []
        for _, row in df.iterrows():
            ah = row["absolute_intake_air_humidity"]
            vel = row["intake_air_velocity (m/s)"]
            interval = row["sample_interval"]
            if pd.notnull(ah) and pd.notnull(vel) and pd.notnull(interval) and vel > 0:
                intake = ah * vel * float(intake_area) * float(interval) / 1000.0
            else:
                intake = 0.0
            step_intake.append(intake)
        df["intake_step (L)"] = pd.Series(step_intake, index=df.index)
    else:
        df["intake_step (L)"] = 0.0

    # Energy step (kWh) from instantaneous power (W)
    if {"power", "timestamp"}.issubset(df.columns):
        try:
            freq_seconds = _safe_median(df["timestamp"].diff().dt.total_seconds().iloc[1:], 0.0)
            freq_hours = freq_seconds / 3600.0
            df["energy_step_from_power (kWh)"] = (df["power"] * freq_hours) / 1000.0
        except Exception as e:
            print(f"❌ Error calculating energy from power: {e}")
            df["energy_step_from_power (kWh)"] = 0.0
    else:
        df["energy_step_from_power (kWh)"] = 0.0

    # ---------------- Optional water cumulative from weight ----------------
    if "weight" in df.columns:
        # Build a raw cumulative from weight just to preserve your original logic,
        # but we will convert it to block-wise steps later so it starts at 0 in each block.
        df["water_production_raw"] = calculate_water_production(df["weight"])
    else:
        df["water_production_raw"] = np.nan
        print("⚠️ No 'weight' column found for water production")

    # ---------------- Apply pause (counting) mask to step terms *before* cumsums ----------------
    counting = df[count_col] if (count_col and count_col in df.columns) else None
    df["intake_step (L)"] = _apply_pause_mask(df["intake_step (L)"], counting)
    df["energy_step (kWh)"] = _apply_pause_mask(df["energy_step_from_power (kWh)"], counting)

    # ---------------- Build reset blocks (per session then per reset) ----------------
    if session_col and session_col in df.columns:
        if reset_col and reset_col in df.columns:
            df["_block_id"] = (
                df.groupby(session_col)[reset_col]
                  .apply(lambda s: _block_ids_from_resets(s))
                  .reset_index(level=0, drop=True)
            )
        else:
            df["_block_id"] = df.groupby(session_col).ngroup()
    else:
        if reset_col and reset_col in df.columns:
            df["_block_id"] = _block_ids_from_resets(df[reset_col])
        else:
            df["_block_id"] = 0

    # ---------------- Block-wise accumulations (start at 0 exactly at reset row) ----------------
    df["accumulated_intake_water"] = df.groupby("_block_id")["intake_step (L)"].cumsum().round(3)
    df["accumulated_energy (kWh)"] = df.groupby("_block_id")["energy_step (kWh)"].cumsum().round(6)

    # Water production: convert raw cumulative to steps, mask by counting, then cumsum per block
    if "water_production_raw" in df.columns:
        prod_step = df.groupby("_block_id")["water_production_raw"].diff()   # step per row within block
        prod_step = prod_step.clip(lower=0).fillna(0.0)                      # first row of block = 0
        prod_step = _apply_pause_mask(prod_step, counting)                   # respect pause
        df["production_step (L)"] = prod_step
        df["water_production"] = df.groupby("_block_id")["production_step (L)"].cumsum().round(3)
    else:
        df["production_step (L)"] = 0.0
        df["water_production"] = 0.0

    # ---------------- Freeze outputs after a flag ----------------
    freeze = df[freeze_col] if (freeze_col and freeze_col in df.columns) else None
    if freeze is not None and freeze.fillna(False).any():
        for _, idx in df.groupby("_block_id").groups.items():
            sub = df.loc[idx]
            f = sub[freeze_col].fillna(False).astype(bool)
            df.loc[idx, "accumulated_intake_water"] = _freeze_after_flag(sub["accumulated_intake_water"], f)
            df.loc[idx, "water_production"] = _freeze_after_flag(sub["water_production"], f)
            df.loc[idx, "accumulated_energy (kWh)"] = _freeze_after_flag(sub["accumulated_energy (kWh)"], f)

    # ---------------- Hourly energy-per-liter (use our step terms after masking) ----------------
    if "timestamp" in df.columns:
        df["timestamp_hour"] = df["timestamp"].dt.floor("H")
        # step-based EPL per row; ignore rows with zero water step to avoid division by zero
        df["step_energy_per_liter"] = df.apply(
            lambda r: (r["energy_step (kWh)"] / r["production_step (L)"]) if r.get("production_step (L)", 0) > 0 else None,
            axis=1,
        )
        hourly = (
            df.groupby("timestamp_hour")["step_energy_per_liter"]
              .mean()
              .rename("energy_per_liter (kWh/L)")
              .reset_index()
        )
        df = df.merge(hourly, on="timestamp_hour", how="left")

    # ---------------- Harvesting efficiency ----------------
    if {"accumulated_intake_water", "water_production"}.issubset(df.columns):
        df["intake_step"] = df.groupby("_block_id")["accumulated_intake_water"].diff()
        df["production_step_no_lag"] = df.groupby("_block_id")["water_production"].diff()
        df["production_step_lagged"] = df.groupby("_block_id")["production_step_no_lag"].shift(-int(lag_steps))
        df["harvesting_efficiency"] = df.apply(
            lambda row: round((row["production_step_lagged"] / row["intake_step"]) * 100, 2)
            if pd.notnull(row["production_step_lagged"]) and pd.notnull(row["intake_step"]) and row["intake_step"] > 0
            else 0.0,
            axis=1,
        )

    return df
