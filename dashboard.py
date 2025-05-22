import streamlit as st
import os
import json
import pandas as pd
from google.cloud import firestore

st.set_page_config(page_title="AWH Dashboard", layout="wide")

# 🔐 Load service account credentials from Streamlit secrets
service_account_info = json.loads(st.secrets["gcp_service_account"])
key_path = "/tmp/service_account.json"
with open(key_path, "w") as f:
    json.dump(service_account_info, f)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

# 🔌 Initialize Firestore
db = firestore.Client()

# 🚀 Get list of stations from Firestore
@st.cache_data(show_spinner=False)
def get_station_list():
    return [doc.id for doc in db.collection("stations").list_documents()]

station_list = get_station_list()
selected_station = st.selectbox("📍 Select a Station", station_list)

# 📦 Load readings for selected station
@st.cache_data(show_spinner=False)
def load_station_data(station_id):
    docs = db.collection("stations").document(station_id).collection("readings").stream()
    return pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in docs])

df = load_station_data(selected_station)

# 🖥️ Interface
st.title(f"📊 AWH Dashboard – {selected_station}")

if df.empty:
    st.warning(f"✅ Firestore connected, but no data found for `{selected_station}`.")
else:
    # Column selection
    all_columns = list(df.columns)
    selected_columns = st.multiselect("📌 Select columns to display", options=all_columns, default=[])

    if selected_columns:
        st.dataframe(df[selected_columns])
    else:
        st.info("Select one or more columns above to view data.")

    # Timestamp parsing and chart
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            chart_column = st.selectbox("📊 Select numeric column for chart", options=numeric_cols)
            st.line_chart(df.set_index("timestamp")[chart_column])

    # Export
    st.download_button("⬇️ Download CSV", df.to_csv(index=False), file_name=f"{selected_station}_readings.csv")
