import logging
import asyncio
from services.satellite_tracker import SatelliteTracker
from fastapi import FastAPI

logger = logging.getLogger("groundstation")


tracker = None
# Initialize tracker once and share it
async def create_tracker():
    global tracker
    tracker = SatelliteTracker(logger)
    await tracker._async_init()

def get_tracker():
    global tracker
    """Dependency to inject the tracker instance."""
    return tracker