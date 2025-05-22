import streamlit as st
import os
import json
import pandas as pd
from google.cloud import firestore

st.set_page_config(page_title="AWH Dashboard", layout="wide")

# 🔐 Load credentials
service_account_info = json.loads(st.secrets["gcp_service_account"])
key_path = "/tmp/service_account.json"
with open(key_path, "w") as f:
    json.dump(service_account_info, f)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

# 🔌 Firestore client
db = firestore.Client()

# 📡 Get station list
@st.cache_data
def get_station_list():
    return [doc.id for doc in db.collection("stations").list_documents()]

# 📥 Load station data
@st.cache_data
def load_station_data(station_id):
    docs = db.collection("stations").document(station_id).collection("readings").stream()
    return pd.DataFrame([doc.to_dict() | {"id": doc.id} for doc in docs])

# 🧭 Sidebar UI
with st.sidebar:
    st.header("🔧 Controls")
    selected_station = st.selectbox("📍 Select Station", get_station_list())

    show_weight = st.checkbox("⚖️ Weight", value=False)
    show_power = st.checkbox("🔌 Power", value=False)
    show_temp = st.checkbox("🌡️ Intake Air Temp", value=False)

# 📊 Load data
df = load_station_data(selected_station)

st.title(f"📊 AWH Dashboard – {selected_station}")

if df.empty:
    st.warning("No data found.")
else:
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Determine fields to display
    selected_fields = []
    if show_weight and "weight" in df.columns:
        selected_fields.append("weight")
    if show_power and "power" in df.columns:
        selected_fields.append("power")
    if show_temp and "temperature" in df.columns:
        selected_fields.append("temperature")

    if selected_fields:
        for field in selected_fields:
            st.subheader(f"📊 `{field}` Data")

            col1, col2 = st.columns([1, 3], gap="large")

            with col1:
                st.markdown("#### 📋 Table")
                st.dataframe(df[["timestamp", field]], use_container_width=True)

                st.download_button(
                    label=f"⬇️ Download `{field}` CSV",
                    data=df[["timestamp", field]].to_csv(index=False),
                    file_name=f"{selected_station}_{field}.csv",
                    mime="text/csv"
                )

            with col2:
                st.markdown("#### 📈 Plot")
                df_sorted = df.sort_values("timestamp")
                st.line_chart(df_sorted.set_index("timestamp")[field])
    else:
        st.info("☝️ Please select at least one data type from the sidebar to view and plot.")
