from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str | None = None
    commit: str | None = None
    branch: str | None = None


class CommandSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    argv: list[str] = Field(min_length=1)
    cwd: str = "."
    timeout_seconds: float = Field(default=30.0, gt=0, le=3600)
    env_allowlist: list[str] = Field(default_factory=list)

    @field_validator("cwd")
    @classmethod
    def relative_cwd(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError("cwd must be relative and cannot contain traversal")
        return value


class Producer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    version: str | None = Field(default=None, max_length=64)
    runtime: str | None = Field(default=None, max_length=128)


class EvidenceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int = Field(ge=1)
    kind: Literal["tool_call", "model_response", "assertion", "policy_decision", "annotation"]
    name: str = Field(min_length=1, max_length=128)
    payload_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    attributes: dict[str, str] = Field(default_factory=dict)


class Environment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    os: str
    platform: str
    python: str
    variables: dict[str, str] = Field(default_factory=dict)


class FileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or value in {"", "."} or "\\" in value:
            raise ValueError("path must be relative and cannot contain traversal")
        return value


class Observed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["passed", "failed", "timeout", "error"]
    exit_code: int | None = None
    duration_ms: int = Field(ge=0)
    stdout_path: str = "artifacts/stdout.txt"
    stderr_path: str = "artifacts/stderr.txt"
    stdout_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    stderr_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Expectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exit_code: int | None = 0
    stdout_regex: str | None = None
    stderr_regex: str | None = None
    stdout_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    stderr_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    duration_max_ms: int | None = Field(default=None, ge=0)


class MatrixProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    env: dict[str, str] = Field(default_factory=dict)
    argv: list[str] | None = None
    timeout_seconds: float | None = Field(default=None, gt=0, le=3600)

    @field_validator("env")
    @classmethod
    def safe_environment_names(cls, value: dict[str, str]) -> dict[str, str]:
        for name in value:
            valid_name = name and name.replace("_", "A").isalnum()
            starts_correctly = name[:1].isalpha() or name[:1] == "_"
            if not valid_name or not starts_correctly:
                raise ValueError(f"invalid environment variable name: {name}")
        return value

    @field_validator("argv")
    @classmethod
    def non_empty_argv(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and not value:
            raise ValueError("argv override cannot be empty")
        return value


class MatrixResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: str
    outcome: Literal["reproduced", "mismatch", "execution_error"]
    status: Literal["passed", "failed", "timeout", "error"]
    exit_code: int | None = None
    duration_ms: int = Field(ge=0)
    reasons: list[str] = Field(default_factory=list)


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format_version: Literal["0.1", "0.2", "0.3"] = "0.2"
    pack_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: Source = Field(default_factory=Source)
    producer: Producer | None = None
    command: CommandSpec
    environment: Environment
    input_files: list[FileEntry] = Field(default_factory=list)
    observed: Observed
    expectation: Expectation = Field(default_factory=Expectation)
    events: list[EvidenceEvent] = Field(default_factory=list)
    fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @field_validator("events")
    @classmethod
    def ordered_unique_events(cls, value: list[EvidenceEvent]) -> list[EvidenceEvent]:
        sequences = [event.sequence for event in value]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("events must have strictly increasing unique sequence values")
        return value

    @property
    def canonical_created_at(self) -> str:
        return self.created_at.astimezone(timezone.utc).isoformat()
