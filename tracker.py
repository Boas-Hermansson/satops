from dataclasses import dataclass
from skyfield.api import load  # For loading the timescale and satellites
from skyfield.iokit import parse_tle_file  # For parsing TLE data
from skyfield.api import EarthSatellite  # For defining the satellite
from skyfield.api import wgs84  # For defining the location of the observer - World Geodetic System 1984
from datetime import datetime, timezone
import sys
from time import sleep


@dataclass
class Pass:
    # Times are in UTC
    rise: datetime
    culminate: datetime
    set: datetime

def load_sats(tle_file, ts, sat_name) -> list[EarthSatellite]:
    """
    Load the satellites from the TLE file
    """
    max_days = 1.0
    sat_name_pure = sat_name.replace(" ", "%20")
    url = f'https://celestrak.org/NORAD/elements/gp.php?NAME={sat_name_pure}&FORMAT=TLE'

    if not load.exists(tle_file) or load.days_old(tle_file) >= max_days:
        load.download(url, filename=tle_file)
    else:  # Download the file if the satellite name is not in the file
        with open(tle_file, 'r') as f:
            lines = f.readlines()
            if len(lines) > 0 and satellite_name.upper() not in lines[0].upper():
                load.download(url, filename=tle_file)

    with load.open(tle_file) as f:
        satellites = list(parse_tle_file(f, ts))

    print(f"Loaded {len(satellites)} satellite(s)")

    return satellites

def get_passes(sat: EarthSatellite, location, start: datetime, end: datetime, ts, deg: float=5.0) -> list[Pass]:
    """
    Get the passes for the satellite in a given time frame
    Args:
        sat: EarthSatellite object
        location: wgs84.latlon object
        start: Time object
        end: Time object
    Returns:
        list of passes. A pass has a rise, culminate and set time
    """
    acc = []
    t, events = sat.find_events(location, ts.from_datetime(start), ts.from_datetime(end), altitude_degrees=deg)
    
    for i in range(0, len(events), 3):
        if events[i] == 0 and events[i+1] == 1 and events[i+2] == 2:
            acc.append(Pass(rise=t[i].utc_datetime(), culminate=t[i+1].utc_datetime(), set=t[i+2].utc_datetime()))
    return acc

def get_next_pass(sat: EarthSatellite, location, ts, deg: float=5.0) -> Pass:
    """
    Get the next pass for the satellite
    Args:
        sat: EarthSatellite object
        location: wgs84.latlon object
    Returns:
        Pass object
    """
    start = ts.now()
    t, events = sat.find_events(location, start, start + 1, altitude_degrees=deg)
    while not (events[0] == 0 and events[1] == 1 and events[2] == 2):
        start = t[2] + 1
        t, events = sat.find_events(location, start, start + 1, altitude_degrees=deg)
    return Pass(rise=t[0].utc_datetime(), culminate=t[1].utc_datetime(), set=t[2].utc_datetime())
    

def track(sat: EarthSatellite, sat_pass: Pass, location, ts) -> None:
    """
    Track the satellite during a pass
    Args:
        sat_pass: Pass object
        location: wgs84.latlon object
    """
    # Sleep till the rise time
    time_till_rise = (sat_pass.rise - datetime.now(timezone.utc)).total_seconds()
    print(f"sleeping until {sat_pass.rise.replace(tzinfo=timezone.utc).astimezone(tz=None).strftime('%Y %b %d %H:%M:%S')}")

    sleep(time_till_rise)

    # Track the satellite during the pass
    difference = sat - location
    topocentric = difference.at(ts.now())
    alt, az, distance = topocentric.altaz()

    while (datetime.now(timezone.utc) - sat_pass.set).seconds < 0 or alt.degrees > 0:
        print(f"Azimuth: {az.degrees:.2f} degrees")
        print(f"Altitude: {alt.degrees:.2f} degrees")
        sleep(3)
        difference = sat - location
        topocentric = difference.at(ts.now())
        alt, az, distance = topocentric.altaz()

    return

if __name__ == "__main__":
    """
    Args:
        satellite_name argv[1]: Name of the satellite
    """
    if len(sys.argv) < 2:
        print("Usage: python tracker.py <satellite_name>")
        sys.exit(1)
    
    # Initialize variables 
    satellite_name = sys.argv[1]
    tle_file = 'disco.tle'
    ts = load.timescale()
    
    # Determine location
    try:
        with open("location.txt", "r") as file:
            lines = file.readlines()
            latitude = float(lines[0].strip())
            longitude = float(lines[1].strip())
    except (FileNotFoundError, IndexError, ValueError):
        latitude = 56.162937
        longitude = 10.203921
    
    location = wgs84.latlon(latitude, longitude)

    # Load satellites
    satellites = load_sats(tle_file, ts, satellite_name)
    # Assuming we only load one satellite (WHICH WE DO!)
    satellite = satellites[0]

    today = datetime.now(timezone.utc)
    tomorrow = datetime.now(timezone.utc).replace(day=today.day+1)
    passes = get_passes(satellite, location, today, tomorrow, ts, 5)
    next_pass = get_next_pass(satellite, location, ts)
    
    track(satellite, next_pass, location, ts)
    