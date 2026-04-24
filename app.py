import os
import time
import uuid
from flask import Flask, abort, render_template, request, send_file, url_for
import geopandas as gpd
import pandas as pd
from datetime import timedelta, datetime
from tools import process_orbit_data, create_map

app = Flask(__name__)
MAP_CACHE_DIR = "/tmp/whereisswot-maps"
MAP_MAX_AGE_SECONDS = 3600
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID")

orbit_data = process_orbit_data()
eez = gpd.read_file('data/external/eez/eez_boundaries_v12.shp').drop(columns=["DOC_DATE"])


def cleanup_old_maps():
    """Best-effort cleanup for stale generated map files."""
    os.makedirs(MAP_CACHE_DIR, exist_ok=True)
    now = time.time()
    for filename in os.listdir(MAP_CACHE_DIR):
        if not filename.endswith(".html"):
            continue
        path = os.path.join(MAP_CACHE_DIR, filename)
        try:
            if now - os.path.getmtime(path) > MAP_MAX_AGE_SECONDS:
                os.remove(path)
        except FileNotFoundError:
            continue


def store_map_html(map_html):
    os.makedirs(MAP_CACHE_DIR, exist_ok=True)
    cleanup_old_maps()
    if GA_MEASUREMENT_ID:
        analytics_snippet = f"""
<script>
  (function () {{
    const gaId = {GA_MEASUREMENT_ID!r};
    if (!gaId || localStorage.getItem('analytics_consent') !== 'accepted' || window.gaLoaded) {{
      return;
    }}

    window.gaLoaded = true;
    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + gaId;
    document.head.appendChild(script);

    window.dataLayer = window.dataLayer || [];
    function gtag() {{ dataLayer.push(arguments); }}
    window.gtag = gtag;
    gtag('js', new Date());
    gtag('config', gaId, {{ 'page_title': 'SWOT Satellite Passings Map' }});
  }})();
</script>
</body>
"""
        map_html = map_html.replace("</body>", analytics_snippet)

    map_id = f"{uuid.uuid4().hex}.html"
    map_path = os.path.join(MAP_CACHE_DIR, map_id)
    with open(map_path, "w", encoding="utf-8") as f:
        f.write(map_html)
    return map_id

@app.route("/", methods=["GET", "POST"])
def index():
    map_url = None
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
                return render_template("index.html", map_url=None, message="Invalid date format", start_date=start_date_str, num_days=num_days_str, ga_measurement_id=GA_MEASUREMENT_ID)

        try:
            num_days = int(num_days_str)
            if num_days > 100:
                return render_template("index.html", map_url=None, message="Number of days must not exceed 100.", start_date=start_date_str, num_days=num_days_str, ga_measurement_id=GA_MEASUREMENT_ID)
        except ValueError:
            return render_template("index.html", map_url=None, message="Invalid number of days format", start_date=start_date_str, num_days=num_days_str, ga_measurement_id=GA_MEASUREMENT_ID)

        end_date = start_date + timedelta(days=num_days)

        if num_days<=4:
            opacity = 0.5
            fill_opacity = 0.3
        else:
            opacity = 0.2
            fill_opacity = 0.1

        map_object, selected = create_map(start_date, end_date, orbit_data, opacity=opacity, fill_opacity=fill_opacity, eez=eez)

        if selected is None or selected.empty:
            return render_template("index.html", map_url=None, message="No data available for the selected date range.", start_date=start_date_str, num_days=num_days_str, ga_measurement_id=GA_MEASUREMENT_ID)

        map_id = store_map_html(map_object.get_root().render())
        map_url = url_for("show_map", map_id=map_id)

        return render_template("index.html", map_url=map_url, message=None, start_date=start_date_str, num_days=num_days_str, ga_measurement_id=GA_MEASUREMENT_ID)

    return render_template("index.html", map_url=None, message=None, start_date=start_date_str, num_days=num_days_str, ga_measurement_id=GA_MEASUREMENT_ID)


@app.route("/show_map/<path:map_id>")
def show_map(map_id):
    cleanup_old_maps()
    map_path = os.path.abspath(os.path.join(MAP_CACHE_DIR, map_id))
    cache_dir = os.path.abspath(MAP_CACHE_DIR)

    if not map_path.startswith(f"{cache_dir}{os.sep}") or not os.path.exists(map_path):
        abort(404)

    return send_file(map_path, mimetype="text/html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=4242)
