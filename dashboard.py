import streamlit as st
import os
import json

# This string is already JSON
service_account_raw = st.secrets["gcp_service_account"]

# Now parse it into a Python dict
service_account_info = json.loads(service_account_raw)

# Write to file
key_path = "/tmp/service_account.json"
with open(key_path, "w") as f:
    json.dump(service_account_info, f)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

from google.cloud import firestore
