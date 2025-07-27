import os
import subprocess
import pandas as pd
import requests

# --- Voip.ms SMS Class ---
class VoipMS:
    """A simple class to send SMS messages using the Voip.ms API."""
    def __init__(self, username: str, password: str):
        self.params: dict[str, str] = {
            "api_username": username,
            "api_password": password,
        }
        self.url = "https://voip.ms/api/v1/rest.php"

    def send_sms(self, did: str, destination: str, message: str) -> dict:
        """Sends an SMS message."""
        sms_params = {
            "method": "sendSMS",
            "did": did,
            "dst": destination,
            "message": message
        }
        all_params = self.params.copy()
        all_params.update(sms_params)
        try:
            response = requests.get(self.url, params=all_params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"status": "error", "error": f"Request failed: {e}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

# --- Script Configuration ---
# Load from environment variables for security
API_USERNAME = os.getenv("VOIPMS_USERNAME")
API_PASSWORD = os.getenv("VOIPMS_API_PASSWORD")
FROM_DID = os.getenv("VOIPMS_DID")      # Your SMS-enabled VoIP.ms number
TO_NUMBER = os.getenv("VOIPMS_TO_NUMBER") # Your cell phone number

# FRED Data Configuration
DATA_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=ICSA"
LOCAL_FILE = "ICSA.csv"

# --- Step 1: Download Data ---
print(f"Attempting to download latest data (ICSA) to '{LOCAL_FILE}'...")
try:
    result = subprocess.run(
        ["/usr/bin/curl", "-sS", "-L", "-o", LOCAL_FILE, DATA_URL], check=True
    )
    print("✅ Download successful.")
except (subprocess.CalledProcessError, FileNotFoundError) as e:
    print(f"‼️ Automatic download failed: {e}. Check if 'curl' is installed.")
    exit() # Exit if we can't get the data

# --- Step 2: Load and Process Data ---
try:
    with open(LOCAL_FILE, 'r') as f:
        for i, line in enumerate(f):
            if "observation_date,ICSA" in line:
                break
    unemployment_data = pd.read_csv(LOCAL_FILE, skiprows=i, index_col='observation_date', parse_dates=True)
    unemployment_data.rename(columns={'ICSA': 'Initial Claims'}, inplace=True)
    unemployment_data['Initial Claims'] = pd.to_numeric(unemployment_data['Initial Claims'], errors='coerce')
    unemployment_data.dropna(inplace=True)
except Exception as e:
    print(f"An error occurred while processing the data: {e}")
    unemployment_data = None

# --- Step 3: Analyze Data and Send SMS ---
if unemployment_data is not None:       
    latest_data = unemployment_data.iloc[-1]
    latest_value = latest_data['Initial Claims']
    four_week_ma = latest_data.rolling(window=4).mean()['Initial Claims']
    is_unusual_increase = latest_value > (four_week_ma * 1.15) # Check for a 15% jump over 4-week MA

    # Print console report
    print("\n--- Initial Unemployment Claims Analysis (Seasonally Adjusted) ---")
    print(f"Latest Data Point: {latest_data.name.strftime('%Y-%m-%d')}")
    print(f"Initial Claims: {latest_value:,.0f}")
    
    # Construct a concise SMS message
    status_emoji = "⚠️" if is_unusual_increase else "✅"
    status_text = "Warning" if is_unusual_increase else "OK"
    sms_message = f"Jobs Alert {status_emoji} {status_text}: Initial claims at {latest_value:,.0f}."
    
    # Check for credentials and send SMS
    if all([API_USERNAME, API_PASSWORD, FROM_DID, TO_NUMBER]):
        print(f"\nAttempting to send SMS: '{sms_message}'")
        voip = VoipMS(API_USERNAME, API_PASSWORD)
        response = voip.send_sms(FROM_DID, TO_NUMBER, sms_message)
        if response.get("status") == "success":
            print("✅ SMS sent successfully.")
        else:
            print(f"‼️ SMS failed to send. Response: {response}")
    else:
        print("\nSMS credentials not set in environment variables. Skipping notification.")
