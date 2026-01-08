from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Initialize FastAPI App
app = FastAPI(
    title="Simco AI Metrics Service",
    description="API for accessing manufacturing metrics from BigQuery.",
    version="1.0.0"
)

# CORS Configuration
origins = ["*"]  # Restrict this in production!

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import Routes
from routes import router as metrics_router
app.include_router(metrics_router)

@app.get("/")
def health_check():
    return {"status": "ok", "service": "metrics-service"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
