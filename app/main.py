from fastapi import FastAPI
import logging
import os
import uvicorn

from core.logging_config import LOGGING_CONFIG
from api.satellite_routes import satellite_router
from api.system_routes import system_router
from api.rotor_routes import rotor_router
from api.dependencies import create_tracker
from contextlib import asynccontextmanager

os.makedirs("logs", exist_ok=True)

logging.config.dictConfig(LOGGING_CONFIG)

# Configure general logger
logger = logging.getLogger("groundstation")


@asynccontextmanager
async def lifespan(app : FastAPI):
    await create_tracker()

    yield
    #shutdown code can go here i guess


app = FastAPI(lifespan=lifespan)

app.include_router(satellite_router, prefix='/satellite')
app.include_router(system_router, prefix='/system')
app.include_router(rotor_router, prefix='/rotor')



if __name__ == "__main__":
    # Automatically create the logs folder if not there
    logger.info("Starting FastAPI server with uvicorn")
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)