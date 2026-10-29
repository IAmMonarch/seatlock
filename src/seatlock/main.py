from fastapi import FastAPI

import seatlock.models  # noqa: F401
from seatlock.auth.router import router as auth_router
from seatlock.venues.router import router as venue_router

app = FastAPI(title="SeatLock")
app.include_router(auth_router)
app.include_router(venue_router)
