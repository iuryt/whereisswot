import os
import tempfile
from flask import Flask, render_template, request, abort, session, send_file
from markupsafe import Markup  # Correct import for Markup
import geopandas as gpd
import pandas as pd
from datetime import timedelta, datetime
from io import BytesIO
import uuid
from tools import calculate_time

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for session management

# Load your shapefile data once during app startup
gdf = gpd.read_file("data/external/swot_swath/swot_science_orbit_sept2015-v2_swath.shp")

# Apply the initial time calculation to the GeoDataFrame
gdf['TIME'] = gdf.apply(lambda row: calculate_time(row['START_TIME'], row.name), axis=1)

# Time delta for iterations
delta = timedelta(days=20.864549)

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
            if num_days > 10:
                return render_template("index.html", map_url=None, message="Number of days must not exceed 10.", start_date=start_date_str, num_days=num_days_str)
        except ValueError:
            return render_template("index.html", map_url=None, message="Invalid number of days format", start_date=start_date_str, num_days=num_days_str)

        # Calculate the end date based on the number of days
        end_date = start_date + timedelta(days=num_days)

        # Filter based on the provided date range
        selected = []
        for i in range(1, 300):
            gdf_copy = gdf.copy()
            gdf_copy["TIME"] = gdf_copy["TIME"] + i * delta

            # Filter for the range provided by the user
            within_range = gdf_copy[(gdf_copy["TIME"] >= start_date) & (gdf_copy["TIME"] <= end_date)]
            
            if within_range.size > 0:
                selected.append(within_range)

        if len(selected) == 0:
            return render_template("index.html", map_url=None, message="No data available for the selected date range.", start_date=start_date_str, num_days=num_days_str)

        # Concatenate the selected data
        selected = pd.concat(selected).reset_index(drop=True)

        # Ensure geometries are valid
        selected = selected[selected.is_valid]

        # Calculate the days from the initial date
        init = f"{selected.TIME.min().round('D')}".split()[0]
        selected[f"DAYS from {init}"] = (selected.TIME - selected.TIME.min()).dt.days

        # Convert TIME column to string for display purposes
        selected["TIME"] = selected["TIME"].astype(str)

        # Save the GeoDataFrame to a temporary file and store the file path in the session
        temp_dir = tempfile.gettempdir()
        temp_filename = os.path.join(temp_dir, f"map_{uuid.uuid4()}.geojson")
        selected.to_file(temp_filename, driver="GeoJSON")

        # Store the temp file name in the session
        session['map_file'] = temp_filename
        session['init'] = init

        # Return a URL to another route where the map will be served
        return render_template("index.html", map_url="/show_map", message=None, start_date=start_date_str, num_days=num_days_str)

    # Always return the form page for GET requests or if no data is submitted
    return render_template("index.html", map_url=None, message=None, start_date=start_date_str, num_days=num_days_str)


@app.route("/show_map")
def show_map():
    # Retrieve temp file path and init from session
    temp_filename = session.get('map_file', None)
    init = session.get('init', None)

    if not temp_filename or not init or not os.path.exists(temp_filename):
        return "No map data available."

    # Load the GeoDataFrame from the file
    selected = gpd.read_file(temp_filename)

    selected["TIME"] = selected["TIME"].astype(str)
    
    # Generate the map dynamically
    map_html_io = BytesIO()
    selected.explore(
        column=f"DAYS from {init}",  # Color by the calculated days difference
        cmap="Spectral",             # Use a color map
        tooltip=["TIME", f"DAYS from {init}"],  # Show time and days in tooltips
        zoom_start=3,
        style_kwds=dict(weight=1, opacity=0.8, fillOpacity=0.3)  # Set polygon/line opacity
    ).save(map_html_io, close_file=False)
    
    # Decode the map HTML and return it
    map_html = map_html_io.getvalue().decode("utf-8")
    return map_html

if __name__ == "__main__":
    app.run(debug=True, port=4242)
