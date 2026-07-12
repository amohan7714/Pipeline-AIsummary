import logging
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_db, init_db
from app.models import Incident, IncidentEvent, IncidentStatus
from app.schemas import IncidentDetailOut, IncidentEventOut, IncidentOut, JenkinsWebhookPayload
from app.services.groq_client import analyze_failure
from app.services.jenkins import fetch_console_log
from app.ws import manager

logger = logging.getLogger("jenkins-incident-api")

app = FastAPI(title="Jenkins Incident API", version="1.0.0")

STATIC_DIR = Path(__file__).parent / "static"

STAGE_MESSAGES = {
    IncidentStatus.RECEIVED: "Webhook received from Jenkins",
    IncidentStatus.FETCHING_LOG: "Fetching console log from Jenkins",
    IncidentStatus.ANALYZING: "Analyzing failure with Groq AI",
    IncidentStatus.RESOLVED: "Analysis complete, result saved",
    IncidentStatus.FAILED: "Pipeline processing failed",
}


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


# ---------------------------------------------------------------------------
# Dashboard (static single-page UI)
# ---------------------------------------------------------------------------
@app.get("/")
async def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


# ---------------------------------------------------------------------------
# Live updates
# ---------------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            # Dashboard doesn't send anything meaningful; just keep the
            # connection open and detect disconnects.
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


async def log_event(db: AsyncSession, incident: Incident, stage: IncidentStatus, message: str | None = None) -> None:
    event = IncidentEvent(
        incident_id=incident.id,
        stage=stage,
        message=message or STAGE_MESSAGES.get(stage, stage.value),
    )
    db.add(event)
    await db.commit()

    await manager.broadcast(
        {
            "type": "incident_update",
            "incident": IncidentOut.model_validate(incident).model_dump(mode="json"),
            "event": IncidentEventOut.model_validate(event).model_dump(mode="json"),
        }
    )


# ---------------------------------------------------------------------------
# Step: Receive Jenkins Webhook
# ---------------------------------------------------------------------------
@app.post("/webhook/jenkins", response_model=IncidentOut, status_code=status.HTTP_202_ACCEPTED)
async def receive_jenkins_webhook(
    payload: JenkinsWebhookPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: str | None = Header(default=None),
):
    if settings.jenkins_webhook_secret and x_webhook_secret != settings.jenkins_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    # Only failed builds become incidents
    if payload.status.upper() != "FAILURE":
        raise HTTPException(
            status_code=422,
            detail=f"Ignoring non-failure build status: {payload.status}",
        )

    # ---- Step: Create Incident ----
    incident = Incident(
        job_name=payload.job_name,
        build_number=payload.build_number,
        build_url=payload.build_url,
        branch=payload.branch,
        status=IncidentStatus.RECEIVED,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    await log_event(db, incident, IncidentStatus.RECEIVED)

    # Fetch log -> analyze -> save happen after the response is sent,
    # so Jenkins isn't kept waiting on the webhook call.
    background_tasks.add_task(process_incident, incident.id)

    return incident


# ---------------------------------------------------------------------------
# Steps: Fetch Console Log -> Analyze -> Save Result
# ---------------------------------------------------------------------------
async def process_incident(incident_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        incident = await db.get(Incident, incident_id)
        if incident is None:
            logger.error("Incident %s not found", incident_id)
            return

        try:
            # ---- Step: Fetch Console Log ----
            incident.status = IncidentStatus.FETCHING_LOG
            await db.commit()
            await log_event(db, incident, IncidentStatus.FETCHING_LOG)

            console_log = await fetch_console_log(incident.build_url)
            incident.console_log = console_log
            await db.commit()

            # ---- Step: Analyze (Groq AI) ----
            incident.status = IncidentStatus.ANALYZING
            await db.commit()
            await log_event(db, incident, IncidentStatus.ANALYZING)

            analysis = await analyze_failure(
                job_name=incident.job_name,
                build_number=incident.build_number,
                console_log=console_log,
            )

            # ---- Step: Save Result ----
            incident.summary = analysis["summary"]
            incident.root_cause = analysis["root_cause"]
            incident.error_message = analysis["error_message"]
            incident.status = IncidentStatus.RESOLVED
            await db.commit()
            await log_event(db, incident, IncidentStatus.RESOLVED)

        except Exception as exc:
            logger.exception("Failed to process incident %s", incident_id)
            incident.status = IncidentStatus.FAILED
            await db.commit()
            await log_event(db, incident, IncidentStatus.FAILED, message=f"Error: {exc}")


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------
@app.get("/incidents/{incident_id}", response_model=IncidentDetailOut)
async def get_incident(incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    result = await db.execute(
        select(IncidentEvent)
        .where(IncidentEvent.incident_id == incident_id)
        .order_by(IncidentEvent.created_at.asc())
    )
    events = result.scalars().all()

    detail = IncidentDetailOut.model_validate(incident)
    detail.events = [IncidentEventOut.model_validate(e) for e in events]
    return detail


@app.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).order_by(Incident.created_at.desc()))
    return result.scalars().all()


@app.get("/health")
async def health():
    return {"status": "ok"}