import json

from groq import AsyncGroq

from app.config import settings

_client = AsyncGroq(api_key=settings.groq_api_key)

SYSTEM_PROMPT = (
    "You are a CI/CD reliability engineer. You are given a Jenkins build's "
    "console log for a FAILED build. Analyze it and respond with strict JSON "
    "only, matching this schema:\n"
    "{\n"
    '  "summary": "2-3 sentence plain-English summary of what went wrong",\n'
    '  "root_cause": "most likely root cause, 1-2 sentences",\n'
    '  "error_message": "the single most relevant error line/message from the log"\n'
    "}\n"
    "Do not include markdown formatting, backticks, or any text outside the JSON object."
)


async def analyze_failure(job_name: str, build_number: int, console_log: str) -> dict:
    user_prompt = (
        f"Job: {job_name}\n"
        f"Build number: {build_number}\n\n"
        f"Console log (tail):\n{console_log}"
    )

    response = await _client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = {
            "summary": raw or "Groq returned an unparseable response.",
            "root_cause": None,
            "error_message": None,
        }

    return {
        "summary": parsed.get("summary"),
        "root_cause": parsed.get("root_cause"),
        "error_message": parsed.get("error_message"),
    }