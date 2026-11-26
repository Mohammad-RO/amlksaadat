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
    category: str
    deal_type: str
    deposit: int | None = None
    rent: int | None = None
    deposit_min: int | None = None
    deposit_max: int | None = None
    rent_min: int | None = None
    rent_max: int | None = None
    rent_convertible: bool = False
    structured_text: str
    unique_code: str
    llm_used: bool
    searchable: bool
    image_count: int
    archived: bool
    created_at_jalali: str
    warnings: list[str] = []


class DivarLinkIn(BaseModel):
    url: str = Field(min_length=8, max_length=500)


class DivarColleagueOut(BaseModel):
    id: int
    name: str
    phone: str


class DivarColleaguesOut(BaseModel):
    url: str
    posts_url: str = ""
    items: list[DivarColleagueOut]
    last_sync_at: str = ""
    last_sync_note: str = ""


class DivarSyncOut(BaseModel):
    running: bool
    needs_login: bool = False
    colleagues_ready: bool = False
    total: int = 0
    completed: int = 0
    sent: int = 0
    skipped: int = 0
    removed: int = 0
    errors: list[str] = []
    message: str = ""
    phase: str = "idle"
    current_index: int = 0
    current_title: str = ""
    current_author: str = ""
    paused: bool = False


class DivarRefreshOut(BaseModel):
    needs_login: bool = False
    added: int = 0
    removed: int = 0
    updated: int = 0
    url: str = ""
    items: list[DivarColleagueOut] = []


class DivarPhoneIn(BaseModel):
    phone: str


class DivarCodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class HealthOut(BaseModel):
    ok: bool
    bot_configured: bool
    archive_configured: bool
