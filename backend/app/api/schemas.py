from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel


class MixMetricsModel(BaseModel):
    finalPeakDbfs: float
    finalRmsDbfs: float

    tempoBpm: float
    tempoConfidence: float

    key: str
    scale: str
    keyStrength: float

    vocalShiftMin: float
    vocalShiftMax: float
    vocalShiftMean: float


JobStatus = Literal["completed", "error"]  # si luego quieres 'pending', 'processing', se amplía


class MixResponseModel(BaseModel):
    jobId: str
    projectName: str
    status: JobStatus
    fullSongUrl: str
    stemsZipUrl: Optional[str] = None
    metrics: MixMetricsModel
    errors: Optional[List[str]] = None
