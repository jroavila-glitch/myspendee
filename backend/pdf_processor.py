"""
Processes PDF bank statements using Claude API (vision).

For PDFs > 5 pages the file is split into chunks of 4 pages each and
processed in parallel calls so we never hit Claude's output-token ceiling.

Returns: (list_of_transaction_dicts, bank_name, statement_month, statement_year)
"""

import base64
import io
import json
import os
import re
from datetime import date as _date
from decimal import Decimal

import anthropic
import pypdf

from classifier import classify


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
PAGES_PER_CHUNK = 4   # pages sent to Claude per call for long PDFs
MAX_TOKENS = 16000    # enough for ~150 transactions per call


# ─────────────────────────────────────────────────────────────────────────────
# Extraction prompts
# ─────────────────────────────────────────────────────────────────────────────

FULL_EXTRACTION_PROMPT = """You are a financial data extraction assistant. Extract ALL transactions from the provided bank statement PDF.

BANK ACCOUNTS AND THEIR LOGIC:
- Revolut (EUR, Debit): "Money in" = direction "in", "Money out" = direction "out"
- Millennium BCP (EUR, Debit): CREDITO column = direction "in", DEBITO column = direction "out"
- Nu Debit (MXN, Debit): Deposits = direction "in", Gastos/withdrawals = direction "out"
- Nu Credit (MXN, Credit): Purchases = direction "out", payments to card = direction "in"
- Rappi Credit (MXN, Credit): Purchases = direction "out", payments to card = direction "in"
- Oro Banamex Credit (MXN, Credit): Purchases = direction "out", payments to card = direction "in"
- Costco Banamex Credit (MXN, Credit): Purchases = direction "out", payments to card = direction "in"
- HSBC 2Now Credit (MXN, Credit): Purchases = direction "out", payments to card = direction "in"
- DolarApp EURc (EUR): Compra EURc = direction "in" (currency = "EUR"); Venta EURc = direction "out" (currency = "EUR")
- DolarApp USDc (USD): Compra USDc = direction "in" (currency = "USD"); Venta USDc = direction "out" (currency = "USD")

CRITICAL DOLARAPP CURRENCY RULE:
- DolarApp USDc statements: ALL transactions → currency = "USD" (NEVER "EUR")
- DolarApp EURc statements: ALL transactions → currency = "EUR" (NEVER "USD")

DOLARAPP EXCHANGE RATE — CRITICAL:
DolarApp statements have a "Monto Local Equivalente" column that shows the MXN value of each
transaction. You MUST extract this MXN value as the "local_mxn" field.
Example: if Monto USDc = 475 and Monto Local Equivalente = 8500, then
  amount = 475, currency = "USD", local_mxn = 8500
Do NOT guess or use a generic exchange rate. Use the exact Monto Local Equivalente from the statement.

INSTRUCTIONS:
1. Identify the bank name and statement period (month/year).
2. Extract EVERY transaction row. Do NOT stop early. Process ALL pages to the end.
   Skip ONLY: cover pages, promotional content, legal disclaimers, amortization tables,
   fee summaries, opening/closing balance summary lines.
3. For each transaction, extract:
   - date: ISO format (YYYY-MM-DD)
   - description: exact raw text (preserve casing and punctuation)
   - amount: positive absolute value
   - currency: MXN | EUR | USD  (follow bank-specific rules above)
   - direction: "in" or "out"
   - exchange_rate: TC/tipo de cambio next to the transaction, or null
   - local_mxn: Monto Local Equivalente in MXN (DolarApp only), or null
   - notes: null unless it's a Rappi installment (see rule below)

4. For Mexican credit cards (Banamex, HSBC, Rappi, Nu Credit): all purchases are
   direction "out". Extract payment entries too (they will be ignored server-side).

5. For foreign-currency transactions in Mexican statements (Banamex, HSBC): use the
   TC field shown next to each transaction as exchange_rate.

6. RAPPI "COMPRAS A MESES" — CRITICAL:
   The "Compras a meses" section lists installment purchases separately.
   a) Use the "Mensualidad" column as amount (NOT "Monto original").
      E.g. Monto original=$12,000 / Mensualidad=$333.33 → use 333.33
   b) Extract installment number from "# de Mensualidad" column.
      E.g. "2 de 12" → notes = "Installment 2/12"
      E.g. "21 de 48" → notes = "Installment 21/48"
   c) direction = "out" for all installment rows.
   d) Output ONE transaction row per installment, using the Mensualidad amount.

7. COMPLETENESS IS MANDATORY: You MUST extract every single transaction on every page.
   If you reach the token limit before finishing, output what you have inside the JSON
   structure so it remains valid — do not truncate the JSON mid-stream.

8. NEVER hallucinate transactions. Only extract what is explicitly printed.

9. Return ONLY valid JSON with this structure — no markdown, no commentary:
{
  "bank_name": "string",
  "statement_period": {"month": integer, "year": integer},
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "description": "string",
      "amount": number,
      "currency": "MXN|EUR|USD",
      "direction": "in|out",
      "exchange_rate": number_or_null,
      "local_mxn": number_or_null,
      "notes": "string_or_null"
    }
  ]
}"""


