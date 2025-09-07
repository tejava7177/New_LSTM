# app/core/schemas.py
from typing import List, Literal, Dict
from pydantic import BaseModel, Field

Genre = Literal["rock", "jazz", "pop"]

class PredictRequest(BaseModel):
    genre: Genre
    seed: List[str] = Field(min_length=3, max_length=3)

class Candidate(BaseModel):
    progression: List[str]
    score: float
    label: str

class PredictResponse(BaseModel):
    candidates: List[Candidate]

class GenerateRequest(BaseModel):
    genre: Genre
    progression: List[str]
    tempo: int = 120
    options: Dict = {}

class JobResponse(BaseModel):
    jobId: str

class StatusResponse(BaseModel):
    status: Literal["QUEUED", "RUNNING", "DONE", "ERROR"]
    progress: int