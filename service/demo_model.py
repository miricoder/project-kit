"""A small rule-based stand-in for the filing model, for trying the app without an
Anthropic API key (DUMPIT_MODEL=demo). It is NOT the product's filer: it understands only a
few simple shapes ("paid 42 for groceries", "coffee 3.50", "my budget is 1400 a month",
"book the car service", "that was 24 not 42", "X and Y") and files anything else as a note.
The app labels itself "demo filer" while it is in use.
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Dict, List

from .model import ModelReply

NAME = "demo"
CATEGORY_WORDS = {
    "Groceries": ("grocer", "supermarket", "lidl", "aldi", "rewe", "tesco", "food shop"),
    "Eating out": ("coffee", "lunch", "dinner", "breakfast", "pizza", "restaurant", "drinks",
                   "beer", "takeaway", "cafe"),
    "Transport": ("uber", "taxi", "bus", "train", "metro", "petrol", "fuel", "parking", "tram"),
    "Housing": ("rent", "ikea", "mortgage"),
    "Bills": ("bill", "electric", "internet", "phone", "water", "gas", "spotify", "netflix"),
    "Health": ("pharmacy", "doctor", "dentist", "physio", "gym"),
    "Shopping": ("shoes", "clothes", "jacket", "book", "gift", "present", "amazon"),
    "Fun": ("cinema", "concert", "museum", "tickets", "game"),
    "Travel": ("hotel", "flight", "hostel", "airbnb"),
}
AMOUNT = r"(\d+(?:[.,]\d{1,2})?)"


def _cents(text: str) -> int:
    return round(float(text.replace(",", ".")) * 100)


def _category(words: str) -> str:
    lowered = words.lower()
    for category, keys in CATEGORY_WORDS.items():
        if any(k in lowered for k in keys):
            return category
    return "Other"


def _one(part: str, today: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    text = part.strip().rstrip(".!")
    low = text.lower()
    if not text:
        return []
    m = re.match(rf"(?:my )?(?:monthly )?budget (?:is |of |to )?€?{AMOUNT}(k)?", low)
    if m:
        cents = _cents(m.group(1)) * (1000 if m.group(2) else 1)
        return [{"op": "set_monthly_budget", "amount_cents": cents}]
    m = re.match(rf"(?:that|it) was €?{AMOUNT} not €?{AMOUNT}", low)
    if m:
        old = _cents(m.group(2))
        for e in reversed(context.get("expenses") or []):
            if e["amount_cents"] == old:
                return [{"op": "update", "ref": e["ref"], "set": {"amount_cents": _cents(m.group(1))}}]
        return [{"op": "note", "text": text, "suggestions": []}]
    m = re.match(rf"(?:paid|spent) €?{AMOUNT}(?: euros?)? (?:for|on|at) (.+)", low) or \
        re.match(rf"(.+?) €?{AMOUNT}(?: euros?)?$", low)
    if m:
        amount, what = (m.group(1), m.group(2)) if low.startswith(("paid", "spent")) \
            else (m.group(2), m.group(1))
        what = re.sub(r"^(?:paid|spent)\s+", "", what).strip() or "Expense"
        return [{"op": "create_expense", "amount_cents": _cents(amount), "date": today,
                 "category": _category(what), "description": what.capitalize()}]
    if re.match(r"(?:remind me to |todo:? |need to )?(?:book|call|buy|pay|send|pick up|email|"
                r"renew|fix|clean|order|return|write|check|cancel|get|make)\b", low):
        title = re.sub(r"^(?:remind me to |todo:? |need to )", "", text, flags=re.I)
        return [{"op": "create_task", "title": title[:1].upper() + title[1:]}]
    return [{"op": "note", "text": text, "suggestions": []}]


class DemoModel:
    name = NAME

    def propose(self, request: Dict[str, Any]) -> ModelReply:
        today = str(request["captured_at"])[:10]
        date.fromisoformat(today)
        context = request.get("context") or {}
        parts = re.split(r"\s+and\s+", request["text"].strip(), flags=re.I)
        ops: List[Dict[str, Any]] = []
        for part in parts:
            ops += _one(part, today, context)
        if any(op["op"] == "note" for op in ops):
            ops = [{"op": "note", "text": request["text"], "suggestions": []}]
        tokens = len(json.dumps(request)) // 4
        return ModelReply(ops, tokens, 50)
