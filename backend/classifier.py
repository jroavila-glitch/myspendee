"""
Classification rules for transactions.
All matching is case-insensitive.
Rules are applied in order: IGNORE → INCOME → EXPENSE → fallback Other.
"""

import re
from decimal import Decimal


def classify(description: str, amount_mxn: Decimal, bank_name: str,
             direction: str, currency_original: str) -> dict:
    """
    Returns dict with keys: type (income/expense/ignored), category, notes
    direction: 'in' or 'out' (money in = income side, money out = expense side)
    """
    desc = description.lower().strip()
    amount = float(amount_mxn)
    bank = bank_name.lower()

    # ──────────────────────────────────────────────
    # 1. IGNORE RULES
    # ──────────────────────────────────────────────
    ignore_patterns = [
        "macstore merida",
        "pago interbancario",
        "pay pal*adobe",
        "su pago gracias",
        "sebastian wohler",
        "paul pitterlein",
        "jose rodrigo avila neira",
        "pago a tu tarjeta de crédito nu",
        "pago a tu tarjeta de credito nu",
        "sent from dolarapp",
        "patricia neira",
        "arturo pastrana",
        "international transfer to jose rodrigo avila neira",
        "exchanged to eur",
        "pago a tarjeta",
        "pago recibido",
    ]
    for pattern in ignore_patterns:
        if pattern in desc:
            return {"type": "ignored", "category": "ignored", "notes": f"Auto-ignored: matched '{pattern}'"}

    # Amazon $149 MXN → ignore
    if "amazon" in desc and abs(amount - 149.0) < 0.01:
        return {"type": "ignored", "category": "ignored", "notes": "Auto-ignored: Amazon $149 MXN"}

    # DolarApp Venta USDc to self
    if "dolarapp" in bank and "venta usdc" in desc and "jose rodrigo avila neira" in desc:
        return {"type": "ignored", "category": "ignored", "notes": "Auto-ignored: DolarApp internal transfer"}

    # Credit card payments
    credit_payment_patterns = [
        "pago de tarjeta",
        "pago tarjeta credito",
        "credit card payment",
        "card payment",
    ]
    for pattern in credit_payment_patterns:
        if pattern in desc:
            return {"type": "ignored", "category": "ignored", "notes": f"Auto-ignored: credit card payment '{pattern}'"}

    # ──────────────────────────────────────────────
    # 2. INCOME RULES
    # ──────────────────────────────────────────────
    if "contini solutions" in desc:
        return {"type": "income", "category": "Perenniam Agency", "notes": None}

    if "filip marek" in desc:
        return {"type": "income", "category": "Tennis Lessons", "notes": None}

    if "bonificación con cashback" in desc or "bonificacion con cashback" in desc:
        return {"type": "income", "category": "Credit Cards Cashback", "notes": None}

    if "iva bonificación con cashback" in desc or "iva bonificacion con cashback" in desc:
        return {"type": "income", "category": "Credit Cards Cashback", "notes": None}

    if "c combinator mexico" in desc or "honos" in desc:
        return {"type": "income", "category": "Other", "notes": "C Combinator / Honos deposit"}

    # Revolut transfer from
    if "revolut" in bank and "transfer from" in desc:
        if amount <= 600:  # roughly ≤€30 at ~20 rate
            return {"type": "income", "category": "Tennis Smash & Social", "notes": None}
        else:
            return {"type": "income", "category": "Tennis Lessons", "notes": None}

    # Millennium BCP CREDITO entries
    if "millennium" in bank and direction == "in":
        if amount <= 600:
            return {"type": "income", "category": "Tennis Smash & Social", "notes": None}
        else:
            return {"type": "income", "category": "Tennis Lessons", "notes": None}

    # DolarApp Compra USDc from Contini
    if "dolarapp" in bank and "compra usdc" in desc and "contini" in desc:
        return {"type": "income", "category": "Perenniam Agency", "notes": None}

    # DolarApp Compra EURc from Filip Marek
    if "dolarapp" in bank and "compra eurc" in desc and "filip marek" in desc:
        return {"type": "income", "category": "Tennis Lessons", "notes": None}

    # DolarApp Compra EURc generic
    if "dolarapp" in bank and "compra eurc" in desc:
        return {"type": "income", "category": "Other", "notes": "DolarApp EURc purchase"}

    # DolarApp Compra USDc generic
    if "dolarapp" in bank and "compra usdc" in desc:
        return {"type": "income", "category": "Other", "notes": "DolarApp USDc purchase"}

    # ──────────────────────────────────────────────
    # 3. EXPENSE RULES
    # ──────────────────────────────────────────────

    # DolarApp Venta commission
    if "venta eurc comisión" in desc or "venta eurc comision" in desc:
        return {"type": "expense", "category": "Bills/Fees", "notes": None}
    if "compra eurc comisión" in desc or "compra eurc comision" in desc:
        return {"type": "expense", "category": "Bills/Fees", "notes": None}
    if "compra usdc comisión" in desc or "compra usdc comision" in desc:
        return {"type": "expense", "category": "Bills/Fees", "notes": None}

    # Transport
    if re.search(r'\bbolt\b|bolt\.eu', desc):
        return {"type": "expense", "category": "Transport", "notes": None}
    if re.search(r'\bubr\b', desc) or ("uber" in desc and "eats" not in desc and "one membershi" not in desc):
        return {"type": "expense", "category": "Transport", "notes": None}
    if "uber *one membershi" in desc or "uber*one membershi" in desc:
        return {"type": "expense", "category": "Transport", "notes": None}
    if re.search(r'\blime\b', desc):
        return {"type": "expense", "category": "Transport", "notes": None}

    # Food & Drink
    if "uber eats" in desc or "uber * eats" in desc or "uber*eats" in desc:
        return {"type": "expense", "category": "Food & Drink", "notes": None}

    food_keywords = [
        "fertonani cafe", "pizza", "pizzeria", "rc sanches", "pomme eatery",
        "shifu ramen", "jncquoi asia", "street chow", "temas medievais",
        "fauna e flora", "loja saldanha", "claudio francisco be",
        "ma duque loule", "enjoy value", "zhang yuemei",
    ]
    for kw in food_keywords:
        if kw in desc:
            return {"type": "expense", "category": "Food & Drink", "notes": None}

    if "sumup *" in desc:
        return {"type": "expense", "category": "Food & Drink", "notes": "SumUp merchant"}

    # Entertainment
    if "cinema" in desc or "uci cinemas" in desc:
        return {"type": "expense", "category": "Entertainment", "notes": None}
    if "netflix" in desc:
        return {"type": "expense", "category": "Entertainment", "notes": None}
    if "help.hbomax.com" in desc or "hbomax" in desc:
        return {"type": "expense", "category": "Entertainment", "notes": None}

    # IG Ro Project
    if "payu *google cloud" in desc or "payu*google cloud" in desc or "payu google cloud" in desc:
        return {"type": "expense", "category": "IG Ro Project", "notes": None}
    if "elevenlabs" in desc:
        return {"type": "expense", "category": "IG Ro Project", "notes": None}
    if "claude" in desc and "anthropic" in desc:
        return {"type": "expense", "category": "IG Ro Project", "notes": None}
    if re.search(r'\bclaude\b', desc) and "api" in desc:
        return {"type": "expense", "category": "IG Ro Project", "notes": None}
    if "google workspace" in desc or "google *workspace" in desc:
        return {"type": "expense", "category": "IG Ro Project", "notes": None}
    if "paddle.net* elfsight" in desc or "elfsight" in desc:
        return {"type": "expense", "category": "IG Ro Project", "notes": None}
    if "calendly" in desc:
        return {"type": "expense", "category": "IG Ro Project", "notes": None}

    # Perenniam Agency (expense)
    if "highlevel agency sub" in desc or "highlevel" in desc:
        return {"type": "expense", "category": "Perenniam Agency", "notes": None}

    # Phone/Tech
    if "vodafone" in desc:
        return {"type": "expense", "category": "Phone/Tech", "notes": None}
    if "telcel" in desc:
        return {"type": "expense", "category": "Phone/Tech", "notes": None}
    if "repair" in desc or "m.repair" in desc:
        return {"type": "expense", "category": "Phone/Tech", "notes": None}
    if "ishop mixup" in desc or "macstore forum" in desc:
        return {"type": "expense", "category": "Phone/Tech", "notes": None}
    if "t1 telcel" in desc or "telcel vps" in desc:
        return {"type": "expense", "category": "Phone/Tech", "notes": None}

    # Apple.Com/Bill by amount
    if "apple.com/bill" in desc or "apple.com" in desc:
        apple_rules = {399: "Personal Dev", 229: "Phone/Tech", 179: "Phone/Tech",
                       215: "IG Ro Project", 79: "Phone/Tech", 39: "Phone/Tech"}
        for amt, cat in apple_rules.items():
            if abs(amount - amt) < 1.0:
                return {"type": "expense", "category": cat, "notes": f"Apple subscription"}
        return {"type": "expense", "category": "Phone/Tech", "notes": "Apple subscription"}

    # Groceries
    if "pagos fijos" in desc:
        return {"type": "expense", "category": "Groceries", "notes": None}
    if "diferimiento de saldo" in desc:
        return {"type": "expense", "category": "Groceries", "notes": None}

    grocery_keywords = ["continente", "pingo doce", "celeiro", "gleba"]
    for kw in grocery_keywords:
        if kw in desc:
            return {"type": "expense", "category": "Groceries", "notes": None}

    # Home
    if "amazon" in desc or "amzn" in desc:
        return {"type": "expense", "category": "Home", "notes": None}
    if "almitas inc invest" in desc:
        return {"type": "expense", "category": "Home", "notes": "DolarApp Venta EURc"}
    if "trf p/ aparecida fernanda silva" in desc:
        return {"type": "expense", "category": "Home", "notes": "Cleaning service"}
    if "trf mb way p/ fernando alves" in desc:
        return {"type": "expense", "category": "Home", "notes": "Utility payment"}

    # Tennis
    tennis_keywords = ["tennis shop", "decathlon", "clube internacional",
                       "camara lisboa", "tennis point", "tp* tennis-point"]
    for kw in tennis_keywords:
        if kw in desc:
            return {"type": "expense", "category": "Tennis", "notes": None}

    # Gym
    if "club7" in desc or "clube vii" in desc:
        return {"type": "expense", "category": "Gym", "notes": None}

    # Healthcare
    if "rituals" in desc:
        return {"type": "expense", "category": "Healthcare", "notes": None}

    # Bills/Fees
    bills_keywords = [
        "iva por intereses", "iva sobre comisiones", "iva interes",
        "interes exento", "interes gravable", "intereses",
        "com.man.conta pacote programa prestige", "imposto selo",
    ]
    for kw in bills_keywords:
        if kw in desc:
            return {"type": "expense", "category": "Bills/Fees", "notes": None}

    # Visa Portugal
    if "algarveknowhow" in desc or "www.algarveknowhow" in desc:
        return {"type": "expense", "category": "Visa Portugal", "notes": None}

    # Gifts
    if "hpy*help.io" in desc or "help.io" in desc:
        return {"type": "expense", "category": "Gifts", "notes": None}

    # Other
    if "fundednext" in desc:
        return {"type": "expense", "category": "Other", "notes": None}
    if "nyx*kvending" in desc:
        return {"type": "expense", "category": "Other", "notes": None}
    if "trf p/ bridge building" in desc:
        return {"type": "expense", "category": "Other", "notes": None}

    # ──────────────────────────────────────────────
    # 4. FALLBACK based on direction
    # ──────────────────────────────────────────────
    if direction == "in":
        return {"type": "income", "category": "Other", "notes": "Unclassified income — manual review needed"}
    else:
        return {"type": "expense", "category": "Other", "notes": "Unclassified expense — manual review needed"}
