from fastapi import FastAPI

app = FastAPI(title="SeatLock")


@app.get("/health")
def health():
    return {"status": "ok"}
