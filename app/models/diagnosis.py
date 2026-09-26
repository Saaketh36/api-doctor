from typing import Any

from pydantic import BaseModel, Field, field_validator


class DiagnosisRequest(BaseModel):
    endpoint: str = Field(..., min_length=1, examples=["POST /users"])
    error_message: str = Field(..., min_length=1, examples=["500 database connection timeout"])
    logs: str = Field(..., min_length=1, examples=["psycopg2.OperationalError: could not connect to server"])
    code_root: str | None = Field(default=None, description="Optional source root to scan for related code.")

    @field_validator("endpoint", "error_message", "logs", mode="before")
    @classmethod
    def strip_and_validate_non_empty(cls, v: Any) -> str:
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                raise ValueError("Field cannot be empty or whitespace only.")
            return v_stripped
        return v

    @field_validator("code_root", mode="before")
    @classmethod
    def clean_code_root(cls, v: Any) -> str | None:
        if isinstance(v, str):
            v_stripped = v.strip()
            return v_stripped if v_stripped else None
        return v


class EvidenceItem(BaseModel):
    source: str
    detail: str
    confidence: float = Field(ge=0.0, le=1.0)


class CodeReference(BaseModel):
    path: str
    line: int
    snippet: str


class ToolResults(BaseModel):
    log_facts: list[dict[str, Any]] = Field(default_factory=list)
    code_references: list[CodeReference] = Field(default_factory=list)


class DiagnosisResponse(BaseModel):
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    category: str
    evidence: list[EvidenceItem] = Field(default_factory=list)
    fixes: list[str] = Field(default_factory=list)
    debugging_steps: list[str] = Field(default_factory=list)
    tool_results: ToolResults = Field(default_factory=ToolResults)


