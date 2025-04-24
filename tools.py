from datetime import datetime, timedelta
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MousePosition

def process_orbit_data(num_cycles_calval=178, num_cycles_science=65):
    """
    Processes orbit data for calval and science orbits, generating predicted 
    data for each based on input parameters and shapefiles.

    Args:
        num_cycles_calval (int, optional): Number of calval cycles to process. 
            Defaults to 178.
        num_cycles_science (int, optional): Number of science cycles to process. 
            Defaults to 65.

    Returns:
        pandas.DataFrame: A concatenated DataFrame containing predicted orbit 
        data for both calval and science orbits. The DataFrame includes the 
        following columns:
            - TIME: The predicted time for each orbit.
            - CYCLE: The cycle number for the orbit.
            - ORBIT: The type of orbit ("calval" or "science").
            - PASS: The pass ID (renamed from "ID_PASS").
    """
    # Constants
    delta_calval = timedelta(days=0.99349)
    delta_science = timedelta(days=20.864549)
    dif = round((20.864549 / 584) * 86400, 1)

    # Start dates
    start_date_calval = datetime(2023, 1, 15, 6, 1, 50) + timedelta(hours=3.42)

    # Load and preprocess calval shapefile
    gdf_calval = gpd.read_file("data/external/swot_swath/swot_calval_orbit_june2015-v2_swath.shp")
    gdf_calval["TIME"] = start_date_calval + pd.to_timedelta(gdf_calval["START_TIME"])
    gdf_calval = gdf_calval.drop(columns=["START_TIME"])

    # Generate predicted data for calval
    predicted_calval = []
    for i in range(0, num_cycles_calval):
        gdf_copy = gdf_calval.copy()
        gdf_copy["TIME"] = gdf_copy["TIME"] + i * delta_calval
        gdf_copy["CYCLE"] = i + 401
        predicted_calval.append(gdf_copy)
    predicted_calval = pd.concat(predicted_calval).reset_index(drop=True)
    predicted_calval["ORBIT"] = "calval"

    # Load and preprocess science shapefile
    gdf_science = (
        gpd.read_file("data/external/swot_swath/swot_science_orbit_sept2015-v2_swath.shp")
        .dissolve(by="ID_PASS")
        .reset_index()
    )
    gdf_science["TIME"] = pd.date_range(
        start=calculate_time(gdf_science["START_TIME"].min(), 0),
        freq=f"{dif}s",
        periods=gdf_science.shape[0]
    )
    gdf_science = gdf_science.drop(columns=["START_TIME"])

    # Generate predicted data for science
    predicted_science = []
    for i in range(1, num_cycles_science + 1):
        gdf_copy = gdf_science.copy()
        gdf_copy["TIME"] = gdf_copy["TIME"] + i * delta_science
        gdf_copy["CYCLE"] = i + 1
        predicted_science.append(gdf_copy)
    predicted_science = pd.concat(predicted_science).reset_index(drop=True)
    # convert from datetime64[ns, UTC] to datetime64[ns]
    predicted_science["TIME"] = predicted_science["TIME"].dt.tz_localize(None)
    predicted_science["ORBIT"] = "science"

    # Concatenate calval and science data
    all_data = pd.concat([predicted_calval, predicted_science]).reset_index(drop=True).rename(columns={"ID_PASS": "PASS"})

    return all_data


def calculate_time(start_time, index, reference_timestamp = pd.Timestamp("2023-07-21T05:33:45.768", tz="UTC")):
    """
    Calculates the exact time for each geometry feature based on its START_TIME and index.
    """
    _, day_num, time_str = start_time.split(" ", 2)
    days = int(day_num)
    time_parts = list(map(int, time_str.split(":")))
    delta = timedelta(days=days-1, hours=time_parts[0], minutes=time_parts[1], seconds=time_parts[2] + index * 30)
    
    return delta + reference_timestamp


def create_map(start_date, end_date, orbit_data, opacity=0.2, fill_opacity=0.1, eez=None):
    """
    Creates and returns a map object and the filtered data based on the date range.

    Parameters:
    - start_date (pd.Timestamp): The start date for filtering.
    - end_date (pd.Timestamp): The end date for filtering.
    - orbit_data (pd.DataFrame): The orbit data to filter and map.

    Returns:
    - tuple: (map_object, selected)
        - map_object: The folium map object returned from GeoDataFrame.explore().
        - selected: The filtered GeoDataFrame.
    """

    # Filter for the range provided by the user
    selected = orbit_data[(orbit_data["TIME"] >= start_date) & (orbit_data["TIME"] <= end_date)]

    if len(selected) == 0:
        return None, None  # No data available for the selected date range

    # Calculate the days from the initial date
    init = f"{selected.TIME.min().round('D')}".split()[0]
    selected[f"DAYS from {init}"] = (selected.TIME - selected.TIME.min()).dt.days

    # Format TIME column to show only date and time
    selected["TIME"] = selected["TIME"].dt.strftime("%Y-%m-%d %H:%M")

    selected_days_since = selected.groupby(["PASS", "geometry"], as_index=False)[f"DAYS from {init}"].min()[f"DAYS from {init}"]

    selected = selected.groupby(["PASS", "geometry"], as_index=False).agg(lambda x: ', '.join(map(str, x)))
    selected = gpd.GeoDataFrame(selected, geometry="geometry")

    selected[f"DAYS from {init}"] = selected_days_since

    # Generate and return the map object dynamically
    map_object = selected.explore(
        column=f"DAYS from {init}",  # Color by the calculated days difference
        cmap="Spectral",             # Use a color map
        tooltip=["TIME", f"DAYS from {init}", "PASS", "CYCLE", "ORBIT"],  # Show time and days in tooltips
        zoom_start=3,
        style_kwds=dict(weight=1, opacity=opacity, fillOpacity=fill_opacity),  # Set polygon/line opacity
        control=True,
        name="SWOT Pass",
    )

    if eez is not None:
        # map_object = eez.explore(m=map_object, color="gray", name="EEZ", style_kwds={"weight": 1.5}, tooltip=["LINE_NAME"], control=True)
        # Create the EEZ layer as a Folium GeoJson, not via .explore()
        folium.GeoJson(
            data=eez.to_json(),
            name="EEZ",
            tooltip=folium.GeoJsonTooltip(fields=["LINE_NAME"]),
            style_function=lambda x: {"color": "gray", "weight": 1.5},
            show=False  # 👈 Toggled OFF by default
        ).add_to(map_object)

    folium.LayerControl().add_to(map_object)

    # Show coordinates when hovering
    MousePosition(
        position="bottomright",
        separator=" | ",
        prefix="Lat/Lon:",
        num_digits=3,
    ).add_to(map_object)

    return map_object, selected


if __name__ == "__main__":
    create_map(datetime.now(), datetime.now()+timedelta(days=4))