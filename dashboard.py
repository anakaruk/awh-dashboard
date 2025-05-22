import streamlit as st
import os
import json

# Load credentials from Streamlit secrets
service_account_info = json.loads(st.secrets["gcp_service_account"])

# Save to temporary file
with open("/tmp/service_account.json", "w") as f:
    json.dump(service_account_info, f)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/service_account.json"

from google.cloud import firestore
import pandas as pd
