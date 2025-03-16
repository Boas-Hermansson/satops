# TODO: Make sure TLE data is updated in satellite tracker

from dataclasses import dataclass
from flask import Flask, jsonify, request
import threading
import logging
import os
from datetime import datetime, timezone, timedelta
from skyfield.api import load, EarthSatellite, wgs84
from skyfield.iokit import parse_tle_file


from fastapi import FastAPI, HTTPException, Query
from typing import Annotated
from pydantic import BaseModel
import uvicorn
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI()

class Pass(BaseModel):
    # Times are in UTC
    rise: datetime
    culminate: datetime
    set: datetime
    
    def to_dict(self):
        """Convert Pass object to dictionary for JSON serialization"""
        return {
            "rise": self.rise.isoformat(),
            "culminate": self.culminate.isoformat(),
            "set": self.set.isoformat()
        }

class SatelliteTracker:
    def __init__(self, satellite_name=None):
        self.tle_file = "disco.tle"
        self.ts = load.timescale()
        
        if not satellite_name:
            try:
                with open(self.tle_file, 'r') as f:
                    satellite_name = f.readline().strip()
            except FileNotFoundError:
                logger.error("TLE file not found, aborting initialization")

        self.satellite_name = satellite_name
        self.satellite = None
        self.is_tracking = False
        self.tracking_thread = None
        
        # Default location (can be overridden)
        self.location = self._load_gs_location()
        
        # TLE file location
        
        # Tracking data
        self.tracking_data = {
            "azimuth": 0,
            "elevation": 0,
            "distance": 0,
            "last_updated": None,
            "status": "idle",  # idle, waiting, tracking, or completed
            "current_pass": None
        }
        
        # Load the satellite
        self.load_satellite()
    
    def _load_gs_location(self):
        """Load location from file or use default"""
        try:
            with open("location.txt", "r") as file:
                lines = file.readlines()
                latitude = float(lines[0].strip())
                longitude = float(lines[1].strip())
                logger.info(f"Loaded location: {latitude}, {longitude}")
        except (FileNotFoundError, IndexError, ValueError):
            # Default location (Aarhus)
            latitude = 56.162937
            longitude = 10.203921
            logger.info(f"Using default location: {latitude}, {longitude}")
        
        return wgs84.latlon(latitude, longitude)
    
    def load_satellite(self) -> bool:
        """Load the satellite from its TLE file"""        
        # Check if file exists
        if not os.path.exists(self.tle_file):
            logger.error(f"TLE file not found for {self.satellite_name}")
            return False
        
        try:
            with load.open(self.tle_file) as f:
                satellites = list(parse_tle_file(f, self.ts))
            
            if not satellites:
                logger.error(f"No satellites found in TLE file for {self.satellite_name}")
                return False
            
            self.satellite = satellites[0]
            self.satellite_name = self.satellite.name
            logger.info(f"Loaded satellite: {self.satellite_name}")
            return True
        except Exception as e:
            logger.error(f"Error loading satellite {self.satellite_name}: {str(e)}")
            return False
    
    def get_sat_position(self) -> dict:
        """Get current latitude and longitude of the satellite"""
        if not self.satellite:
            return None
        
        # Get current position
        t = self.ts.now()
        geocentric = self.satellite.at(t)
        
        subpoint = geocentric.subpoint()
        
        return {
            "satellite": self.satellite_name,
            "latitude": subpoint.latitude.degrees,
            "longitude": subpoint.longitude.degrees,
            "elevation": subpoint.elevation.m,
            "timestamp": t.utc_datetime().isoformat()
        }
    
    def get_passes(self, start_time=None, end_time=None, min_elevation=5.0) -> list[Pass]:
        """Get passes for the satellite in a given time frame"""
        if not self.satellite:
            return []
        
        if start_time is None:
            start_time = datetime.now(timezone.utc)
        
        if end_time is None:
            end_time = start_time + timedelta(days=1)
        
        return self._get_passes(start_time, end_time, min_elevation)
    
    def _get_passes(self, start: datetime, end: datetime, deg: float=5.0) -> list[Pass]:
        """
        Get the passes for the satellite in a given time frame
        Args:
            start: datetime object (UTC)
            end: datetime object (UTC)
            deg: minimum elevation in degrees
        Returns:
            list of passes
        """
        acc = []
        t, events = self.satellite.find_events(self.location, self.ts.from_datetime(start), 
                                   self.ts.from_datetime(end), altitude_degrees=deg)
        
        for i in range(0, len(events), 3):
            if i+2 < len(events) and events[i] == 0 and events[i+1] == 1 and events[i+2] == 2:
                acc.append(Pass(rise=t[i].utc_datetime(), 
                               culminate=t[i+1].utc_datetime(),
                               set=t[i+2].utc_datetime()))
        return acc
    
    def get_next_pass(self, min_elevation: float=5.0) -> Pass:
        """Get the next pass for the satellite"""
        if not self.satellite:
            return None
        
        return self._get_next_pass(min_elevation)
    
    def _get_next_pass(self, deg: float=10.0) -> Pass:
        """
        Get the next pass for the satellite
        Args:
            deg: minimum elevation in degrees
        Returns:
            Pass object
        """
        start = self.ts.now()
        t, events = self.satellite.find_events(self.location, start, start + 1, altitude_degrees=deg)
        
        # If no events or incomplete pass, search further
        attempts = 0
        max_attempts = 10  # Limit search to prevent infinite loop
        
        while attempts < max_attempts:
            if len(events) >= 3 and events[0] == 0 and events[1] == 1 and events[2] == 2:
                return Pass(rise=t[0].utc_datetime(), 
                           culminate=t[1].utc_datetime(),
                           set=t[2].utc_datetime())
            
            # Search further ahead
            if len(events) > 0:
                start = t[-1] + 0.1  # Add a little time to avoid same events
            else:
                start = start + 1  # Add a day if no events found
                
            t, events = self.satellite.find_events(self.location, start, start + 1, altitude_degrees=deg)
            attempts += 1
        
        logger.warning(f"Could not find next pass after {max_attempts} attempts")
        return None
        
     
    def start_tracking(self):
        """Start tracking the satellite"""
        if self.is_tracking:
            return False
        
        if not self.satellite:
            if not self.load_satellite():
                return False
        
        # Find the next pass
        next_pass = self._get_next_pass()
        if not next_pass:
            logger.error(f"No upcoming passes found for {self.satellite_name}")
            return False
        
        # Update tracking data
        self.tracking_data["status"] = "waiting"
        self.tracking_data["current_pass"] = next_pass
        
        # Start tracking thread
        self.tracking_thread = threading.Thread(
            target=self._track_satellite,
            args=(next_pass,)
        )
        self.tracking_thread.daemon = True
        self.tracking_thread.start()
        
        self.is_tracking = True
        logger.info(f"Started tracking {self.satellite_name}, next pass at {next_pass.rise}")
        return True
    
    def _track_satellite(self, sat_pass):
        """Track the satellite during a pass"""
        # Sleep till the rise time
        now = datetime.now(timezone.utc)
        time_till_rise = (sat_pass.rise - now).total_seconds()
        
        if time_till_rise > 0:
            logger.info(f"Waiting until rise time for {self.satellite_name}: {sat_pass.rise}")
            self.tracking_data["status"] = "waiting"
            # Sleep until rise time
            threading.Event().wait(time_till_rise)
        
        # Update status
        self.tracking_data["status"] = "tracking"
        
        # Track the satellite during the pass
        while self.is_tracking:
            now = datetime.now(timezone.utc)
            
            # Check if the pass is over
            if now > sat_pass.set:
                logger.info(f"Pass completed for {self.satellite_name}")
                break
            
            # Calculate position
            difference = self.satellite - self.location
            topocentric = difference.at(self.ts.now())
            alt, az, distance = topocentric.altaz()
            
            # Send azimuth, elevation to rotctl
            subprocess.run(["rotctl", "P", az, alt])
            
            # Update tracking data
            self.tracking_data.update({
                "azimuth": az.degrees,
                "elevation": alt.degrees,
                "distance": distance.km,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            })
            
            # If below horizon, stop tracking
            if alt.degrees < 0:
                logger.info(f"Satellite {self.satellite_name} below horizon, stopping tracking")
                break
                
            # Sleep for a short time before updating
            threading.Event().wait(1)
        
        # Update status
        self.tracking_data["status"] = "completed"
        self.is_tracking = False
    
    def stop_tracking(self):
        """Stop tracking the satellite"""
        if not self.is_tracking:
            return False
        
        self.is_tracking = False
        self.tracking_data["status"] = "idle"
        logger.info(f"Stopped tracking satellite {self.satellite_name}")
        return True
    
    def get_tracking_data(self):
        """Get the latest tracking data"""
        return {
            "satellite": self.satellite_name,
            "azimuth": self.tracking_data["azimuth"],
            "elevation": self.tracking_data["elevation"],
            "distance": self.tracking_data["distance"],
            "status": self.tracking_data["status"],
            "last_updated": self.tracking_data["last_updated"],
            "pass": self.tracking_data["current_pass"].to_dict() if self.tracking_data["current_pass"] else None
        }
    
    def set_satellite(self, satellite_name):
        """Change the tracked satellite"""
        if self.is_tracking:
            self.stop_tracking()
            
        self.satellite_name = satellite_name
        return self.load_satellite()


