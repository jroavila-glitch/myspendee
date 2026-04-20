from datetime import date as date_type
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from models import Transaction, Statement, Loan, LoanPayment
from schemas import TransactionCreate, TransactionUpdate, LoanCreate, LoanUpdate, LoanPaymentCreate, LoanPaymentUpdate


# ── Duplicate Detection ───────────────────────────────────────────────────────

def is_duplicate(db: Session, bank_name: str, tx_date: date_type,
                 amount_mxn: float, description: str) -> bool:
    existing = db.query(Transaction).filter(
        and_(
            func.lower(Transaction.bank_name) == bank_name.lower(),
            Transaction.date == tx_date,
            func.abs(Transaction.amount_mxn - Decimal(str(amount_mxn))) < Decimal("0.01"),
            func.lower(Transaction.description) == description.lower(),
        )
    ).first()
    return existing is not None


# ── Statements ────────────────────────────────────────────────────────────────

def create_statement(db: Session, filename: str, bank_name: str = None,
                     month: int = None, year: int = None,
                     inserted: int = 0, ignored: int = 0) -> Statement:
    s = Statement(
        filename=filename,
        bank_name=bank_name,
        month=month,
        year=year,
        transactions_inserted=inserted,
        transactions_ignored=ignored,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def get_statements(db: Session) -> list[Statement]:
    return db.query(Statement).order_by(Statement.uploaded_at.desc()).all()


def delete_statement(db: Session, statement_id: UUID) -> bool:
    s = db.query(Statement).filter(Statement.id == statement_id).first()
    if not s:
        return False
    # Delete all linked transactions
    db.query(Transaction).filter(Transaction.statement_id == statement_id).delete()
    db.delete(s)
    db.commit()
    return True


# ── Transactions ──────────────────────────────────────────────────────────────

def create_transaction_from_extracted(db: Session, tx_data: dict) -> Transaction:
    tx = Transaction(**tx_data)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def create_transaction_manual(db: Session, data: TransactionCreate) -> Transaction:
    tx = Transaction(
        date=data.date,
        description=data.description,
        amount_original=data.amount_mxn,
        currency_original="MXN",
        amount_mxn=data.amount_mxn,
        exchange_rate_used=Decimal("1.0"),
        category=data.category,
        type=data.type,
        bank_name=data.bank_name,
        month=data.date.month,
        year=data.date.year,
        manually_added=True,
        notes=data.notes,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def update_transaction(db: Session, tx_id: UUID, data: TransactionUpdate) -> Optional[Transaction]:
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(tx, field, value)
    # Recalculate month/year if date changed
    if data.date:
        tx.month = data.date.month
        tx.year = data.date.year
    # Sync amount_original if amount_mxn changed on a manual/MXN transaction
    if data.amount_mxn and tx.currency_original == "MXN":
        tx.amount_original = data.amount_mxn
    db.commit()
    db.refresh(tx)
    return tx


def get_transactions(db: Session, month: Optional[int] = None, year: Optional[int] = None,
                     category: Optional[str] = None, bank: Optional[str] = None,
                     type_: Optional[str] = None, skip: int = 0, limit: int = 500):
    q = db.query(Transaction)
    if month:
        q = q.filter(Transaction.month == month)
    if year:
        q = q.filter(Transaction.year == year)
    if category:
        q = q.filter(func.lower(Transaction.category) == category.lower())
    if bank:
        q = q.filter(func.lower(Transaction.bank_name) == bank.lower())
    if type_:
        q = q.filter(Transaction.type == type_)
    else:
        # Default: exclude ignored from main listing
        q = q.filter(Transaction.type != "ignored")
    return q.order_by(Transaction.date.desc()).offset(skip).limit(limit).all()


def get_summary(db: Session, month: int, year: int) -> dict:
    base = db.query(Transaction).filter(
        Transaction.month == month,
        Transaction.year == year,
        Transaction.type != "ignored",
    )
    total_income = base.filter(Transaction.type == "income").with_entities(
        func.coalesce(func.sum(Transaction.amount_mxn), 0)
    ).scalar()
    total_expenses = base.filter(Transaction.type == "expense").with_entities(
        func.coalesce(func.sum(Transaction.amount_mxn), 0)
    ).scalar()
    return {
        "month": month,
        "year": year,
        "total_income": Decimal(str(total_income)),
        "total_expenses": Decimal(str(total_expenses)),
        "net": Decimal(str(total_income)) - Decimal(str(total_expenses)),
    }


def get_breakdown(db: Session, month: int, year: int) -> dict:
    base = db.query(Transaction).filter(
        Transaction.month == month,
        Transaction.year == year,
        Transaction.type != "ignored",
    )

    income_rows = (
        base.filter(Transaction.type == "income")
        .with_entities(
            Transaction.category,
            func.sum(Transaction.amount_mxn).label("amount"),
            func.count(Transaction.id).label("count"),
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount_mxn).desc())
        .all()
    )

    expense_rows = (
        base.filter(Transaction.type == "expense")
        .with_entities(
            Transaction.category,
            func.sum(Transaction.amount_mxn).label("amount"),
            func.count(Transaction.id).label("count"),
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount_mxn).desc())
        .all()
    )

    return {
        "month": month,
        "year": year,
        "income": [{"category": r.category, "amount": Decimal(str(r.amount)), "count": r.count}
                   for r in income_rows],
        "expenses": [{"category": r.category, "amount": Decimal(str(r.amount)), "count": r.count}
                     for r in expense_rows],
    }


