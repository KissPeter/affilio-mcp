from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, AnyHttpUrl


class ShortenRequest(BaseModel):
    url: AnyHttpUrl


class ShortenResponse(BaseModel):
    short_url: str
    qr_url: str
    expires_at: Optional[datetime.datetime] = None
    classification: str
    powered_by: str
    pending: bool

