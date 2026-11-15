from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class CopilotMetric(BaseModel):
    label: str
    value: str
    status: Optional[str] = "good"  # good, warn, bad

class CopilotQueryRequest(BaseModel):
    dataset_id: str = Field(..., description="Target dataset UUID")
    question: str = Field(..., min_length=1, max_length=1000, description="Natural language question")

class CopilotQueryResponse(BaseModel):
    answer: str
    metrics: Optional[List[CopilotMetric]] = None
    recommendations: Optional[List[str]] = None
    dataset_id: str
    dataset_name: str
    model: str
    is_fallback: bool = False
    evidence_used: Optional[List[str]] = None

class CopilotMessageSchema(BaseModel):
    id: str
    dataset_id: str
    role: str  # user, assistant
    content: str
    recommendations: Optional[List[str]] = None
    metrics: Optional[List[Dict[str, Any]]] = None
    model_used: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class CopilotSuggestionsResponse(BaseModel):
    dataset_id: str
    dataset_name: str
    suggestions: List[str]
