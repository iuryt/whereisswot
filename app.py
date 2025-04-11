import os
import tempfile
from flask import Flask, render_template, request, abort, session, send_file
from markupsafe import Markup  # Correct import for Markup
import geopandas as gpd
import pandas as pd
from datetime import timedelta, datetime, timezone
from io import BytesIO
import uuid
from tools import process_orbit_data, create_map  # Import create_map
import numpy as np
import os

app = Flask(__name__)

app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback_secret_key')

orbit_data = process_orbit_data()
eez = gpd.read_file('data/external/eez/eez_boundaries_v12.shp').drop(columns=["DOC_DATE"])

@app.route("/", methods=["GET", "POST"])
def index():
    map_url = None  # Initialize map_url to None
    start_date_str = None
    num_days_str = "5"  # Default number of days to 5
    
    if request.method == "POST":
        # Get the start date and number of days from the form
        start_date_str = request.form.get("start_date")
        num_days_str = request.form.get("num_days", "5")  # Default number of days to 5

        # Convert the string start date to datetime (default to current date if not provided)
        if not start_date_str:
            start_date = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))
        else:
            try:
                start_date = pd.to_datetime(start_date_str)
            except ValueError:
                return render_template("index.html", map_url=None, message="Invalid date format", start_date=start_date_str, num_days=num_days_str)  # Return error page

        # Convert the number of days to integer (default to 5, max 10)
        try:
            num_days = int(num_days_str)
            if num_days > 100:
                return render_template("index.html", map_url=None, message="Number of days must not exceed 100.", start_date=start_date_str, num_days=num_days_str)
        except ValueError:
            return render_template("index.html", map_url=None, message="Invalid number of days format", start_date=start_date_str, num_days=num_days_str)

        # Calculate the end date based on the number of days
        end_date = start_date + timedelta(days=num_days)

        if num_days<=4:
            opacity = 0.5
            fill_opacity = 0.3
        else:
            opacity = 0.2
            fill_opacity = 0.1

        # Use the create_map function to generate the map and get the filtered data
        map_object, selected = create_map(start_date, end_date, orbit_data, opacity=opacity, fill_opacity=fill_opacity, eez=eez)

        if selected is None or selected.empty:
            return render_template("index.html", map_url=None, message="No data available for the selected date range.", start_date=start_date_str, num_days=num_days_str)

        # Save the map to a temporary file and store the file path in the session
        temp_dir = tempfile.gettempdir()
        temp_filename = os.path.join(temp_dir, f"map_{uuid.uuid4()}.html")
        map_object.save(temp_filename)
        session['map_file'] = temp_filename

        # Return a URL to another route where the map will be served
        return render_template("index.html", map_url="/show_map", message=None, start_date=start_date_str, num_days=num_days_str)

    # Always return the form page for GET requests or if no data is submitted
    return render_template("index.html", map_url=None, message=None, start_date=start_date_str, num_days=num_days_str)


@app.route("/show_map")
def show_map():
    # Retrieve temp file path from session
    temp_filename = session.get('map_file', None)

    if not temp_filename or not os.path.exists(temp_filename):
        return "No map data available."

    # Read and return the map HTML
    with open(temp_filename, 'r') as f:
        map_html = f.read()

    # Securely delete the temp file
    try:
        os.remove(temp_filename)
    except Exception as e:
        print(f"Error deleting file: {e}")

    return map_html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4242)
