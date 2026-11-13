"""Dumpit filing service: turns one capture into a proposed op list.

It holds the model key and the limits, and nothing else: no user data, no capture text in
logs. The phone validates and applies the ops (docs/spec.md, "Interfaces").

    uvicorn service.app:app
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections import Counter
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from .filing import ProviderUnavailable, SchemaFailure, propose
from .limits import Limits, token_hash
from .model import PROMPT_VERSION, AnthropicModel, Model

MAX_TEXT = 4000
log = logging.getLogger("dumpit.service")


class FileRequest(BaseModel):
    capture_id: str
    text: str
    source: Literal["typed", "paste"]
    captured_at: str
    tz: str
    currency: Literal["EUR"] = "EUR"
    context: Dict[str, Any] = {}


def _error(status: int, message: str, headers: Optional[Dict[str, str]] = None) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status, headers=headers)


def _bearer(request: Request) -> Optional[str]:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def create_app(model: Optional[Model] = None, limits: Optional[Limits] = None,
               eur_per_mtok_in: Optional[float] = None,
               eur_per_mtok_out: Optional[float] = None) -> FastAPI:
    app = FastAPI(title="Dumpit filing service")
    # Rates in euros per million tokens. The defaults are Claude Haiku 5.5's dollar prices
    # taken as euros, which overstates the cost a little: the cap trips early, not late.
    rate_in = eur_per_mtok_in if eur_per_mtok_in is not None \
        else float(os.environ.get("DUMPIT_EUR_PER_MTOK_IN", "0.10"))
    rate_out = eur_per_mtok_out if eur_per_mtok_out is not None \
        else float(os.environ.get("DUMPIT_EUR_PER_MTOK_OUT", "0.50"))
    app.state.limits = limits or Limits(
        os.environ.get("DUMPIT_DB", ":memory:"),
        int(os.environ.get("DUMPIT_PER_INSTALL_DAILY", "200")),
        float(os.environ.get("DUMPIT_DAILY_CAP_EUR", "2.0")))
    app.state.model = model

    def current_model() -> Model:
        if app.state.model is None:            # built lazily so tests never need a key
            app.state.model = AnthropicModel()
        return app.state.model

    @app.get("/v1/health")
    def health() -> Dict[str, Any]:
        name = app.state.model.name if app.state.model else \
            os.environ.get("DUMPIT_MODEL", "claude-haiku-5-5")
        return {"status": "ok", "prompt_version": PROMPT_VERSION, "model": name}

    @app.post("/v1/install", status_code=201)
    def install() -> Dict[str, str]:
        return {"install_token": app.state.limits.issue()}

    @app.post("/v1/file")
    async def file(request: Request) -> JSONResponse:
        started, request_id = time.monotonic(), uuid.uuid4().hex[:12]
        limits: Limits = app.state.limits
        token = _bearer(request)
        ops_kinds: Counter = Counter()
        usage = {"input_tokens": 0, "output_tokens": 0}

        def done(response: JSONResponse) -> JSONResponse:
            # Never the text, context, amounts or model output.
            log.info(json.dumps({
                "request_id": request_id,
                "install": token_hash(token)[:8] if token else None,
                "status": response.status_code,
                "latency_ms": round((time.monotonic() - started) * 1000),
                **usage, "ops": dict(ops_kinds), "prompt_version": PROMPT_VERSION}))
            return response

        if not limits.known(token):
            return done(_error(401, "unknown install token"))
        try:
            body = FileRequest.model_validate(json.loads(await request.body()))
        except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
            return done(_error(400, "malformed request"))
        if len(body.text) > MAX_TEXT:
            return done(_error(413, f"text is over {MAX_TEXT} characters"))
        if limits.over_spend_cap():
            return done(_error(503, "daily spend cap reached"))
        if not limits.take_capture(token):
            return done(_error(429, "daily capture limit reached",
                               {"Retry-After": str(limits.seconds_to_reset())}))

        model = current_model()

        def count(tokens_in: int, tokens_out: int) -> None:
            usage["input_tokens"] += tokens_in
            usage["output_tokens"] += tokens_out
            limits.add_spend(round(tokens_in * rate_in + tokens_out * rate_out))

        try:
            ops = propose(model, body.model_dump(), on_usage=count).ops
        except ProviderUnavailable:
            return done(_error(503, "model provider unavailable"))
        except SchemaFailure:
            return done(_error(502, "model output failed the schema check twice"))

        ops_kinds.update(op["op"] for op in ops)
        return done(JSONResponse({
            "capture_id": body.capture_id, "prompt_version": PROMPT_VERSION,
            "model": model.name, "ops": ops, "usage": usage}))

    return app


app = create_app()
