"""
Processes PDF bank statements using Claude API (vision).
Returns a list of raw transaction dicts for further classification.
"""

import base64
import json
import os
import re
from decimal import Decimal, InvalidOperation

import anthropic

from classifier import classify


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

EXTRACTION_PROMPT = """You are a financial data extraction assistant. Your job is to extract transactions from bank statements.

BANK ACCOUNTS AND THEIR LOGIC:
- Revolut (EUR, Debit): "Money in" = income direction, "Money out" = expense direction
- Millennium BCP (EUR, Debit): CREDITO column = income direction, DEBITO column = expense direction
- Nu Debit (MXN, Debit): Deposits = income direction, Gastos/withdrawals = expense direction
- Nu Credit (MXN, Credit): Purchases = expense direction, payments to card = ignore
- Rappi Credit (MXN, Credit): Purchases = expense direction, payments to card = ignore
- Oro Banamex Credit (MXN, Credit): Purchases = expense direction, payments to card = ignore
- Costco Banamex Credit (MXN, Credit): Purchases = expense direction, payments to card = ignore
- HSBC 2Now Credit (MXN, Credit): Purchases = expense direction, payments to card = ignore
- DolarApp EURc (EUR, Debit): Compra EURc = income direction; Venta EURc = check description
- DolarApp USDc (USD, Debit): Compra USDc = income direction; Venta USDc = check description

INSTRUCTIONS:
1. First identify the bank name and statement period (month/year).
2. Extract ONLY transaction rows. Ignore: cover pages, promotional content, legal disclaimers, amortization tables, fee summaries, balance summaries.
3. For each transaction extract:
   - date: ISO format (YYYY-MM-DD)
   - description: exact raw text from the statement
   - amount: positive number (absolute value)
   - currency: the currency of the amount (MXN, EUR, USD)
   - direction: "in" (money received/credited) or "out" (money spent/debited)
   - exchange_rate: if the statement shows a TC (tipo de cambio) or exchange rate next to the transaction, include it as a number; otherwise null
4. For Mexican credit cards (Banamex, HSBC, Rappi, Nu Credit): purchases are always "out". Payments like "SU PAGO GRACIAS" or "PAGO INTERBANCARIO" should still be extracted with direction="in" (we will handle ignore logic separately).
5. For foreign currency transactions in Mexican bank statements (Banamex, HSBC), use the TC field shown next to the transaction for exchange_rate.
6. NEVER invent or hallucinate transactions. Only extract what is explicitly on the page.
7. Return ONLY a valid JSON object with this exact structure:

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
      "exchange_rate": number or null
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
    # Remove markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return json.loads(text)


def process_pdf(pdf_bytes: bytes) -> list[dict]:
    """
    Send PDF to Claude, extract transactions, apply classification.
    Returns list of dicts ready for DB insertion.
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    pdf_b64 = encode_pdf(pdf_bytes)

    response = client.messages.create(
        model="claude-opus-4-6",
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
                # Use approximate fallback rates
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

            # Parse date
            from datetime import date as date_type
            parts = tx_date_str.split("-")
            tx_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))

            results.append({
                "date": tx_date,
                "description": description,
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
                "notes": classification.get("notes"),
            })
        except Exception as e:
            # Log and skip malformed transactions
            print(f"[pdf_processor] Skipping transaction due to error: {e} | tx={tx}")
            continue

    return results
