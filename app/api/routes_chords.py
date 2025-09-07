# app/api/routes_chords.py
from fastapi import APIRouter
from ..core.schemas import PredictRequest, PredictResponse, Candidate
from ..core.pipeline_predict import predict_top_k

router = APIRouter()

@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    results = predict_top_k(req.genre, req.seed, k=3)
    return {"candidates": [Candidate(**r) for r in results]}