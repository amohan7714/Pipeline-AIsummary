from urllib.parse import quote

import httpx

from app.config import settings

# Groq's context window can't take an unlimited log; keep the tail, since
# failures are almost always near the end of the console output.
MAX_LOG_CHARS = 12_000


async def fetch_console_log(job_name: str, build_number: int) -> str:
    """Fetch the plain-text console log for a Jenkins build.

    Deliberately does NOT use the build_url Jenkins sends in the webhook
    payload. That URL is built from Jenkins' own "Jenkins URL" system
    setting, which is often a public address (e.g. an EC2 public IP) that
    isn't reachable from *inside* this container/host — most cloud
    providers, AWS included, don't support an instance reaching its own
    public IP from within itself ("hairpin" routing).

    Instead this builds the request from JENKINS_URL in settings, which
    should be set to an address that IS reachable from where this API runs
    (e.g. http://host.docker.internal:8080, an internal/private IP, or a
    Docker Compose service name if Jenkins also runs in this network).
    """
    if not settings.jenkins_url:
        raise RuntimeError(
            "JENKINS_URL is not set — cannot fetch console log. "
            "Set it to an address reachable from inside this container "
            "(not the public IP Jenkins reports in its webhook payload)."
        )

    base = settings.jenkins_url.rstrip("/")
    job_path = quote(job_name, safe="")
    url = f"{base}/job/{job_path}/{build_number}/consoleText"

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