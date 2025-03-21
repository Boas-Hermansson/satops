# TODO: Make sure TLE data is updated in satellite tracker
from satellite_tracker import SatelliteTracker

from fastapi import FastAPI, HTTPException
import logging
import os
import uvicorn
from datetime import datetime, timezone, timedelta
from skyfield.api import load, wgs84
import subprocess

from api_logging_config import LOGGING_CONFIG

#GS_LOGS = 'logs/groundstation.log'
logging.config.dictConfig(LOGGING_CONFIG)
#formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt="%Y-%m-%d %H:%M:%S")

# Configure general logger
logger = logging.getLogger("groundstation")
#hdlr = logging.FileHandler(GS_LOGS)
#hdlr.setFormatter(formatter)
#logger.setLevel(logging.INFO)
#logger.addHandler(hdlr)

app = FastAPI()

# Initialize the tracker with default satellite (ISS)
tracker = SatelliteTracker(logger)

# API endpoints
@app.get('/satellite')
async def get_satellite_info():
    """Get information about the tracked satellite"""
    return {
        "name": tracker.satellite_name,
        "tracking": tracker.is_tracking,
        "status": tracker.tracking_data["status"]
    }

@app.get('/satellite/position')
async def get_satellite_position():
    """Get current position of the satellite"""
    position = tracker.get_sat_position()
    if position:
        return position
    raise HTTPException(status_code=404, detail="Satellite position not available")

@app.get('/satellite/passes')
async def get_satellite_passes(
    days: int = 1,
    min_elevation: float = 10.0
):
    """Get passes for the satellite in a given time frame"""
    if days < 1:
        raise HTTPException(status_code=400, detail="Days must be greater than 0")
    if min_elevation < 5:
        raise HTTPException(status_code=400, detail="Minimum elevation must be greater than 5")    
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=days)

    passes = tracker.get_passes(start_time, end_time, min_elevation=min_elevation)
    return [p.to_dict() for p in passes]

@app.get('/satellite/next-pass')
async def get_next_pass(
    min_elevation: float = 10.0    
):
    """Get the next pass for the satellite""" 
    if min_elevation < 5:
        raise HTTPException(status_code=400, detail="Minimum elevation must be greater than 5")   
    next_pass = tracker.get_next_pass(min_elevation=min_elevation)
    if next_pass is None:
        raise HTTPException(status_code=404, detail="No upcoming passes found")

    return next_pass.to_dict()

@app.post('/satellite/reload_tle')
async def reload_sat_tle():
    """Reload the starfield satellite object with fresh tle data."""
    success = tracker.reload_satellite()
    return {"success": success}

@app.post('/satellite/track/start')
async def start_satellite_tracking():
    """Start tracking the satellite"""
    success = tracker.start_tracking()
    return {"success": success}

@app.post('/satellite/track/stop')
async def stop_satellite_tracking():
    """Stop tracking the satellite"""
    success = tracker.stop_tracking()
    return {"success": success}

@app.get('/satellite/track/data')
async def get_tracking_data():
    """Get the latest tracking data"""
    data = tracker.get_tracking_data()
    return data

@app.get('/system/location')
async def get_location():
    """Get the current observer location"""
    location = tracker.location
    return {
        "latitude": location.latitude.degrees,
        "longitude": location.longitude.degrees
    }

@app.post('/system/location')
async def set_location(
    latitude: float,
    longitude: float
):
    """Set the observer location"""
    try:
        # Update the location file
        with open("location.txt", "w") as f:
            f.write(f"{latitude}\n{longitude}\n")
        # Update the tracker's location
        tracker.location = wgs84.latlon(latitude, longitude)
        
        return {
            "success": True,
            "latitude": latitude,
            "longitude": longitude
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.get('') #Get system logs

@app.get('/system/status')
async def system_status():
    """Get the system status"""
    return {
        "running": True,
        "satellite": tracker.satellite_name,
        "tracking": tracker.is_tracking,
        "status": tracker.tracking_data["status"],
        "last_updated": tracker.tracking_data["last_updated"]
    }

@app.get('/rotor/status')
async def rotor_status():
    """Get the rotor status from rotctl"""
    try:
        output = subprocess.check_output(["rotctl", "p"]).splitlines()
        azimuth = output[0].decode()
        elevation = output[1].decode()
        return {
            "azimuth": azimuth,
            "elevation": elevation
        }
    except Exception as e:
        return {
            "error": str(e)
        }
    
@app.post('/rotor/control')
async def rotor_control(
    azimuth: int,
    elevation: int
):
    """Manually point the rotor to a specific direction"""
    if azimuth > 180 or azimuth < -180:
        raise HTTPException(status_code=400, detail="Azimuth must be between 180 and -180")

    if elevation < 1 or elevation > 90:
        raise HTTPException(status_code=400, detail="Elevation must be between 0 and 90")
    
    try:
        subprocess.check_call(["rotctl", "P", str(azimuth), str(elevation)])
        return {"success": True}
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    

if __name__ == "__main__":
    # Automatically create the logs folder if not there
    os.makedirs("logs", exist_ok=True)
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)