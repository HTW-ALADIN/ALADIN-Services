from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from core.download_service import BatchSizeError, validate_batch_size


class DownloadItem(BaseModel):
    provider: str
    paper_id: str


class DownloadRequest(BaseModel):
    items: list[DownloadItem]
    credentials: dict[str, dict[str, str]] = Field(default_factory=dict)

    @field_validator("items")
    @classmethod
    def _bounded_batch(cls, items: list[DownloadItem]) -> list[DownloadItem]:
        try:
            validate_batch_size(len(items))
        except BatchSizeError as exc:
            raise ValueError(str(exc)) from exc
        return items


class DownloadResultSchema(BaseModel):
    provider: str
    paper_id: str
    status: Literal["ok", "paywalled", "not_found", "error"]
    path: str | None = None
    error: str | None = None


class DownloadResponse(BaseModel):
    results: list[DownloadResultSchema]


class FulltextResponse(BaseModel):
    provider: str
    paper_id: str
    text: str
