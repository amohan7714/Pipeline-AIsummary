import httpx

from app.config import settings

# Groq's context window can't take an unlimited log; keep the tail, since
# failures are almost always near the end of the console output.
MAX_LOG_CHARS = 12_000


async def fetch_console_log(build_url: str) -> str:
    """Fetch the plain-text console log for a Jenkins build.

    build_url is expected to look like: https://jenkins.example.com/job/my-job/42/
    Jenkins exposes the raw log at "<build_url>/consoleText".
    """
    url = build_url.rstrip("/") + "/consoleText"

    auth = None
    if settings.jenkins_user and settings.jenkins_api_token:
        auth = (settings.jenkins_user, settings.jenkins_api_token)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, auth=auth)
        response.raise_for_status()
        log = response.text

    if len(log) > MAX_LOG_CHARS:
        log = log[-MAX_LOG_CHARS:]

    return log