def delete_transaction(db: Session, tx_id: UUID) -> bool:
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        return False
    db.delete(tx)
    db.commit()
    return True


def bulk_update_transactions(db: Session, ids: list, updates: dict) -> int:
    """Update category/type/notes on a list of transaction IDs. Returns count updated."""
    if not ids or not updates:
        return 0
    txs = db.query(Transaction).filter(Transaction.id.in_(ids)).all()
    for tx in txs:
        for field, value in updates.items():
            if value is not None:
                setattr(tx, field, value)
    db.commit()
    return len(txs)


def get_banks(db: Session) -> list[str]:
    rows = db.query(Transaction.bank_name).distinct().order_by(Transaction.bank_name).all()
    return [r[0] for r in rows]


# ── Loans ─────────────────────────────────────────────────────────────────────

def get_loans(db: Session) -> list[Loan]:
    return db.query(Loan).order_by(Loan.created_at.asc()).all()


def get_loan(db: Session, loan_id: UUID) -> Optional[Loan]:
    return db.query(Loan).filter(Loan.id == loan_id).first()


def create_loan(db: Session, data: LoanCreate) -> Loan:
    loan = Loan(**data.model_dump())
    db.add(loan)
    db.commit()
    db.refresh(loan)
    return loan


def update_loan(db: Session, loan_id: UUID, data: LoanUpdate) -> Optional[Loan]:
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(loan, field, value)
    db.commit()
    db.refresh(loan)
    return loan


def delete_loan(db: Session, loan_id: UUID) -> bool:
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        return False
    db.delete(loan)
    db.commit()
    return True


def get_loan_payments(db: Session, loan_id: UUID) -> list[LoanPayment]:
    return (
        db.query(LoanPayment)
        .filter(LoanPayment.loan_id == loan_id)
        .order_by(LoanPayment.date.desc())
        .all()
    )


def create_loan_payment(db: Session, loan_id: UUID, data: LoanPaymentCreate) -> LoanPayment:
    payment = LoanPayment(loan_id=loan_id, **data.model_dump())
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def update_loan_payment(db: Session, payment_id: UUID, data: LoanPaymentUpdate) -> Optional[LoanPayment]:
    p = db.query(LoanPayment).filter(LoanPayment.id == payment_id).first()
    if not p:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(p, field, value)
    db.commit()
    db.refresh(p)
    return p


def delete_loan_payment(db: Session, payment_id: UUID) -> bool:
    p = db.query(LoanPayment).filter(LoanPayment.id == payment_id).first()
    if not p:
        return False
    db.delete(p)
    db.commit()
    return True


def get_categories(db: Session) -> dict:
    return {
        "income": [
            "Tennis Lessons", "Perenniam Agency", "Ro IG Tennis", "Tennis Smash & Social",
            "PlaticArte", "Credit Cards Cashback", "Azulik", "Investments", "Gifts", "Other"
        ],
        "expense": [
            "Rent", "Home", "Groceries", "Food & Drink", "Tennis", "Car", "Transport",
            "IG Ro Project", "Healthcare", "Gym", "Phone/Tech", "Books", "Travel",
            "Personal Dev", "Gifts", "Entertainment", "Visa Portugal", "Bills/Fees",
            "Clothing", "Perenniam Agency", "Beauty", "Investments", "Loan Papá", "Other"
        ]
    }
