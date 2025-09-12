# firestore_loader.py — optimized Firestore loader with window + field selection
import os
import json
import pandas as pd
import streamlit as st
from google.cloud import firestore
from google.api_core.retry import Retry
from datetime import datetime

# Global retry for Firestore reads (handles transient 503/timeout cases)
RETRY = Retry()

# 🔐 Load credentials from Streamlit secrets
@st.cache_resource
def get_firestore_client():
    try:
        raw = st.secrets.get("gcp_service_account")
        service_account_info = json.loads(raw) if isinstance(raw, str) else dict(raw)
        key_path = "/tmp/service_account.json"
        with open(key_path, "w") as f:
            json.dump(service_account_info, f)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
        return firestore.Client()
    except Exception as e:
        st.error(f"❌ Failed to initialize Firestore client: {e}")
        raise

# 🔌 Initialize Firestore client
db = get_firestore_client()

# 📡 Get list of stations that have at least one reading
@st.cache_data(ttl=60)
def get_station_list():
    try:
        station_ids_with_data = []
        for station_ref in db.collection("stations").list_documents(page_size=1000, retry=RETRY):
            has_one = bool(
                db.collection("stations")
                  .document(station_ref.id)
                  .collection("readings")
                  .limit(1)
                  .get(retry=RETRY)
            )
            if has_one:
                station_ids_with_data.append(station_ref.id)
        return sorted(station_ids_with_data)
    except Exception as e:
        st.error(f"❌ Error loading station list: {e}")
        return []

# 📥 Load data for a specific station (window + field scoping)
@st.cache_data(ttl=120)
def load_station_data(
    station_id: str,
    start: datetime = None,
    end: datetime = None,
    fields: list[str] = None,
    limit: int = None,
    order: str = "asc",
) -> pd.DataFrame:
    try:
        ref = db.collection("stations").document(station_id).collection("readings")

        # ---- Normalize start/end to naive UTC ----
        def _to_utc_naive(dt):
            if dt is None:
                return None
            ts = pd.to_datetime(dt, utc=True)
            return ts.to_pydatetime().replace(tzinfo=None)

        start_utc = _to_utc_naive(start)
        end_utc = _to_utc_naive(end)

        if start_utc:
            ref = ref.where("timestamp", ">=", start_utc)
        if end_utc:
            ref = ref.where("timestamp", "<=", end_utc)

        # ---- Field selection (always include timestamp) ----
        if fields:
            cols = list(set(fields) | {"timestamp"})
            ref = ref.select(cols)

        # ---- Ordering ----
        direction = firestore.Query.ASCENDING if order == "asc" else firestore.Query.DESCENDING
        ref = ref.order_by("timestamp", direction=direction)

        # ---- Limit ----
        if limit:
            ref = ref.limit(limit)

        # ---- Run query ----
        snaps = ref.get(retry=RETRY)

        records = []
        for doc in snaps:
            data = doc.to_dict() or {}
            ts = data.get("timestamp")
            if isinstance(ts, datetime):
                dt = pd.to_datetime(ts, utc=True)
            else:
                dt = pd.to_datetime(ts, utc=True, errors="coerce")
            data["timestamp"] = dt
            data["id"] = doc.id
            records.append(data)

        df = pd.DataFrame(records)
        if df.empty:
            return df

        return df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    except Exception as e:
        st.error(f"❌ Failed to load data for station `{station_id}`: {e}")
        return pd.DataFrame()
