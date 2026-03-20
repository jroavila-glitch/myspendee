import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Numeric, Boolean, Integer, Date, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False)
    description = Column(Text, nullable=False)
    amount_original = Column(Numeric(12, 2), nullable=False)
    currency_original = Column(String(10), nullable=False, default="MXN")
    amount_mxn = Column(Numeric(12, 2), nullable=False)
    exchange_rate_used = Column(Numeric(10, 6), nullable=True)
    category = Column(String(100), nullable=False, default="Other")
    type = Column(String(20), nullable=False)  # income / expense / ignored
    bank_name = Column(String(100), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    manually_added = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
