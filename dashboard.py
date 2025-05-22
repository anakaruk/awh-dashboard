import streamlit as st
import os
import json
import pandas as pd
from google.cloud import firestore

# ✅ Must be before any UI
st.set_page_config(page_title="AWH Dashboard", layout="wide")

# Set up credentials from Streamlit secrets
service_account_raw = st.secrets["gcp_service_account"]
service_account_info = json.loads(service_account_raw)
key_path = "/tmp/service_account.json"
with open(key_path, "w") as f:
    json.dump(service_account_info, f)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

# Firestore client
db = firestore.Client()

# Load data
@st.cache_resource
def load_data():
    docs = db.collection("stations").document("station_1").collection("readings").stream()
    return pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in docs])

# UI rendering
st.title("📊 AWH Dashboard – Station 1 Readings")

try:
    df = load_data()
    if df.empty:
        st.warning("✅ Firestore is connected, but no data was found.")
    else:
        st.dataframe(df)

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            st.line_chart(df.set_index("timestamp").select_dtypes(include="number"))

        st.download_button("Download CSV", df.to_csv(index=False), file_name="station_readings.csv")

except Exception as e:
    st.error(f"Error: {e}")