def _chunk_prompt(bank_name: str, month: int, year: int,
                  currency_hint: str, page_start: int, page_end: int) -> str:
    """Prompt for secondary page chunks — shorter, context-injected."""
    return f"""Extract ALL transactions from pages {page_start}–{page_end} of a {bank_name} bank statement (period: {month}/{year}).

Currency for this bank: {currency_hint}
DolarApp USDc rule: if this is a DolarApp USDc statement, currency = "USD" and local_mxn = Monto Local Equivalente.
DolarApp EURc rule: if this is a DolarApp EURc statement, currency = "EUR" and local_mxn = Monto Local Equivalente.

Extract EVERY transaction row on these pages — do not stop early.
For Rappi "Compras a meses": use the Mensualidad amount, notes = "Installment N/M".
For Banamex/HSBC foreign transactions: include exchange_rate (TC value).

Return ONLY a JSON array of transaction objects. No wrapper object. No markdown.
Each object: {{ "date":"YYYY-MM-DD", "description":"...", "amount":number, "currency":"...",
               "direction":"in|out", "exchange_rate":number_or_null,
               "local_mxn":number_or_null, "notes":"string_or_null" }}"""


# ─────────────────────────────────────────────────────────────────────────────
# PDF utilities
# ─────────────────────────────────────────────────────────────────────────────

def _count_pages(pdf_bytes: bytes) -> int:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return len(reader.pages)


