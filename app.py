import os
from flask import Flask, render_template, request
import geopandas as gpd
import pandas as pd
from datetime import timedelta, datetime
from tools import process_orbit_data, create_map

app = Flask(__name__)

orbit_data = process_orbit_data()
eez = gpd.read_file('data/external/eez/eez_boundaries_v12.shp').drop(columns=["DOC_DATE"])

@app.route("/", methods=["GET", "POST"])
def index():
    map_html = None
    start_date_str = None
    num_days_str = "5"

    if request.method == "POST":
        start_date_str = request.form.get("start_date")
        num_days_str = request.form.get("num_days", "5")

        if not start_date_str:
            start_date = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))
        else:
            try:
                start_date = pd.to_datetime(start_date_str)
            except ValueError:
                return render_template("index.html", map_html=None, message="Invalid date format", start_date=start_date_str, num_days=num_days_str)

        try:
            num_days = int(num_days_str)
            if num_days > 100:
                return render_template("index.html", map_html=None, message="Number of days must not exceed 100.", start_date=start_date_str, num_days=num_days_str)
        except ValueError:
            return render_template("index.html", map_html=None, message="Invalid number of days format", start_date=start_date_str, num_days=num_days_str)

        end_date = start_date + timedelta(days=num_days)

        if num_days<=4:
            opacity = 0.5
            fill_opacity = 0.3
        else:
            opacity = 0.2
            fill_opacity = 0.1

        map_object, selected = create_map(start_date, end_date, orbit_data, opacity=opacity, fill_opacity=fill_opacity, eez=eez)

        if selected is None or selected.empty:
            return render_template("index.html", map_html=None, message="No data available for the selected date range.", start_date=start_date_str, num_days=num_days_str)

        map_html = map_object._repr_html_()

        return render_template("index.html", map_html=map_html, message=None, start_date=start_date_str, num_days=num_days_str)

    return render_template("index.html", map_html=None, message=None, start_date=start_date_str, num_days=num_days_str)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4242)
