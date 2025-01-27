from skyfield.api import N, W, load, wgs84
from skyfield.iokit import parse_tle_file
from sgp4.api import Satrec
from skyfield.positionlib import ICRF
from datetime import timedelta, datetime, timezone
from time import sleep



location = wgs84.latlon(56.171836003400216 * N, 10.1884953301856 * W, 20)
location = wgs84.latlon(62.010570 * N, 6.798298 * W, 128)
ts = load.timescale() 




max_days = 7.0
tle_file = 'disco.tle'

# url = 'https://celestrak.org/NORAD/elements/gp.php?NAME=disco&FORMAT=tle'
url = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=CUBESAT'


load.download(url, filename=tle_file)

if load.days_old(tle_file) >= max_days:
    load.download(url, filename=tle_file)



def filter_pass(times, event_types):
        # passes should rise -> culminate -> set
        for i in range(0, len(times)):
            if event_types[i] != i:
                return False

        # valid passes rise above 20 degrees
        good = False
        for time in times: 
            difference = satellite.at(time) - location.at(time)
            alt, az, h = difference.altaz()
            alt = alt.degrees
            if alt > 20:
                good = True        

        return good



def get_next_pass(satellite):
    t = []
    start = ts.now()
    t1 = start
    while True:
        while len(t) < 3:
            t1 = t1 + timedelta(minutes = 2)
            t, events = satellite.find_events(location, start, t1, altitude_degrees = -5) 

        if filter_pass(t, events):
            return t[0], t[2]
        
        # if this was a bad pass skip the first event and try again
        start = t[0] + timedelta(seconds = 20)
        t = t[1:]
        events = events[1:]

    return t[0], t[2]

          

def predict_pass(satellite, day, month, year):
    start = ts.tt(year, month, day, 0, 0)
    t1 = start + timedelta(days = 1)
    t, events = satellite.find_events(location, start, t1, altitude_degrees = -5) 
    
    good_passes = []

    for i in range(0, len(t) - 2): 
        current_times = t[i:i+3]
        current_events= events[i:i+3]
        if filter_pass(current_times, current_events):
            good_passes.append([current_times[0], current_times[2]])
    

    return good_passes

    
    

def track(satellite): 
    t_start, t_end = get_next_pass(satellite)
    now = ts.now()
     
    time_until_pass = (t_start.utc_datetime() - now.utc_datetime()).total_seconds()

    print(f"sleeping until {t_start.utc_strftime('%Y %b %d %H:%M:%S')}")
    sleep(int(time_until_pass))

    now = ts.now()
    difference = satellite.at(now) - location.at(now)
    alt, az, h = difference.altaz()
    az = az.degrees
    alt = alt.degrees

    while (now - t_end) < 0 or alt > 0:
         
        print("azimuth:", az)
        print("altitude:", alt)
        
        sleep(3)

        difference = satellite.at(now) - location.at(now)
        alt, az, h = difference.altaz()
        az = az.degrees
        alt = alt.degrees

        now = ts.now()

    #call to some rotor controller
    # subprocess.run(["rotctl", "P", az, alt])

    

if __name__ == "__main__":

        satellite = load.tle(tle_file)["DISCO-1"]
        
        # predict_pass(satellite)

        # track(satellite)
        
        passes = predict_pass(satellite, 17, 1, 2025)
        print(passes)