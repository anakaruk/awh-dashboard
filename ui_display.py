import pandas as pd
import math
from typing import Iterable, Optional

# -----------------------------
# Helper utilities
# -----------------------------

def _block_ids_from_resets(reset_flags: pd.Series) -> pd.Series:
    """Create monotonically increasing block ids that increment when reset flag is True.
    If reset_flags is missing or all False, all rows get block id 0.
    """
    if reset_flags is None:
        return pd.Series(0, index=pd.RangeIndex(len(reset_flags)))  # type: ignore
    rf = reset_flags.fillna(False).astype(bool)
    return rf.astype(int).cumsum()


def _cumsum_with_resets(values: pd.Series, reset_flags: Optional[pd.Series] = None) -> pd.Series:
    """Cumulative sum that restarts to 0 whenever reset_flags is True.
    If reset_flags is None, behaves like normal cumsum.
    """
    if reset_flags is None:
        return values.cumsum()
    blocks = _block_ids_from_resets(reset_flags)
    return values.groupby(blocks).cumsum()


def _freeze_after_flag(series: pd.Series, freeze: Optional[pd.Series]) -> pd.Series:
    """Freeze (carry forward) cumulative series after the first True in freeze flag.
    If freeze is None or never True, returns the series unchanged.
    """
    if freeze is None or not freeze.any():
        return series
    out = series.copy()
    # identify the first index where freeze is True
    first_idx = freeze[freeze.fillna(False)].index.min()
    if pd.isna(first_idx):
        return out
    # carry-forward last value from just before first freeze-True row
    # The row where freeze becomes True should also be frozen
    last_val = out.loc[first_idx - 1] if first_idx > out.index.min() else out.loc[first_idx]
    out.loc[first_idx:] = last_val
    return out


