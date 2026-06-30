from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class SubscriberCreate(BaseModel):
    name: str
    email: EmailStr
    is_active: bool = True


class SubscriberUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    is_active: bool | None = None


class SubscriberOut(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CSVImportResult(BaseModel):
    imported: int
    skipped: int
    invalid_rows: list[str]


class EmailLogOut(BaseModel):
    id: int
    subscriber_id: int
    newsletter_id: int
    status: str
    provider_message_id: str | None = None
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EmailStatistics(BaseModel):
    total_emails: int
    successful_deliveries: int
    failed_deliveries: int
    pending: int
    success_percentage: float