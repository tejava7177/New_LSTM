# app/api/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes_chords import router as chords_router
from .routes_tracks import router as tracks_router
from .routes_render import router as render_router
# ↓ 실제 파일이 있을 때만 사용하세요.
# from .routes_audio  import router as audio_router

app = FastAPI(title="CBB Web API", version="0.1.0")

# CORS: credentials(True)면 * 사용 X → 프론트 도메인을 명시
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(chords_router, prefix="/api/chords", tags=["chords"])
app.include_router(tracks_router, prefix="/api/tracks", tags=["tracks"])
# if routes_audio 모듈이 있다면 활성화
# app.include_router(audio_router,  prefix="/api/audio",  tags=["audio"])
app.include_router(render_router, prefix="/api/render", tags=["render"])

@app.get("/health")
async def health():
    return {"ok": True}