import subprocess
from fastapi import APIRouter, HTTPException

rotor_router = APIRouter()




@rotor_router.get('/status')
async def rotor_status():
    """Get the rotor status from rotctl"""
    # TODO try to connect using sockets instead
    try:
        output = subprocess.check_output(["tctl", "p"]).splitlines()
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
    
@rotor_router.post('/control')
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
    