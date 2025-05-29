import os
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# Load Firestore credentials from a service account key file
FIRESTORE_KEY = os.getenv("FIRESTORE_KEY", "firebase-key.json")
if not firebase_admin._apps:
    cred = credentials.Certificate(FIRESTORE_KEY)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- CONFIGURATION ---

COLLECTION_NAME = "station_data"  # <-- Change if your Firestore collection has a different name
STATION_FIELD = "station_name"    # <-- Use "station_name" field to identify stations

def get_station_list():
    """
    Returns a sorted list of unique station_name entries found in the Firestore collection.
    """
    docs = db.collection(COLLECTION_NAME).stream()
    station_set = set()
    for doc in docs:
        data = doc.to_dict()
        station = data.get(STATION_FIELD)
        if station:
            station_set.add(station)
    return sorted(list(station_set))

def load_station_data(station_name):
    """
    Loads all documents for a given station_name from the Firestore collection and returns as a DataFrame.
    """
    docs = db.collection(COLLECTION_NAME).where(STATION_FIELD, "==", station_name).stream()
    records = [doc.to_dict() for doc in docs]
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)
