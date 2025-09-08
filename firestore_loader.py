import os
import json
import pandas as pd
from google.cloud import firestore
from google.api_core.retry import Retry
import streamlit as st
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
        # list_documents supports retry
        for station_ref in db.collection("stations").list_documents(page_size=1000, retry=RETRY):
            # Use .get(retry=...) (short-lived) instead of .stream()
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

# 📥 Load data for a specific station, sorted by timestamp (batched; no long-lived stream)
@st.cache_data(ttl=60)
def load_station_data(station_id: str) -> pd.DataFrame:
    try:
        base = (
            db.collection("stations")
              .document(station_id)
              .collection("readings")
              .order_by("timestamp", direction=firestore.Query.ASCENDING)
        )

        batch_size = 2000
        cursor = None
        records = []

        while True:
            q = base.limit(batch_size)
            if cursor is not None:
                q = q.start_after(cursor)
            snaps = q.get(retry=RETRY)  # short RPC; avoids the streaming/_retry bug
            if not snaps:
                break

            for doc in snaps:
                data = (doc.to_dict() or {}).copy()
                data["id"] = doc.id
                ts = data.get("timestamp")
                if isinstance(ts, datetime):
                    dt = ts
                else:
                    dt = pd.to_datetime(ts, utc=True, errors="coerce")
                data["timestamp"] = dt
                records.append(data)

            cursor = snaps[-1]  # page forward

        df = pd.DataFrame(records)
        if df.empty:
            st.info(f"ℹ️ No records found for station `{station_id}`.")
            return df

        return df.dropna(subset=["timestamp"]).sort_values("timestamp")

    except Exception as e:
        st.error(f"❌ Failed to load data for station `{station_id}`: {e}")
        return pd.DataFrame()
