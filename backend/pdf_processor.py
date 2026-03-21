"""
Processes PDF bank statements using Claude API (vision).
Returns a tuple: (list_of_transaction_dicts, bank_name, statement_month, statement_year)
"""

import base64
import json
import os
import re
from decimal import Decimal, InvalidOperation

import anthropic

from classifier import classify


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

EXTRACTION_PROMPT = """You are a financial data extraction assistant. Extract transactions from the provided bank statement PDF.

BANK ACCOUNTS AND THEIR LOGIC:
- Revolut (EUR, Debit): "Money in" = direction "in", "Money out" = direction "out"
- Millennium BCP (EUR, Debit): CREDITO column = direction "in", DEBITO column = direction "out"
- Nu Debit (MXN, Debit): Deposits = direction "in", Gastos/withdrawals = direction "out"
- Nu Credit (MXN, Credit): Purchases = direction "out", payments to card = direction "in"
- Rappi Credit (MXN, Credit): Purchases = direction "out", payments to card = direction "in"
- Oro Banamex Credit (MXN, Credit): Purchases = direction "out", payments to card = direction "in"
- Costco Banamex Credit (MXN, Credit): Purchases = direction "out", payments to card = direction "in"
- HSBC 2Now Credit (MXN, Credit): Purchases = direction "out", payments to card = direction "in"
- DolarApp EURc (EUR, Debit): Compra EURc = direction "in"; Venta EURc = direction "out"
- DolarApp USDc (USD, Debit): Compra USDc = direction "in"; Venta USDc = direction "out"

INSTRUCTIONS:
1. Identify the bank name and statement period (month/year).
2. Extract ONLY transaction rows. Skip: cover pages, promotional content, legal disclaimers, amortization tables, fee summaries, opening/closing balance lines.
3. For each transaction extract:
   - date: ISO format (YYYY-MM-DD)
   - description: exact raw text from the statement (preserve original casing and punctuation)
   - amount: positive number (absolute value)
   - currency: the currency of the amount (MXN, EUR, USD)
   - direction: "in" (money received/credited) or "out" (money spent/debited)
   - exchange_rate: if the statement shows a TC (tipo de cambio) or exchange rate next to the transaction, include it; otherwise null
   - notes: optional extra info — use this for installment info (see Rappi rule below)

4. For Mexican credit cards (Banamex, HSBC, Rappi, Nu Credit): purchases are always direction "out". Payment entries like "SU PAGO GRACIAS" or "PAGO INTERBANCARIO" should be extracted with direction "in".

5. For foreign currency transactions in Mexican bank statements (Banamex, HSBC), use the TC field shown next to the transaction for exchange_rate.

6. RAPPI "COMPRAS A MESES" (installment purchases) — CRITICAL RULE:
   Rappi statements contain a section called "Compras a meses" listing installment purchases.
   - Do NOT use the "Monto original" column for the amount.
   - Instead use the "Mensualidad" column (the monthly installment amount).
   - Extract the installment number from the "# de Mensualidad" column (e.g. "2 de 12" means payment 2 of 12).
   - Set notes = "Installment 2/12" (replace numbers with the actual values from the statement).
   - Set direction = "out" for all installment entries.

7. IGNORE classification is handled server-side — still extract ALL transactions including payments, internal transfers, etc.

8. NEVER invent or hallucinate transactions. Only extract what is explicitly printed on the page.

9. Return ONLY a valid JSON object with this exact structure:

{
  "bank_name": "string — exact bank name from the statement",
  "statement_period": {"month": integer, "year": integer},
  "transactions": [
    {
      "date": "YYYY-MM-DD",
      "description": "raw description text",
      "amount": number,
      "currency": "MXN|EUR|USD",
      "direction": "in|out",
      "exchange_rate": number or null,
      "notes": "string or null"
    }
  ]
}

Return ONLY the JSON. No explanations, no markdown, no code blocks.
"""


def encode_pdf(pdf_bytes: bytes) -> str:
    return base64.standard_b64encode(pdf_bytes).decode("utf-8")


def extract_json(text: str) -> dict:
    """Extract JSON from Claude response, handling possible markdown wrapping."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def process_pdf(pdf_bytes: bytes) -> tuple[list[dict], str, int, int]:
    """
    Send PDF to Claude, extract transactions, apply classification.
    Returns: (transactions_list, bank_name, statement_month, statement_year)
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    pdf_b64 = encode_pdf(pdf_bytes)

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=8000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": EXTRACTION_PROMPT,
                    },
                ],
            }
        ],
    )

    raw_text = response.content[0].text
    data = extract_json(raw_text)

    bank_name = data.get("bank_name", "Unknown")
    period = data.get("statement_period", {})
    statement_month = period.get("month", 1)
    statement_year = period.get("year", 2025)

    results = []
    for tx in data.get("transactions", []):
        try:
            tx_date_str = tx.get("date", "")
            description = tx.get("description", "").strip()
            raw_amount = tx.get("amount", 0)
            currency = tx.get("currency", "MXN").upper()
            direction = tx.get("direction", "out")
            exchange_rate = tx.get("exchange_rate")
            extraction_notes = tx.get("notes")  # e.g. "Installment 2/12" from Rappi

            if not tx_date_str or not description or raw_amount is None:
                continue

            amount_original = Decimal(str(raw_amount))

            # Convert to MXN
            if currency == "MXN":
                amount_mxn = amount_original
                rate = Decimal("1.0")
            elif exchange_rate:
                rate = Decimal(str(exchange_rate))
                amount_mxn = amount_original * rate
            else:
                fallback = {"EUR": Decimal("21.5"), "USD": Decimal("20.0")}
                rate = fallback.get(currency, Decimal("20.0"))
                amount_mxn = amount_original * rate

            # Classify
            classification = classify(
                description=description,
                amount_mxn=amount_mxn,
                bank_name=bank_name,
                direction=direction,
                currency_original=currency,
            )

            # Apply amount divisor (e.g. shared rent → ÷3)
            divisor = classification.get("amount_divisor")
            if divisor:
                amount_mxn = amount_mxn / Decimal(str(divisor))
                amount_original = amount_original / Decimal(str(divisor))

            # Apply description override
            final_description = classification.get("description_override") or description

            # Merge notes: classifier notes + extraction notes (installment info)
            classifier_notes = classification.get("notes")
            notes_parts = [p for p in [classifier_notes, extraction_notes] if p]
            final_notes = " | ".join(notes_parts) if notes_parts else None

            # Parse date
            from datetime import date as date_type
            parts = tx_date_str.split("-")
            tx_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))

            results.append({
                "date": tx_date,
                "description": final_description,
                "amount_original": float(amount_original),
                "currency_original": currency,
                "amount_mxn": float(amount_mxn),
                "exchange_rate_used": float(rate) if rate else None,
                "category": classification["category"],
                "type": classification["type"],
                "bank_name": bank_name,
                "month": tx_date.month,
                "year": tx_date.year,
                "manually_added": False,
                "notes": final_notes,
            })
        except Exception as e:
            print(f"[pdf_processor] Skipping transaction due to error: {e} | tx={tx}")
            continue

    return results, bank_name, statement_month, statement_year
