import streamlit as st
import os
import json
import pandas as pd
from google.cloud import firestore

st.set_page_config(page_title="AWH Dashboard", layout="wide")

# 🔐 Credentials
service_account_info = json.loads(st.secrets["gcp_service_account"])
with open("/tmp/service_account.json", "w") as f:
    json.dump(service_account_info, f)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/service_account.json"

db = firestore.Client()

@st.cache_data
def get_station_list():
    return [doc.id for doc in db.collection("stations").list_documents()]

@st.cache_data
def load_station_data(station_id):
    docs = db.collection("stations").document(station_id).collection("readings").stream()
    return pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in docs])

# 🔹 Sidebar layout
with st.sidebar:
    st.header("🔧 Controls")
    selected_station = st.selectbox("📍 Station", get_station_list())
    show_date = st.checkbox("🗓️ Date/time", value=False)
    show_weight = st.checkbox("⚖️ Weight", value=False)
    show_power = st.checkbox("🔌 Power", value=False)
    show_temp = st.checkbox("🌡️ Intake air temp", value=False)

df = load_station_data(selected_station)

st.title(f"📊 AWH Dashboard – {selected_station}")

if df.empty:
    st.warning("No data found.")
else:
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 💾 Decide what to show based on checkboxes
    selected_fields = ["timestamp"]
    if show_weight and "weight" in df.columns:
        selected_fields.append("weight")
    if show_power and "power" in df.columns:
        selected_fields.append("power")
    if show_temp and "temperature" in df.columns:
        selected_fields.append("temperature")

    # 📋 Show table
    st.subheader("📋 Data Table")
    st.dataframe(df[selected_fields])

    # 📥 Optional: CSV export
    st.download_button("⬇️ Download CSV", df[selected_fields].to_csv(index=False), file_name=f"{selected_station}_data.csv")

            else:
                st.info("No data selected to plot.")
