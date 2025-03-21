import logging
from services.satellite_tracker import SatelliteTracker

logger = logging.getLogger("groundstation")

# Initialize tracker once and share it
tracker = SatelliteTracker(logger)

def get_tracker():
    """Dependency to inject the tracker instance."""
    return tracker