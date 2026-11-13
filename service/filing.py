"""The filing step shared by the eval endpoint (/v1/file) and the signed-in Captures API:
one model call, a schema check, and one retry on output that breaks the schema."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from dumpit_ops.schema import shape_problems

from .model import Model, ModelOutputError, ProviderError


class ProviderUnavailable(Exception):
    """The model provider could not be reached or refused the request (503)."""


class SchemaFailure(Exception):
    """The model's output broke the op schema twice (502)."""


@dataclass
class Proposal:
    ops: List[Dict[str, Any]]
    input_tokens: int
    output_tokens: int


def propose(model: Model, request: Dict[str, Any], on_usage=None) -> Proposal:
    """`on_usage(input_tokens, output_tokens)` is called for every reply, including a
    rejected first one, so spend is counted even when the batch is thrown away."""
    tokens_in = tokens_out = 0
    for _ in range(2):
        try:
            reply = model.propose(request)
        except ProviderError as exc:
            raise ProviderUnavailable(str(exc)) from exc
        except ModelOutputError:
            continue
        tokens_in += reply.input_tokens
        tokens_out += reply.output_tokens
        if on_usage:
            on_usage(reply.input_tokens, reply.output_tokens)
        if not shape_problems(reply.ops):
            return Proposal(reply.ops, tokens_in, tokens_out)
    raise SchemaFailure("model output failed the schema check twice")
