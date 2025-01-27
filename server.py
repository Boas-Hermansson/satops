from fastapi import FastAPI
from pydantic import BaseModel
import subprocess

class Direction(BaseModel):
    azimuth : int
    elevation : int




app = FastAPI() 


@app.get("/")
def read():
    return {"Hello" : "World" }


@app.post("/rotor")
def set_direction(direction: Direction):
    az = direction.azimuth 
    if az > 180 or az < -180:
        raise HTTPException(status_code=400, detail="azimuth must be between 180 and -180")

    el = direction.elevation
    if el < 1 or el > 90:
        raise HTTPException(status_code=400, detail="elevation must be between 0 and 90")

    subprocess.check_call(["rotctl", "P", az, el])


@app.get("/rotor")
def get_direction():
    output = subprocess.check_output(["rotctl", "p"]).splitlines()
    direction = Direction(azimuth = output[0].decode(), elevation = output[1].decode())
    return direction