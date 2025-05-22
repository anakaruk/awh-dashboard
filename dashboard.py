import pandas as pd

st.set_page_config(page_title="AWH Dashboard", layout="wide")
st.title("📊 AWH Dashboard – Station 1 Readings")

# Create Firestore client
db = firestore.Client()

# Load data
@st.cache_resource
def load_data():
    collection_ref = db.collection("stations").document("station_1").collection("readings")
    docs = collection_ref.stream()
    data = []
    for doc in docs:
        row = doc.to_dict()
        row["id"] = doc.id
        data.append(row)
    return pd.DataFrame(data)

# Display data
try:
    df = load_data()
    if df.empty:
        st.warning("✅ Connected to Firestore, but no data found in `station_1/readings`.")
    else:
        st.subheader("📋 Readings Table")
        st.dataframe(df)

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            st.line_chart(df.set_index("timestamp").select_dtypes(include="number"))

        st.download_button("⬇ Download CSV", df.to_csv(index=False), "station_readings.csv")
except Exception as e:
    st.error(f"❌ Failed to load or show data: {e}")
