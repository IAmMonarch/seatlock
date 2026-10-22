from fastapi import FastAPI

app = FastAPI(title="SeatLock")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
