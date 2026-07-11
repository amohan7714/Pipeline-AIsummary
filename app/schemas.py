import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import IncidentStatus


class JenkinsWebhookPayload(BaseModel):
    """Minimal shape expected from a Jenkins 'Generic Webhook' / post-build notifier.
    Adjust field names to match your actual Jenkins notification plugin payload."""

    job_name: str
    build_number: int
    build_url: str
    status: str  # e.g. "FAILURE", "SUCCESS", "UNSTABLE"
    branch: str | None = None


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_name: str
    build_number: int
    build_url: str
    branch: str | None
    status: IncidentStatus
    summary: str | None
    root_cause: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime