from datetime import timedelta
import pandas as pd
import geopandas as gpd

def calculate_time(start_time, index):
    """
    Calculates the exact time for each geometry feature based on its START_TIME and index.
    """
    _, day_num, time_str = start_time.split(" ", 2)
    days = int(day_num)
    time_parts = list(map(int, time_str.split(":")))
    delta = timedelta(days=days-1, hours=time_parts[0], minutes=time_parts[1], seconds=time_parts[2] + index * 30)
    reference_timestamp = pd.Timestamp("2023-07-21T05:33:45.768")
    return delta + reference_timestamp