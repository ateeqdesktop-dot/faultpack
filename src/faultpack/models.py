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


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format_version: Literal["0.1", "0.2"] = "0.2"
    pack_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: Source = Field(default_factory=Source)
    command: CommandSpec
    environment: Environment
    input_files: list[FileEntry] = Field(default_factory=list)
    observed: Observed
    expectation: Expectation = Field(default_factory=Expectation)
    fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @property
    def canonical_created_at(self) -> str:
        return self.created_at.astimezone(timezone.utc).isoformat()
