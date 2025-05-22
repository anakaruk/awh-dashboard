import streamlit as st
import os
import json
import pandas as pd
from google.cloud import firestore

# Load service account key from Streamlit Secrets
service_account_info = json.loads(st.secrets["gcp_service_account"])
key_path = "/tmp/service_account.json"
with open(key_path, "w") as f:
    json.dump(service_account_info, f)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

# Firestore client
db = firestore.Client()

st.set_page_config(page_title="AWH Dashboard", layout="wide")
st.title("📊 AWH Dashboard – Station 1 Readings")

@st.cache_resource
def load_data():
    collection_ref = db.collection("stations").document("station_1").collection("readings")
    docs = collection_ref.stream()
    records = []
    for doc in docs:
        row = doc.to_dict()
        row["doc_id"] = doc.id
        records.append(row)
    return pd.DataFrame(records)

try:
    df = load_data()
    if df.empty:
        st.warning("⚠️ Firestore is connected, but no data found in `stations/station_1/readings`.")
        st.info("You can manually check in Firestore console.")
    else:
        st.subheader("Raw Data")
        st.dataframe(df)

        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            st.line_chart(df.set_index("timestamp").select_dtypes(include='number'))

        st.download_button("Download CSV", df.to_csv(index=False), file_name="readings.csv")

except Exception as e:
    st.error(f"Error: {e}")
