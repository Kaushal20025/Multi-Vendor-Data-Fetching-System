from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class VendorType(str, Enum):
    SYNC = "sync"
    ASYNC = "async"


class JobRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="Any JSON payload")


class JobResponse(BaseModel):
    request_id: str = Field(..., description="Unique job identifier")


class JobStatusResponse(BaseModel):
    status: JobStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class VendorRequest(BaseModel):
    job_id: str
    payload: Dict[str, Any]


class VendorResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class WebhookRequest(BaseModel):
    job_id: str
    data: Dict[str, Any]


def generate_request_id() -> str:
    """Generate a unique request ID"""
    return str(uuid.uuid4())


def clean_vendor_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean vendor response data by trimming strings and removing PII
    """
    if not isinstance(data, dict):
        return data
    
    cleaned = {}
    for key, value in data.items():
        if isinstance(value, str):
            # Trim whitespace
            cleaned_value = value.strip()
            # Remove common PII patterns (simplified)
            if any(pii in key.lower() for pii in ['email', 'phone', 'ssn', 'password']):
                cleaned_value = '[REDACTED]'
            cleaned[key] = cleaned_value
        elif isinstance(value, dict):
            cleaned[key] = clean_vendor_data(value)
        elif isinstance(value, list):
            cleaned[key] = [clean_vendor_data(item) if isinstance(item, dict) else item for item in value]
        else:
            cleaned[key] = value
    
    return cleaned 