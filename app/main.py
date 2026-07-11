import logging
import uuid

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_db, init_db
from app.models import Incident, IncidentStatus
from app.schemas import IncidentOut, JenkinsWebhookPayload
from app.services.groq_client import analyze_failure
from app.services.jenkins import fetch_console_log

logger = logging.getLogger("jenkins-incident-api")

app = FastAPI(title="Jenkins Incident API", version="1.0.0")


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


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

            console_log = await fetch_console_log(incident.build_url)
            incident.console_log = console_log
            await db.commit()

            # ---- Step: Analyze (Groq AI) ----
            incident.status = IncidentStatus.ANALYZING
            await db.commit()

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

        except Exception:
            logger.exception("Failed to process incident %s", incident_id)
            incident.status = IncidentStatus.FAILED
            await db.commit()


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------
@app.get("/incidents/{incident_id}", response_model=IncidentOut)
async def get_incident(incident_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@app.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).order_by(Incident.created_at.desc()))
    return result.scalars().all()


@app.get("/health")
async def health():
    return {"status": "ok"}