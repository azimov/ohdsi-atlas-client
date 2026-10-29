"""Pydantic models for the WebAPI 3.0 payloads used by the typed client.

The models are deliberately permissive: WebAPI evolves, and unknown fields
must survive a round trip. Use ``model_dump(by_alias=True, exclude_none=True)``
when sending a model back to the server.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


def _to_datetime(value: Any) -> datetime | None:
    """Accept epoch milliseconds, epoch seconds, or ISO strings."""
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        divisor = 1000.0 if value > 10_000_000_000 else 1.0
        return datetime.fromtimestamp(value / divisor, tz=timezone.utc)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


class APIModel(BaseModel):
    """Base model that keeps unknown WebAPI fields."""

    model_config = ConfigDict(extra="allow", populate_by_name=True, arbitrary_types_allowed=True)


class User(APIModel):
    id: int | None = None
    login: str | None = None
    name: str | None = None


class EntityGrant(APIModel):
    read: bool = False
    write: bool = False


class Authorization(APIModel):
    permissions: list[str] = Field(default_factory=list)
    cohort_definition_access: dict[str, Any] = Field(
        default_factory=dict, alias="cohortDefinitionAccess"
    )
    concept_set_access: dict[str, Any] = Field(default_factory=dict, alias="conceptSetAccess")
    source_access: dict[str, Any] = Field(default_factory=dict, alias="sourceAccess")


class CurrentUser(APIModel):
    user: User
    authz: Authorization = Field(default_factory=Authorization)


class Info(APIModel):
    version: str
    build_info: dict[str, Any] = Field(default_factory=dict, alias="buildInfo")
    configuration: dict[str, Any] = Field(default_factory=dict)


class Daimon(APIModel):
    source_daimon_id: int | None = Field(default=None, alias="sourceDaimonId")
    daimon_type: str | None = Field(default=None, alias="daimonType")
    table_qualifier: str | None = Field(default=None, alias="tableQualifier")
    priority: int | None = None


class Source(APIModel):
    source_id: int | None = Field(default=None, alias="sourceId")
    source_name: str | None = Field(default=None, alias="sourceName")
    source_dialect: str | None = Field(default=None, alias="sourceDialect")
    source_key: str | None = Field(default=None, alias="sourceKey")
    daimons: list[Daimon] = Field(default_factory=list)
    connection_string: str | None = Field(default=None, alias="connectionString")

    @property
    def key(self) -> str:
        return self.source_key or ""

    def table_qualifier(self, daimon_type: str = "CDM") -> str | None:
        wanted = daimon_type.lower()
        for daimon in self.daimons:
            if (daimon.daimon_type or "").lower() == wanted:
                return daimon.table_qualifier
        return None


class Concept(APIModel):
    concept_id: int = Field(alias="CONCEPT_ID")
    concept_name: str = Field(default="", alias="CONCEPT_NAME")
    standard_concept: str | None = Field(default=None, alias="STANDARD_CONCEPT")
    standard_concept_caption: str | None = Field(default=None, alias="STANDARD_CONCEPT_CAPTION")
    invalid_reason: str | None = Field(default=None, alias="INVALID_REASON")
    invalid_reason_caption: str | None = Field(default=None, alias="INVALID_REASON_CAPTION")
    concept_code: str | None = Field(default=None, alias="CONCEPT_CODE")
    domain_id: str | None = Field(default=None, alias="DOMAIN_ID")
    vocabulary_id: str | None = Field(default=None, alias="VOCABULARY_ID")
    concept_class_id: str | None = Field(default=None, alias="CONCEPT_CLASS_ID")
    valid_start_date: Any = Field(default=None, alias="VALID_START_DATE")
    valid_end_date: Any = Field(default=None, alias="VALID_END_DATE")

    @property
    def label(self) -> str:
        return f"{self.concept_name} ({self.concept_id})"


class ConceptSetItem(APIModel):
    concept: Concept
    is_excluded: bool = Field(default=False, alias="isExcluded")
    include_descendants: bool = Field(default=False, alias="includeDescendants")
    include_mapped: bool = Field(default=False, alias="includeMapped")


class ConceptSetExpression(APIModel):
    items: list[ConceptSetItem] = Field(default_factory=list)


class ConceptSet(APIModel):
    id: int | None = None
    name: str = ""
    description: str | None = None
    created_by: User | None = Field(default=None, alias="createdBy")
    modified_by: User | None = Field(default=None, alias="modifiedBy")
    created_date: datetime | None = Field(default=None, alias="createdDate")
    modified_date: datetime | None = Field(default=None, alias="modifiedDate")
    read_access: bool = Field(default=False, alias="readAccess")
    write_access: bool = Field(default=False, alias="writeAccess")
    tags: list[dict[str, Any]] = Field(default_factory=list)
    expression: ConceptSetExpression | None = None

    _parse_dates = field_validator("created_date", "modified_date", mode="before")(_to_datetime)


class ConceptSetSummary(ConceptSet):
    """Metadata returned by ``GET /conceptset`` (no expression)."""


class CohortSummary(APIModel):
    id: int
    name: str
    description: str | None = None
    created_by: User | None = Field(default=None, alias="createdBy")
    modified_by: User | None = Field(default=None, alias="modifiedBy")
    created_date: datetime | None = Field(default=None, alias="createdDate")
    modified_date: datetime | None = Field(default=None, alias="modifiedDate")
    read_access: bool = Field(default=False, alias="readAccess")
    write_access: bool = Field(default=False, alias="writeAccess")
    tags: list[dict[str, Any]] = Field(default_factory=list)

    _parse_dates = field_validator("created_date", "modified_date", mode="before")(_to_datetime)


class Cohort(CohortSummary):
    """A cohort definition with its Circe expression parsed into a dictionary."""

    expression: dict[str, Any] = Field(default_factory=dict)
    expression_type: str | None = Field(default=None, alias="expressionType")
    raw_expression: str | None = Field(
        default=None, alias="rawExpression", exclude=True, repr=False
    )

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> Cohort:
        data = dict(payload)
        raw = data.get("expression")
        if isinstance(raw, str):
            try:
                data["expression"] = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                data["expression"] = {}
            data["rawExpression"] = raw
        elif raw is None:
            data["expression"] = {}
        return cls.model_validate(data)


class JobParameters(APIModel):
    job_name: str | None = Field(default=None, alias="jobName")
    source_id: int | None = Field(default=None, alias="sourceId")


class Job(APIModel):
    execution_id: int | None = Field(default=None, alias="executionId")
    status: str | None = None
    start_date: datetime | None = Field(default=None, alias="startDate")
    end_date: datetime | None = Field(default=None, alias="endDate")
    exit_status: str | None = Field(default=None, alias="exitStatus")
    fail_message: str | None = Field(default=None, alias="failMessage")
    job_instance: dict[str, Any] | None = Field(default=None, alias="jobInstance")
    job_parameters: dict[str, Any] | None = Field(default=None, alias="jobParameters")

    _parse_dates = field_validator("start_date", "end_date", mode="before")(_to_datetime)

    @property
    def finished(self) -> bool:
        return (self.status or "").upper() in {
            "COMPLETED",
            "FAILED",
            "ABANDONED",
            "STOPPED",
        }

    @property
    def succeeded(self) -> bool:
        return (self.status or "").upper() == "COMPLETED" and (
            self.exit_status or "COMPLETED"
        ).upper() == "COMPLETED"


class Page(APIModel, Generic[T]):
    content: list[T] = Field(default_factory=list)
    total_elements: int = Field(default=0, alias="totalElements")
    total_pages: int = Field(default=0, alias="totalPages")
    number: int = 0
    size: int = 0
    first: bool = True
    last: bool = True

    @property
    def items(self) -> list[T]:
        return self.content


class ConceptCount(APIModel):
    """Record/person counts for one concept from ``/cdmresults``.

    WebAPI returns a two-element array (record count, descendant record count)
    on older 3.x builds and a four-element array (record, descendant record,
    person, descendant person) when person counts are enabled. ``values``
    preserves the raw array and the named properties are populated from it.
    """

    concept_id: int
    values: list[int] = Field(default_factory=list)

    @property
    def record_count(self) -> int | None:
        return self.values[0] if len(self.values) >= 1 else None

    @property
    def descendant_record_count(self) -> int | None:
        return self.values[1] if len(self.values) >= 2 else None

    @property
    def person_count(self) -> int | None:
        return self.values[2] if len(self.values) >= 3 else None

    @property
    def descendant_person_count(self) -> int | None:
        return self.values[3] if len(self.values) >= 4 else None


class ApiKey(APIModel):
    name: str
    description: str | None = None
    key_identifier: str | None = Field(default=None, alias="keyIdentifier")
    raw_key: str | None = Field(default=None, alias="rawKey")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    disabled: bool = False
    last_used_at: datetime | None = Field(default=None, alias="lastUsedAt")

    _parse_dates = field_validator("created_at", "expires_at", "last_used_at", mode="before")(
        _to_datetime
    )


class Role(APIModel):
    id: int | None = None
    name: str | None = None
    value: str | None = None
    description: str | None = None


class Permission(APIModel):
    id: int | None = None
    value: str | None = None
    description: str | None = None


class Tag(APIModel):
    id: int | None = None
    name: str = ""
    color: str | None = None
    description: str | None = None


class GenerationInfo(APIModel):
    """Cohort generation status for one source.

    WebAPI 3.0 returns an embedded ``id`` object
    (``cohortDefinitionId`` + ``sourceId``), a status such as ``COMPLETE``, and
    optional person/record counts. The model stays permissive because this
    response shape has changed across 3.x builds.
    """

    id: Any = None
    source: Any = None
    status: str | None = None
    start_time: datetime | None = Field(default=None, alias="startTime")
    execution_duration: int | None = Field(default=None, alias="executionDuration")
    person_count: int | None = Field(default=None, alias="personCount")
    record_count: int | None = Field(default=None, alias="recordCount")
    is_valid: bool | None = Field(default=None, alias="isValid")
    is_canceled: bool | None = Field(default=None, alias="isCanceled")
    fail_message: str | None = Field(default=None, alias="failMessage")
    cc_generate_id: int | None = Field(default=None, alias="ccGenerateId")
    is_demographic: bool | None = Field(default=None, alias="isDemographic")
    records: int | None = None

    _parse_dates = field_validator("start_time", mode="before")(_to_datetime)