def _extract_page_range(pdf_bytes: bytes, start: int, end: int) -> bytes:
    """Return a new PDF containing pages [start, end) (0-indexed)."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    writer = pypdf.PdfWriter()
    for i in range(start, min(end, len(reader.pages))):
        writer.add_page(reader.pages[i])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _b64(pdf_bytes: bytes) -> str:
    return base64.standard_b64encode(pdf_bytes).decode("utf-8")


def _parse_json_response(text: str) -> dict | list:
    text = text.strip()
    # Strip markdown fences if present
    text = re.sub(r'^```[a-z]*\n?', '', text)
    text = re.sub(r'\n?```$', '', text)
    return json.loads(text)


# ─────────────────────────────────────────────────────────────────────────────
# Claude API helpers
# ─────────────────────────────────────────────────────────────────────────────

def _call_claude_full(client: anthropic.Anthropic, pdf_bytes: bytes) -> tuple[dict, str]:
    """Send the full PDF with the comprehensive extraction prompt. Returns (data, stop_reason)."""
    resp = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=MAX_TOKENS,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": _b64(pdf_bytes),
                    },
                },
                {"type": "text", "text": FULL_EXTRACTION_PROMPT},
            ],
        }],
    )
    raw = resp.content[0].text
    data = _parse_json_response(raw)
    return data, resp.stop_reason


def _call_claude_chunk(client: anthropic.Anthropic, chunk_bytes: bytes,
                       bank_name: str, month: int, year: int,
                       currency_hint: str, page_start: int, page_end: int) -> list:
    """Send a page chunk and return the list of raw transaction dicts."""
    prompt = _chunk_prompt(bank_name, month, year, currency_hint, page_start, page_end)
    resp = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=MAX_TOKENS,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": _b64(chunk_bytes),
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )
    raw = resp.content[0].text
    data = _parse_json_response(raw)
    if isinstance(data, list):
        return data
    # Claude sometimes wraps it anyway
    if isinstance(data, dict):
        return data.get("transactions", [])
    return []


# ─────────────────────────────────────────────────────────────────────────────
# Currency helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fix_currency_for_bank(currency: str, bank_name: str) -> str:
    """Force correct currency based on bank name (DolarApp USDc/EURc safeguard)."""
    b = bank_name.lower()
    if "usdc" in b:
        return "USD"
    if "eurc" in b:
        return "EUR"
    return currency


def _currency_hint(bank_name: str) -> str:
    b = bank_name.lower()
    if "usdc" in b:
        return "USD"
    if "eurc" in b or "millennium" in b or "revolut" in b:
        return "EUR"
    return "MXN"


# ─────────────────────────────────────────────────────────────────────────────
# Installment helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_installment(notes: str | None, description: str) -> str | None:
    """Return 'Installment N/M' string from notes or description, or None."""
    for text in [notes, description]:
        if not text:
            continue
        m = re.search(r'(\d+)\s+de\s+(\d+)', text, re.IGNORECASE)
        if m:
            return f"Installment {int(m.group(1))}/{int(m.group(2))}"
        m2 = re.search(r'[Ii]nstallment\s+(\d+)/(\d+)', text)
        if m2:
            return f"Installment {m2.group(1)}/{m2.group(2)}"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main transaction builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_transaction(tx: dict, bank_name: str,
                       statement_month: int, statement_year: int) -> dict | None:
    """
    Convert a raw extracted transaction dict into the final DB-ready dict.
    Returns None if the transaction should be skipped (bad data).
    """
    try:
        tx_date_str = tx.get("date", "")
        description = tx.get("description", "").strip()
        raw_amount = tx.get("amount", 0)
        currency = tx.get("currency", "MXN").upper()
        direction = tx.get("direction", "out")
        exchange_rate = tx.get("exchange_rate")
        local_mxn = tx.get("local_mxn")           # MXN equivalent from DolarApp statements
        extraction_notes = tx.get("notes")

        if not tx_date_str or not description or raw_amount is None:
            return None

        amount_original = Decimal(str(raw_amount))

        # Enforce correct currency based on bank name
        currency = _fix_currency_for_bank(currency, bank_name)

        # ── MXN conversion ───────────────────────────────────────────────
        is_dolarapp = "dolarapp" in bank_name.lower()

        if currency == "MXN":
            amount_mxn = amount_original
            rate = Decimal("1.0")

        elif is_dolarapp and local_mxn:
            # DolarApp: use Monto Local Equivalente directly — this IS the MXN amount
            amount_mxn = Decimal(str(local_mxn))
            rate = (amount_mxn / amount_original) if amount_original else Decimal("20.0")

        elif exchange_rate:
            rate = Decimal(str(exchange_rate))
            amount_mxn = amount_original * rate

        else:
            # Fallback market rates — used only when no TC is available
            fallback = {"EUR": Decimal("21.5"), "USD": Decimal("17.9")}
            rate = fallback.get(currency, Decimal("20.0"))
            amount_mxn = amount_original * rate

        # ── Installment note normalisation (Rappi) ───────────────────────
        is_rappi = "rappi" in bank_name.lower()
        if is_rappi:
            parsed = _parse_installment(extraction_notes, description)
            if parsed:
                extraction_notes = parsed

        # ── Classification ───────────────────────────────────────────────
        classification = classify(
            description=description,
            amount_mxn=amount_mxn,
            bank_name=bank_name,
            direction=direction,
            currency_original=currency,
        )

        # ── Special overrides from classifier ────────────────────────────

        # Almitas fixed EUR 600: ignore statement amount, always use EUR 600
        if classification.get("fixed_eur_amount"):
            fixed_eur = Decimal(str(classification["fixed_eur_amount"]))
            amount_original = fixed_eur
            currency = "EUR"
            if exchange_rate:
                rate = Decimal(str(exchange_rate))
            else:
                rate = Decimal("21.5")
            amount_mxn = amount_original * rate

        # Amount divisor (e.g. shared cleaning — ÷3)
        divisor = classification.get("amount_divisor")
        if divisor:
            amount_mxn = amount_mxn / Decimal(str(divisor))
            amount_original = amount_original / Decimal(str(divisor))

        # Description override
        final_description = classification.get("description_override") or description

        # Merge notes
        classifier_notes = classification.get("notes")
        notes_parts = [p for p in [classifier_notes, extraction_notes] if p]
        final_notes = " | ".join(notes_parts) if notes_parts else None

        # ── Parse date ───────────────────────────────────────────────────
        parts = tx_date_str.split("-")
        tx_date = _date(int(parts[0]), int(parts[1]), int(parts[2]))

        return {
            "date": tx_date,
            "description": final_description,
            "amount_original": float(amount_original),
            "currency_original": currency,
            "amount_mxn": float(amount_mxn),
            "exchange_rate_used": float(rate),
            "category": classification["category"],
            "type": classification["type"],
            "bank_name": bank_name,
            "month": tx_date.month,
            "year": tx_date.year,
            "manually_added": False,
            "notes": final_notes,
        }

    except Exception as e:
        print(f"[pdf_processor] Skipping transaction due to error: {e!r} | tx={tx}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def process_pdf(pdf_bytes: bytes) -> tuple[list[dict], str, int, int]:
    """
    Send PDF to Claude, extract transactions, classify them.
    For PDFs longer than PAGES_PER_CHUNK pages the PDF is split into chunks
    to avoid token-limit truncation that silently drops late-page transactions.

    Returns: (transactions_list, bank_name, statement_month, statement_year)
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    total_pages = _count_pages(pdf_bytes)
    print(f"[pdf_processor] PDF has {total_pages} pages")

    # ── Full-document pass (always done for page 1 to get bank name/period) ──
    first_chunk_end = min(PAGES_PER_CHUNK, total_pages)
    first_chunk_bytes = _extract_page_range(pdf_bytes, 0, first_chunk_end)

    if total_pages <= PAGES_PER_CHUNK:
        # Short PDF: send the whole thing in one call
        data, stop_reason = _call_claude_full(client, pdf_bytes)
        print(f"[pdf_processor] Single-pass stop_reason={stop_reason}")
    else:
        # Long PDF: first chunk with full prompt (gets bank_name + period)
        data, stop_reason = _call_claude_full(client, first_chunk_bytes)
        print(f"[pdf_processor] Chunk 1 (pages 1-{first_chunk_end}) stop_reason={stop_reason}")

    bank_name = data.get("bank_name", "Unknown")
    period = data.get("statement_period", {})
    statement_month = period.get("month", 1)
    statement_year = period.get("year", 2025)
    currency_hint = _currency_hint(bank_name)

    raw_transactions: list[dict] = list(data.get("transactions", []))
    print(f"[pdf_processor] Chunk 1: {len(raw_transactions)} raw transactions extracted")

    # ── Additional chunks for long PDFs ─────────────────────────────────────
    if total_pages > PAGES_PER_CHUNK:
        chunk_num = 2
        for chunk_start in range(PAGES_PER_CHUNK, total_pages, PAGES_PER_CHUNK):
            chunk_end = min(chunk_start + PAGES_PER_CHUNK, total_pages)
            chunk_bytes = _extract_page_range(pdf_bytes, chunk_start, chunk_end)
            print(f"[pdf_processor] Processing chunk {chunk_num} (pages {chunk_start+1}–{chunk_end})")
            chunk_txs = _call_claude_chunk(
                client, chunk_bytes,
                bank_name, statement_month, statement_year,
                currency_hint,
                page_start=chunk_start + 1,
                page_end=chunk_end,
            )
            print(f"[pdf_processor] Chunk {chunk_num}: {len(chunk_txs)} raw transactions")
            raw_transactions.extend(chunk_txs)
            chunk_num += 1

    print(f"[pdf_processor] Total raw transactions from all chunks: {len(raw_transactions)}")

    # ── Build & classify ─────────────────────────────────────────────────────
    results = []
    skipped = 0
    for tx in raw_transactions:
        built = _build_transaction(tx, bank_name, statement_month, statement_year)
        if built:
            results.append(built)
        else:
            skipped += 1

    print(f"[pdf_processor] Final: {len(results)} transactions built, {skipped} skipped")
    return results, bank_name, statement_month, statement_year
