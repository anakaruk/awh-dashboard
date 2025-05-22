import streamlit as st
from google.cloud import firestore
import pandas as pd
import os

# Title
st.set_page_config(page_title="AWH Dashboard", layout="wide")
st.title("📊 AWH Dashboard – Station 1 Readings")

# Firestore connection
@st.cache_resource
def get_firestore_data():
    db = firestore.Client()
    docs = db.collection("stations").document("station_1").collection("readings").stream()
    data = []
    for doc in docs:
        d = doc.to_dict()
        d['id'] = doc.id
        data.append(d)
    return pd.DataFrame(data)

# Load data
try:
    df = get_firestore_data()

    if df.empty:
        st.warning("⚠️ No data found in Firestore.")
    else:
        # Timestamp conversion
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        st.subheader("📋 Full Table View")
        st.dataframe(df)

        # Column selection
        numeric_cols = df.select_dtypes(include='number').columns.tolist()
        if 'timestamp' in df.columns:
            x_options = [']()_
