import os
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import get_db, init_db
from schemas import (
    TransactionOut, TransactionCreate, SummaryOut, BreakdownOut, UploadResponse
)
import crud
from pdf_processor import process_pdf

app = FastAPI(title="MySpendee API", version="1.0.0")

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
    inserted = 0
    duplicates_skipped = 0
    ignored = 0
    errors = []

    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            errors.append(f"{file.filename}: not a PDF")
            continue
        try:
            pdf_bytes = await file.read()
            transactions = process_pdf(pdf_bytes)

            for tx in transactions:
                if tx["type"] == "ignored":
                    ignored += 1
                    # Still store ignored transactions
                    if not crud.is_duplicate(db, tx["bank_name"], tx["date"],
                                             tx["amount_mxn"], tx["description"]):
                        crud.create_transaction_from_extracted(db, tx)
                    continue

                if crud.is_duplicate(db, tx["bank_name"], tx["date"],
                                     tx["amount_mxn"], tx["description"]):
                    duplicates_skipped += 1
                    continue

                crud.create_transaction_from_extracted(db, tx)
                inserted += 1

        except Exception as e:
            errors.append(f"{file.filename}: {str(e)}")

    return UploadResponse(
        inserted=inserted,
        duplicates_skipped=duplicates_skipped,
        ignored=ignored,
        errors=errors,
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


# ── Meta ──────────────────────────────────────────────────────────────────────

@app.get("/banks")
def get_banks(db: Session = Depends(get_db)):
    return crud.get_banks(db)


@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    return crud.get_categories(db)
