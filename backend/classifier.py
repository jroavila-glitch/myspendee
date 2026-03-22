"""
Classification rules for transactions.
All matching is case-insensitive.
Rules are applied in order: IGNORE → INCOME → EXPENSE → fallback Other.

Return dict keys:
  type                  income / expense / ignored
  category              string
  notes                 string or None
  description_override  string or None  — replace raw description with this
  amount_divisor        int or None     — divide amount_mxn (and amount_original) by this
"""

import re
import unicodedata
from decimal import Decimal


def _norm(s: str) -> str:
    """Lowercase + strip accents so é/ê/è all match e, ó matches o, etc."""
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode("ascii")


def classify(description: str, amount_mxn: Decimal, bank_name: str,
             direction: str, currency_original: str) -> dict:
    desc = description.lower().strip()
    desc_norm = _norm(description)          # accent-stripped lowercase for matching
    amount = float(amount_mxn)
    bank = bank_name.lower()

    def result(type_, category, notes=None, desc_override=None, divisor=None, fixed_eur=None):
        return {
            "type": type_,
            "category": category,
            "notes": notes,
            "description_override": desc_override,
            "amount_divisor": divisor,
            "fixed_eur_amount": fixed_eur,   # override amount to this many EUR (Almitas rule)
        }

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
        # Any "pago a tu tarjeta de crédito / credito"
        "pago a tu tarjeta de cr",        # covers both é and e variants
        "sent from dolarapp",
        "patricia neira",
        "arturo pastrana",
        "international transfer to jose rodrigo avila neira",
        "exchanged to eur",
        "pago a tarjeta",
        "pago recibido",
        "pago por spei",
    ]
    for pattern in ignore_patterns:
        if pattern in desc or pattern in desc_norm:
            return result("ignored", "ignored", f"Auto-ignored: matched '{pattern}'")

    # Amazon $149 MXN → ignore
    if "amazon" in desc and abs(amount - 149.0) < 0.01:
        return result("ignored", "ignored", "Auto-ignored: Amazon $149 MXN")

    # DolarApp Venta USDc to self
    if "dolarapp" in bank and "venta usdc" in desc and "jose rodrigo avila neira" in desc:
        return result("ignored", "ignored", "Auto-ignored: DolarApp internal transfer")

    # DolarApp/EURc & USDc commissions → ignored
    commission_ignores = [
        "compra eurc comisi",   # covers comisión / comision
        "venta eurc comisi",
        "compra usdc comisi",
        "venta usdc comisi",
    ]
    for pat in commission_ignores:
        if pat in desc_norm:
            return result("ignored", "ignored", f"Auto-ignored: commission '{pat}'")

    # DIFERIMIENTO DE SALDO APP MOBILE → ignored
    if "diferimiento de saldo app mobile" in desc_norm:
        return result("ignored", "ignored", "Auto-ignored: Diferimiento de saldo app mobile")

    # Conversión USDc a EURc → ignored (internal wallet conversion)
    if "conversion usdc a eurc" in desc_norm or "conversión usdc a eurc" in desc:
        return result("ignored", "ignored", "Auto-ignored: USDc→EURc internal conversion")

    # TRF P/ Bridge Building → ignored (internal transfer)
    if "trf p/ bridge building" in desc_norm or "bridge building" in desc_norm:
        return result("ignored", "ignored", "Auto-ignored: Bridge Building transfer")

    # Credit card payment entries
    credit_payment_patterns = [
        "pago de tarjeta",
        "pago tarjeta credito",
        "credit card payment",
        "card payment",
    ]
    for pattern in credit_payment_patterns:
        if pattern in desc or pattern in desc_norm:
            return result("ignored", "ignored", f"Auto-ignored: credit card payment '{pattern}'")

    # ──────────────────────────────────────────────
    # 2. INCOME RULES
    # ──────────────────────────────────────────────

    if "contini solutions" in desc:
        return result("income", "Perenniam Agency")

    if "filip marek" in desc_norm:
        return result("income", "Tennis Lessons")

    # Rappi BONIFICACIÓN CON CASHBACK → specific description
    if ("bonificaci" in desc_norm and "cashback" in desc_norm) and "rappi" in bank:
        return result("income", "Credit Cards Cashback",
                      desc_override="RappiCard - BONIFICACIÓN CON CASHBACK")

    if "bonificaci" in desc_norm and "cashback" in desc_norm:
        return result("income", "Credit Cards Cashback")

    if "iva bonificaci" in desc_norm and "cashback" in desc_norm:
        return result("income", "Credit Cards Cashback")

    if "c combinator mexico" in desc or "honos" in desc:
        return result("income", "Other", "C Combinator / Honos deposit")

    # Revolut transfer from — Goncalo (shared rent/utilities) → Home, divide by 3
    if "revolut" in bank and "goncalo de campos melo" in desc_norm:
        return result("expense", "Home", "Shared rent/utilities — 1/3 of total", divisor=3)

    # Revolut transfer from (generic income)
    if "revolut" in bank and "transfer from" in desc:
        if amount <= 600:  # roughly ≤€30 at ~20 rate
            return result("income", "Tennis Smash & Social")
        else:
            return result("income", "Tennis Lessons")

    # Millennium BCP CREDITO entries
    if "millennium" in bank and direction == "in":
        if amount <= 600:
            return result("income", "Tennis Smash & Social")
        else:
            return result("income", "Tennis Lessons")

    # DolarApp Compra USDc from Contini
    if "dolarapp" in bank and "compra usdc" in desc and "contini" in desc_norm:
        return result("income", "Perenniam Agency")

    # DolarApp Compra EURc from Filip Marek
    if "dolarapp" in bank and "compra eurc" in desc and "filip marek" in desc_norm:
        return result("income", "Tennis Lessons")

    # DolarApp Compra EURc generic
    if "dolarapp" in bank and "compra eurc" in desc:
        return result("income", "Other", "DolarApp EURc purchase")

    # DolarApp Compra USDc generic
    if "dolarapp" in bank and "compra usdc" in desc:
        return result("income", "Other", "DolarApp USDc purchase")

    # ──────────────────────────────────────────────
    # 3. EXPENSE RULES
    # ──────────────────────────────────────────────

    # Almitas Inc Invest → Home (Rent), fixed EUR 600 (shared flat — always this amount)
    if "almitas inc invest" in desc_norm:
        return result("expense", "Home", "Rent — fixed EUR 600",
                      desc_override="Rent - " + description.strip(),
                      fixed_eur=600)

    # Transport
    if re.search(r'\bbolt\b|bolt\.eu', desc):
        return result("expense", "Transport")
    if re.search(r'\bubr\b', desc) or ("uber" in desc and "eats" not in desc and "one membershi" not in desc):
        return result("expense", "Transport")
    if "uber *one membershi" in desc or "uber*one membershi" in desc:
        return result("expense", "Transport")
    if re.search(r'\blime\b', desc):
        return result("expense", "Transport")

    # Food & Drink
    if "uber eats" in desc or "uber * eats" in desc or "uber*eats" in desc:
        return result("expense", "Food & Drink")

    food_keywords = [
        "fertonani cafe", "pizza", "pizzeria", "rc sanches", "pomme eatery",
        "shifu ramen", "jncquoi asia", "street chow", "temas medievais",
        "fauna e flora", "loja saldanha", "claudio francisco be",
        "ma duque loule", "enjoy value", "zhang yuemei",
        "nyxkvending", "nyx*kvending", "nyx kvending",
        "pandorca", "panorca",
    ]
    for kw in food_keywords:
        if kw in desc or kw in desc_norm:
            return result("expense", "Food & Drink")

    if "sumup *" in desc or "sumup*" in desc:
        return result("expense", "Food & Drink", "SumUp merchant")

    # Generic café/coffee shop catch — after specific keywords to avoid double-matching
    if re.search(r'\bcaf[eé]\b|\bcaff[eè]\b', desc, re.IGNORECASE) or \
       re.search(r'\bcaf[eé]\b|\bcaff[eè]\b', desc_norm, re.IGNORECASE):
        return result("expense", "Food & Drink")

    # Entertainment
    if "cinema" in desc or "uci cinemas" in desc:
        return result("expense", "Entertainment")
    if "netflix" in desc:
        return result("expense", "Entertainment")
    if "help.hbomax.com" in desc or "hbomax" in desc:
        return result("expense", "Entertainment")

    # IG Ro Project
    if "payu *google cloud" in desc or "payu*google cloud" in desc or "payu google cloud" in desc:
        return result("expense", "IG Ro Project")
    if "elevenlabs" in desc:
        return result("expense", "IG Ro Project")
    if "claude" in desc and "anthropic" in desc:
        return result("expense", "IG Ro Project")
    if re.search(r'\bclaude\b', desc) and "api" in desc:
        return result("expense", "IG Ro Project")
    if "google workspace" in desc or "google *workspace" in desc:
        return result("expense", "IG Ro Project")

    # Perenniam Agency (expense) — Calendly moved here from IG Ro Project
    if "calendly" in desc:
        return result("expense", "Perenniam Agency")

    # Apple.Com/Bill by amount — with description overrides
    if "apple.com/bill" in desc or "apple.com" in desc:
        apple_rules = {
            215: ("IG Ro Project",  "IG Verification - Servicio Apple.Com/Bill"),
            399: ("Personal Dev",   None),
            229: ("Phone/Tech",     "TextMe - Servicio Apple.Com/Bill"),
            179: ("Phone/Tech",     "iCloud - Servicio Apple.Com/Bill"),
            79:  ("Phone/Tech",     None),
            39:  ("Phone/Tech",     None),
        }
        for amt, (cat, desc_ov) in apple_rules.items():
            if abs(amount - amt) < 1.0:
                return result("expense", cat, "Apple subscription", desc_override=desc_ov)
        return result("expense", "Phone/Tech", "Apple subscription")

    # Perenniam Agency (expense)
    if "highlevel agency sub" in desc or "highlevel" in desc:
        return result("expense", "Perenniam Agency")
    if "paddle.net" in desc and ("elfsight" in desc):
        return result("expense", "Perenniam Agency")
    if "elfsight" in desc:
        return result("expense", "Perenniam Agency")

    # Phone/Tech
    if "vodafone" in desc:
        return result("expense", "Phone/Tech")
    if "telcel" in desc:
        return result("expense", "Phone/Tech")
    if "repair" in desc or "m.repair" in desc:
        return result("expense", "Phone/Tech")
    if "ishop mixup" in desc or "macstore forum" in desc:
        return result("expense", "Phone/Tech")
    if "t1 telcel" in desc or "telcel vps" in desc:
        return result("expense", "Phone/Tech")

    # MACSTORE CIB III → Phone/Tech + extract installment from description
    if "macstore cib" in desc_norm:
        # Try to extract installment pattern e.g. "001 de 036" or "001 DE 036"
        m = re.search(r'(\d+)\s+de\s+(\d+)', desc, re.IGNORECASE)
        install_note = None
        if m:
            current = int(m.group(1))
            total = int(m.group(2))
            install_note = f"Installment {current}/{total}"
        return result("expense", "Phone/Tech", install_note)

    # Groceries
    if "pagos fijos" in desc:
        return result("expense", "Groceries")
    if "diferimiento de saldo" in desc_norm:
        return result("expense", "Groceries")
    if "el corte ingles" in desc_norm or "el corte inglés" in desc:
        return result("expense", "Groceries")

    grocery_keywords = ["continente", "pingo doce", "celeiro", "gleba", "lidl"]
    for kw in grocery_keywords:
        if kw in desc or kw in desc_norm:
            return result("expense", "Groceries")

    # Home
    if "amazon" in desc or "amzn" in desc:
        return result("expense", "Home")

    # Cleaning — APARECIDA FERNANDA (any variant), shared cost ÷3
    if "aparecida fernanda" in desc_norm:
        return result("expense", "Home", "Cleaning — 1/3 share",
                      desc_override="Cleaning - " + description.strip(),
                      divisor=3)

    # Healthcare — Fernando Alves
    if "trf mb way p/ fernando alves" in desc_norm or "fernando alves" in desc_norm:
        return result("expense", "Healthcare", "Healthcare / pharmacy payment")

    # Brian — Inês Gardete Lemos (handles accented ê and plain e)
    if "ines gardete lemos" in desc_norm or "in\u00eas gardete lemos" in desc:
        return result("expense", "Home", "Brian — shared home expense",
                      desc_override="Brian - " + description.strip())

    # Tennis — Monsanto / Camara Lisboa (must come before generic tennis_keywords)
    if "camara lisboa" in desc_norm:
        return result("expense", "Tennis", None,
                      desc_override="Monsanto - " + description.strip())

    tennis_keywords = ["tennis shop", "decathlon", "clube internacional",
                       "tennis point", "tp* tennis-point"]
    for kw in tennis_keywords:
        if kw in desc or kw in desc_norm:
            return result("expense", "Tennis")

    # Gym
    if "club7" in desc or "clube vii" in desc_norm:
        return result("expense", "Gym")

    # Healthcare
    if "rituals" in desc:
        return result("expense", "Healthcare")

    # Bills/Fees
    bills_keywords = [
        "iva por intereses", "iva sobre comisiones", "iva interes",
        "interes exento", "interes gravable", "intereses",
        "com.man.conta pacote programa prestige", "imposto selo",
        "comision administracion tarjeta titular",
        "iva comision administracion",
        "comision cobrada",
        "iva comision cobrada",
    ]
    for kw in bills_keywords:
        if kw in desc or kw in desc_norm:
            return result("expense", "Bills/Fees")

    # Visa Portugal
    if "algarveknowhow" in desc or "www.algarveknowhow" in desc:
        return result("expense", "Visa Portugal")

    # Gifts
    if "hpy*help.io" in desc or "help.io" in desc:
        return result("expense", "Gifts")

    # Other
    if "fundednext" in desc:
        return result("expense", "Other")

    # ──────────────────────────────────────────────
    # 4. FALLBACK based on direction
    # ──────────────────────────────────────────────
    if direction == "in":
        return result("income", "Other", "Unclassified income — manual review needed")
    else:
        return result("expense", "Other", "Unclassified expense — manual review needed")