def _apply_pause_mask(values: pd.Series, counting: Optional[pd.Series]) -> pd.Series:
    """Zero-out values where counting flag is False (i.e., paused). If counting is None, return values.
    Accepts True/False/1/0; NaN treated as True (keep counting).
    """
    if counting is None:
        return values
    keep = counting.fillna(True).astype(bool)
    return values.where(keep, 0)


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
    """Accumulate produced water in liters from a balance trace that occasionally resets down.
    This function is stateless; to reset the accumulation between setups, pass a reset flag
    to process_data() which will regroup the running total.
    """
    water_production = []
    total = 0.0
    prev = None

    for weight in weight_series:
        if pd.isnull(weight):
            water_production.append(None)
            continue

        if prev is None:
            total = float(weight)
        elif weight >= prev:
            total += (float(weight) - float(prev))
        prev = float(weight)
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
    """
    Enhanced version of data-play with controls to:
      1) Reset cumulative calculations when setup changes (reset_col) or when session id changes (session_col)
      2) Temporarily pause counting (count_col=False)
      3) Freeze cumulative outputs from a point onward (freeze_col=True)

    Controls (optional):
      - reset_col: a boolean column in df. When True on a row, all *cumulative* series restart from zero on that row.
      - count_col: a boolean column in df. Where False, we zero-out *step* terms so they don't add to accumulations.
      - freeze_col: a boolean column in df. From the first True onward, cumulative outputs stay constant (carry-forward).
      - session_col: a key to compute everything per session/device/station; cumsums do not cross sessions.

    Notes:
      - If both session_col and reset_col are provided, resets happen *within each session* independently.
      - If none of these control columns are provided, behavior matches the previous implementation.
    """

    df = df.copy()

    # ---------------- Timestamp handling & interval ----------------
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        df["sample_interval"] = df["timestamp"].diff().dt.total_seconds()
        median_interval = df["sample_interval"].iloc[1:].median()
        df["sample_interval"] = df["sample_interval"].fillna(median_interval or 30)
        df.loc[df["sample_interval"] < 0, "sample_interval"] = median_interval or 30

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

    # ---------------- Water production from weight ----------------
    if "weight" in df.columns:
        df["water_production"] = calculate_water_production(df["weight"])  # L (running total; will reset later)
    else:
        print("⚠️ No 'weight' column found for water production")

    # ---------------- Intake water accumulation (from AH & velocity) ----------------
    if {"absolute_intake_air_humidity", "intake_air_velocity (m/s)", "sample_interval"}.issubset(df.columns):
        # Step intake volume per row (L)
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

    # ---------------- Energy from power ----------------
    if {"power", "timestamp"}.issubset(df.columns):
        try:
            freq_seconds = df["timestamp"].diff().dt.total_seconds().median()
            freq_hours = freq_seconds / 3600 if pd.notnull(freq_seconds) else 0
            df["energy_step_from_power (kWh)"] = (df["power"] * freq_hours) / 1000.0
        except Exception as e:
            print(f"❌ Error calculating energy from power: {e}")
            df["energy_step_from_power (kWh)"] = 0.0
    else:
        df["energy_step_from_power (kWh)"] = 0.0

    # ---------------- Hourly energy per liter (diagnostic) ----------------
    if {"timestamp", "power"}.issubset(df.columns):
        df["timestamp_hour"] = df["timestamp"].dt.floor("H")
        # A monotonic proxy for energy if your power is already cumulative in Wh; otherwise use energy_step_from_power
        df["energy_step (Wh)"] = df["power"].diff().clip(lower=0).fillna(0)
        df["energy_step (kWh)"] = df["energy_step (Wh)"] / 1000.0
        if "weight" in df.columns:
            df["weight_diff"] = df["weight"].diff().clip(lower=0).fillna(0)
            df["water_step (L)"] = df["weight_diff"] / 1000.0
        else:
            df["water_step (L)"] = 0.0
        df["step_energy_per_liter"] = df.apply(
            lambda row: (row["energy_step (kWh)"] / row["water_step (L)"]) if row["water_step (L)"] > 0 else None,
            axis=1,
        )
        hourly = (
            df.groupby("timestamp_hour")["step_energy_per_liter"].mean().rename("energy_per_liter (kWh/L)").reset_index()
        )
        df = df.merge(hourly, on="timestamp_hour", how="left")

    # ---------------- Apply counting (pause) mask to step terms ----------------
    counting = df[count_col] if (count_col and count_col in df.columns) else None
    df["intake_step (L)"] = _apply_pause_mask(df["intake_step (L)"], counting)
    if "water_step (L)" in df.columns:
        df["water_step (L)"] = _apply_pause_mask(df["water_step (L)"], counting)
    df["energy_step_from_power (kWh)"] = _apply_pause_mask(df["energy_step_from_power (kWh)"], counting)

    # ---------------- Build reset blocks (per session, then per reset) ----------------
    if session_col and session_col in df.columns:
        # compute per-session block ids that also bump when reset_col=True
        if reset_col and reset_col in df.columns:
            df["_block_id"] = (
                df.groupby(session_col)[reset_col].apply(lambda s: _block_ids_from_resets(s)).reset_index(level=0, drop=True)
            )
        else:
            # one block per session
            df["_block_id"] = df.groupby(session_col).ngroup()
    else:
        # single session; blocks only from resets
        if reset_col and reset_col in df.columns:
            df["_block_id"] = _block_ids_from_resets(df[reset_col])
        else:
            df["_block_id"] = 0

    # ---------------- Accumulate within blocks ----------------
    df["accumulated_intake_water"] = df.groupby(["_block_id"])['intake_step (L)'].cumsum().round(3)

    if "water_production" in df.columns:
        # Make water_production a *block-wise* running total based on positive weight increases
        # First derive per-row production step from the already-built running total
        prod_step = df.groupby("_block_id")["water_production"].diff().fillna(df["water_production"])  # L
        prod_step = prod_step.clip(lower=0)
        df["production_step (L)"] = prod_step
        df["water_production"] = df.groupby("_block_id")["production_step (L)"].cumsum().round(3)

    # Energy accumulations per block
    df["energy_step (kWh)"] = df["energy_step_from_power (kWh)"]
    df["accumulated_energy (kWh)"] = df.groupby(["_block_id"])['energy_step (kWh)'].cumsum().round(6)

    # ---------------- Freeze outputs after a flag ----------------
    freeze = df[freeze_col] if (freeze_col and freeze_col in df.columns) else None
    if freeze is not None and freeze.any():
        # Freeze independently per (session, block)
        for _, idx in df.groupby(["_block_id"]).groups.items():
            sub = df.loc[idx]
            f = sub[freeze_col]
            df.loc[idx, "accumulated_intake_water"] = _freeze_after_flag(sub["accumulated_intake_water"], f)
            if "water_production" in df.columns:
                df.loc[idx, "water_production"] = _freeze_after_flag(sub["water_production"], f)
            df.loc[idx, "accumulated_energy (kWh)"] = _freeze_after_flag(sub["accumulated_energy (kWh)"], f)

    # ---------------- Harvesting efficiency ----------------
    if {"accumulated_intake_water", "water_production"}.issubset(df.columns):
        df["intake_step"] = df.groupby(["_block_id"])['accumulated_intake_water'].diff()
        df["production_step"] = df.groupby(["_block_id"])['water_production'].diff()
        df["production_step_lagged"] = df.groupby(["_block_id"])['production_step'].shift(-int(lag_steps))
        df["harvesting_efficiency"] = df.apply(
            lambda row: round((row["production_step_lagged"] / row["intake_step"]) * 100, 2)
            if pd.notnull(row["production_step_lagged"]) and pd.notnull(row["intake_step"]) and row["intake_step"] > 0
            else 0.0,
            axis=1,
        )

    # Cleanup helper columns
    return df
