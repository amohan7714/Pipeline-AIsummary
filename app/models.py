import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class IncidentStatus(str, enum.Enum):
    RECEIVED = "received"
    FETCHING_LOG = "fetching_log"
    ANALYZING = "analyzing"
    RESOLVED = "resolved"
    FAILED = "failed"


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    job_name: Mapped[str] = mapped_column(String(255), index=True)
    build_number: Mapped[int] = mapped_column(Integer)
    build_url: Mapped[str] = mapped_column(String(1024))
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)

    status: Mapped[IncidentStatus] = mapped_column(
        Enum(IncidentStatus), default=IncidentStatus.RECEIVED, index=True
    )

    console_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )