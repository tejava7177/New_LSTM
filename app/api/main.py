from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes_chords import router as chords_router
from .routes_tracks import router as tracks_router

app = FastAPI(title="CBB Web API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chords_router, prefix="/api/chords", tags=["chords"])
app.include_router(tracks_router, prefix="/api/tracks", tags=["tracks"])

@app.get("/health")
def health():
    return {"ok": True}