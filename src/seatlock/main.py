from fastapi import FastAPI

from seatlock.auth.router import router as auth_router

app = FastAPI(title="SeatLock")
app.include_router(auth_router)
