
import sched
import time
import json
import requests

from fastapi import FastAPI, Form
from threading import Thread

app = FastAPI()

# Initialize scheduler
scheduler = sched.scheduler(time.time, time.sleep)

# URL of the government website to fetch data from
government_data_url = "https://cbic-gst.gov.in/gst-goods-services-rates.html"

# Function to fetch data from the government website and update the JSON file
def fetch_and_update_government_data():
    global government_data
    try:
        response = requests.get(government_data_url)
        if response.status_code == 200:
            government_data = response.json()
            with open("output.json", "w", encoding="utf-8") as file:
                json.dump(government_data, file, indent=4)
                print("Government dataset updated successfully.")
        else:
            print(f"Failed to fetch data from the government website. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error occurred while fetching data: {e}")

# Function to periodically fetch and update government dataset
def update_government_data(sc):
    fetch_and_update_government_data()
    scheduler.enter(3600, 1, update_government_data, (sc,))  # Schedule next update after 1 hour

# Schedule initial update
scheduler.enter(0, 1, update_government_data, (scheduler,))

# Load initial government dataset from JSON file
with open("output.json", "r", encoding="utf-8") as file:
    government_data = json.load(file)

# Dataset of products with their GST rates
products = [
    {"HSN": "1234", "gst_rate_percent": 5, "tariff_item_number": "12345"},
    # Add other products with their GST rates and tariff item numbers
]

def calculate_gst(amount, gst_rate):
    # Convert gst_rate to float if it's a string
    if isinstance(gst_rate, str):
        gst_rate = float(gst_rate.rstrip('%')) / 100  # Remove '%' sign and convert to float

    cgst_rate = gst_rate / 2
    sgst_rate = gst_rate / 2
    igst_rate = gst_rate

    cgst = (amount * cgst_rate)
    sgst = (amount * sgst_rate)
    utgst = 0  # UTGST is not used in this calculation
    igst = (amount * igst_rate)

    return cgst, sgst, utgst, igst


def calculate_amount_including_gst(amount, gst_rate):
    cgst, sgst, _, _ = calculate_gst(amount, gst_rate)
    total_gst = cgst + sgst
    return amount + total_gst

def calculate_gst_details(amount, gst_rate):
    cgst, sgst, utgst, igst = calculate_gst(amount, gst_rate)
    return cgst, sgst, utgst, igst

@app.post("/calculate_gst/")
async def calculate_gst_endpoint(
    HSN: str = Form(..., description="HSN of the product"),
    amount: float = Form(..., description="Price of the product"),
    quantity: int = Form(1, description="Quantity of the product"),
):
    # Retrieve GST rate and tariff item number from government dataset based on HSN
    for product in government_data:
        if product["Chapter\n\n  / Heading / Sub-heading / Tariff item"] == HSN:
            gst_rate_percent = product["IGST Rate\n\n  (%)"]
            tariff_item_number = product["S. No."]
            break
    else:
        # If product not found in dataset, assume a default GST rate of 18%
        gst_rate_percent = 18
        tariff_item_number = "Unknown"

    cgst, sgst, utgst, igst = calculate_gst_details(amount, gst_rate_percent)
    amount_including_gst = calculate_amount_including_gst(amount * quantity, gst_rate_percent)

    return {
        "HSN": HSN,
        "Tariff_Item_Number": tariff_item_number,
        "CGST": cgst,
        "SGST": sgst,
        "UTGST": utgst,
        "IGST": igst,
        "Amount_excluding_GST": amount * quantity,
        "Amount_including_GST": amount_including_gst,
        "GST": igst if cgst == sgst else cgst + sgst
    }

# Start a background thread to periodically fetch and update government dataset
update_thread = Thread(target=fetch_and_update_government_data)
update_thread.daemon = True
update_thread.start()
