# 📥 Load data for a specific station, scoped by time window and fields
@st.cache_data(ttl=60)
def load_station_data(
    station_id: str,
    start: datetime = None,
    end: datetime = None,
    fields: list[str] = None,
    limit: int = None,
    order: str = "asc",
) -> pd.DataFrame:
    try:
        ref = (
            db.collection("stations")
              .document(station_id)
              .collection("readings")
        )

        # Add timestamp filters
        if start is not None:
            ref = ref.where("timestamp", ">=", start)
        if end is not None:
            ref = ref.where("timestamp", "<=", end)

        # Restrict fields
        if fields:
            # always include timestamp
            cols = list(set(fields) | {"timestamp"})
            ref = ref.select(cols)

        # Order
        direction = firestore.Query.ASCENDING if order == "asc" else firestore.Query.DESCENDING
        ref = ref.order_by("timestamp", direction=direction)

        # Limit if requested
        if limit:
            ref = ref.limit(limit)

        # Batch fetch
        snaps = ref.get(retry=RETRY)

        records = []
        for doc in snaps:
            data = doc.to_dict() or {}
            ts = data.get("timestamp")
            if isinstance(ts, datetime):
                dt = ts
            else:
                dt = pd.to_datetime(ts, utc=True, errors="coerce")
            data["timestamp"] = dt
            data["id"] = doc.id
            records.append(data)

        df = pd.DataFrame(records)
        if df.empty:
            return df

        return df.dropna(subset=["timestamp"]).sort_values("timestamp")

    except Exception as e:
        st.error(f"❌ Failed to load data for station `{station_id}`: {e}")
        return pd.DataFrame()
