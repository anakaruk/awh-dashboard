
import streamlit as st
from google.cloud import firestore
import pandas as pd

st.set_page_config(page_title="AWH Station Dashboard", layout="wide")
st.title("📊 AWH Data Dashboard")

# Firestore init
db = firestore.Client()

# Get all station IDs
station_docs = db.collection("stations").stream()
station_ids = [doc.id for doc in station_docs]

station_id = st.selectbox("Select a station", station_ids)

if station_id:
    readings_ref = db.collection("stations").document(station_id).collection("readings")
    readings = readings_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(100).stream()

    data = []
    for doc in readings:
        row = doc.to_dict()
        row["timestamp"] = row.get("timestamp")
        data.append(row)

    if data:
        df = pd.DataFrame(data)
        st.dataframe(df)

        with st.expander("📈 Charts"):
            st.line_chart(df.set_index("timestamp")[["temperature", "humidity", "velocity"]])

        csv = df.to_csv(index=False)
        st.download_button("⬇️ Download CSV", csv, "data.csv", "text/csv")
    else:
        st.warning("No data found for this station.")
