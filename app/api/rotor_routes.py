import subprocess
from fastapi import Depends, APIRouter, HTTPException
from api.dependencies import get_tracker

rotor_router = APIRouter()




@rotor_router.get('/status')
async def rotor_status(tracker = Depends(get_tracker)):
    """Get the rotor status from rotctl"""
    azimuth, elevation = await tracker.rotor.read()
    try:
        return {
            "azimuth": azimuth,
            "elevation": elevation
        }
    except Exception as e:
        return {
            "error": str(e)
        }
    
@rotor_router.post('/control')
async def rotor_control(
    azimuth: int,
    elevation: int,
    tracker = Depends(get_tracker)
):
    """Manually point the rotor to a specific direction"""
    if azimuth > 180 or azimuth < -180:
        raise HTTPException(status_code=400, detail="Azimuth must be between 180 and -180")

    if elevation < 1 or elevation > 90:
        raise HTTPException(status_code=400, detail="Elevation must be between 0 and 90")
    
    try:
        await tracker.rotor.write(azimuth, elevation)
        return {"success": True}
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    