from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class TransactionBase(BaseModel):
    date: date
    description: str
    amount_original: Decimal
    currency_original: str = "MXN"
    amount_mxn: Decimal
    exchange_rate_used: Optional[Decimal] = None
    category: str = "Other"
    type: str  # income / expense / ignored
    bank_name: str
    notes: Optional[str] = None


class TransactionCreate(BaseModel):
    date: date
    description: str
    amount_mxn: Decimal
    category: str
    type: str  # income / expense
    bank_name: str
    notes: Optional[str] = None


class TransactionUpdate(BaseModel):
    date: Optional[date] = None
    description: Optional[str] = None
    amount_mxn: Optional[Decimal] = None
    category: Optional[str] = None
    type: Optional[str] = None
    bank_name: Optional[str] = None
    notes: Optional[str] = None


class TransactionOut(TransactionBase):
    id: UUID
    month: int
    year: int
    manually_added: bool
    statement_id: Optional[UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StatementOut(BaseModel):
    id: UUID
    filename: str
    bank_name: Optional[str] = None
    month: Optional[int] = None
    year: Optional[int] = None
    transactions_inserted: int
    transactions_ignored: int
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class SummaryOut(BaseModel):
    month: int
    year: int
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal


class CategoryBreakdown(BaseModel):
    category: str
    amount: Decimal
    count: int


class BreakdownOut(BaseModel):
    month: int
    year: int
    income: list[CategoryBreakdown]
    expenses: list[CategoryBreakdown]


class UploadResponse(BaseModel):
    inserted: int
    duplicates_skipped: int
    ignored: int
    errors: list[str]
    statement_id: Optional[UUID] = None
