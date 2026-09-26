from fastapi import Depends, FastAPI

from app.models.diagnosis import DiagnosisRequest, DiagnosisResponse
from app.services.api_doctor import APIDoctor

app = FastAPI(
    title="API Doctor",
    description="Agentic API error diagnosis service for endpoints, logs, and code context.",
    version="0.1.0",
)


def get_doctor() -> APIDoctor:
    return APIDoctor()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose(
    request: DiagnosisRequest,
    doctor: APIDoctor = Depends(get_doctor),
) -> DiagnosisResponse:
    return await doctor.diagnose(request)


