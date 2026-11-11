from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminLogin(BaseModel):
    username: str
    password: str


class AgentLogin(BaseModel):
    phone: str


class TokenOut(BaseModel):
    token: str
    role: str
    name: str


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = None
    is_active: bool | None = None


class AgentOut(BaseModel):
    id: int
    name: str
    phone: str
    is_active: bool
    listings_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportRow(BaseModel):
    agent_id: int
    name: str
    phone: str
    is_active: bool
    listings_count: int


class ReportOut(BaseModel):
    date_from: str | None
    date_to: str | None
    items: list[ReportRow]


class ListingCreate(BaseModel):
    divar_url: str = Field(min_length=8, max_length=500)


class ListingOut(BaseModel):
    id: int
    title: str
    divar_url: str
    divar_token: str
    area: float | None
    price: int | None
    bedrooms: int | None
    structured_text: str
    unique_code: str
    llm_used: bool
    searchable: bool
    image_count: int
    archived: bool
    created_at_jalali: str
    warnings: list[str] = []


class HealthOut(BaseModel):
    ok: bool
    bot_configured: bool
    archive_configured: bool
