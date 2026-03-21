import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import get_db, init_db
from schemas import (
    TransactionOut, TransactionCreate, TransactionUpdate,
    SummaryOut, BreakdownOut, UploadResponse, StatementOut
)
import crud
from pdf_processor import process_pdf

app = FastAPI(title="MySpendee API", version="1.1.0")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── Upload ──────────────────────────────────────────────────────────────────

@app.post("/upload", response_model=UploadResponse)
async def upload_pdfs(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    total_inserted = 0
    total_duplicates = 0
    total_ignored = 0
    errors = []
    last_statement_id = None

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            errors.append(f"{file.filename}: not a PDF")
            continue
        try:
            pdf_bytes = await file.read()
            transactions, bank_name, statement_month, statement_year = process_pdf(pdf_bytes)

            file_inserted = 0
            file_ignored = 0

            for tx in transactions:
                if tx["type"] == "ignored":
                    file_ignored += 1
                    total_ignored += 1
                    if not crud.is_duplicate(db, tx["bank_name"], tx["date"],
                                             tx["amount_mxn"], tx["description"]):
                        crud.create_transaction_from_extracted(db, tx)
                    continue

                if crud.is_duplicate(db, tx["bank_name"], tx["date"],
                                     tx["amount_mxn"], tx["description"]):
                    total_duplicates += 1
                    continue

                crud.create_transaction_from_extracted(db, tx)
                file_inserted += 1
                total_inserted += 1

            # Create statement record
            stmt = crud.create_statement(
                db,
                filename=file.filename,
                bank_name=bank_name,
                month=statement_month,
                year=statement_year,
                inserted=file_inserted,
                ignored=file_ignored,
            )
            last_statement_id = stmt.id

            # Back-fill statement_id on the transactions we just inserted
            from sqlalchemy import text
            db.execute(
                text("""
                    UPDATE transactions
                    SET statement_id = :sid
                    WHERE statement_id IS NULL
                      AND bank_name = :bank
                      AND month = :month
                      AND year = :year
                      AND manually_added = false
                      AND created_at >= (NOW() - INTERVAL '5 minutes')
                """),
                {"sid": str(stmt.id), "bank": bank_name,
                 "month": statement_month, "year": statement_year}
            )
            db.commit()

        except Exception as e:
            errors.append(f"{file.filename}: {str(e)}")

    return UploadResponse(
        inserted=total_inserted,
        duplicates_skipped=total_duplicates,
        ignored=total_ignored,
        errors=errors,
        statement_id=last_statement_id,
    )


# ── Transactions ─────────────────────────────────────────────────────────────

@app.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    category: Optional[str] = Query(None),
    bank: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    skip: int = Query(0),
    limit: int = Query(500),
    db: Session = Depends(get_db),
):
    return crud.get_transactions(db, month=month, year=year, category=category,
                                 bank=bank, type_=type, skip=skip, limit=limit)


@app.post("/transactions", response_model=TransactionOut, status_code=201)
def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    return crud.create_transaction_manual(db, data)


@app.put("/transactions/{tx_id}", response_model=TransactionOut)
def edit_transaction(tx_id: UUID, data: TransactionUpdate, db: Session = Depends(get_db)):
    tx = crud.update_transaction(db, tx_id, data)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


@app.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: UUID, db: Session = Depends(get_db)):
    success = crud.delete_transaction(db, tx_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found")


# ── Summary & Breakdown ───────────────────────────────────────────────────────

@app.get("/summary", response_model=SummaryOut)
def get_summary(
    month: int = Query(...),
    year: int = Query(...),
    db: Session = Depends(get_db),
):
    return crud.get_summary(db, month=month, year=year)


@app.get("/breakdown", response_model=BreakdownOut)
def get_breakdown(
    month: int = Query(...),
    year: int = Query(...),
    db: Session = Depends(get_db),
):
    return crud.get_breakdown(db, month=month, year=year)


# ── Statements ────────────────────────────────────────────────────────────────

@app.get("/statements", response_model=list[StatementOut])
def list_statements(db: Session = Depends(get_db)):
    return crud.get_statements(db)


@app.delete("/statements/{statement_id}", status_code=204)
def delete_statement(statement_id: UUID, db: Session = Depends(get_db)):
    success = crud.delete_statement(db, statement_id)
    if not success:
        raise HTTPException(status_code=404, detail="Statement not found")


# ── Meta ──────────────────────────────────────────────────────────────────────

@app.get("/banks")
def get_banks(db: Session = Depends(get_db)):
    return crud.get_banks(db)


@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    return crud.get_categories(db)