# Initialize the tracker with default satellite (ISS)
tracker = SatelliteTracker()

# API endpoints
@app.get('/satellite')
def get_satellite_info():
    """Get information about the tracked satellite"""
    return {
        "name": tracker.satellite_name,
        "tracking": tracker.is_tracking,
        "status": tracker.tracking_data["status"]
    }

@app.get('/satellite/position')
def get_satellite_position():
    """Get current position of the satellite"""
    position = tracker.get_sat_position()
    if position:
        return position
    raise HTTPException(status_code=404, detail="Satellite position not available")

@app.get('/satellite/passes')
def get_satellite_passes(
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
def get_next_pass(
    min_elevation: float = 10.0    
):
    """Get the next pass for the satellite""" 
    if min_elevation < 5:
        raise HTTPException(status_code=400, detail="Minimum elevation must be greater than 5")   
    next_pass = tracker.get_next_pass(min_elevation=min_elevation)
    if next_pass is None:
        raise HTTPException(status_code=404, detail="No upcoming passes found")

    return next_pass.to_dict()

@app.post('/satellite/track/start')
def start_satellite_tracking():
    """Start tracking the satellite"""
    success = tracker.start_tracking()
    return {"success": success}

@app.post('/satellite/track/stop')
def stop_satellite_tracking():
    """Stop tracking the satellite"""
    success = tracker.stop_tracking()
    return {"success": success}

@app.get('/satellite/track/data')
def get_tracking_data():
    """Get the latest tracking data"""
    data = tracker.get_tracking_data()
    return data

@app.get('/system/location')
def get_location():
    """Get the current observer location"""
    location = tracker.location
    return {
        "latitude": location.latitude.degrees,
        "longitude": location.longitude.degrees
    }

@app.post('/system/location')
def set_location(
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

@app.get('/system/status')
def system_status():
    """Get the system status"""
    return {
        "running": True,
        "satellite": tracker.satellite_name,
        "tracking": tracker.is_tracking,
        "status": tracker.tracking_data["status"],
        "last_updated": tracker.tracking_data["last_updated"]
    }

@app.get('/rotor/status')
def rotor_status():
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
def rotor_control(
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
    uvicorn.run("server:app", host="0.0.0.0", port=5000, reload=True)