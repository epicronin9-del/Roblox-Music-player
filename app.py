
from fastapi import FastAPI

app = FastAPI(title="Deplexo Audio API")

@app.get("/")
def home():
    return {"status": "online"}

@app.get("/health")
def health():
    return {"status": "online"}
