"""The model's output schema and its conversion to canonical ops."""
import json
from types import SimpleNamespace

import pytest

from dumpit_ops.schema import shape_problems
from service.model import (OUTPUT_SCHEMA, AnthropicModel, ModelOutputError, from_model)


def nulls(**fields):
    keys = ["ref", "title", "due_date", "due_time", "amount_cents", "date", "category",
            "description", "trip_ref", "name", "start_date", "end_date", "budget_cents",
            "text"]
    return {**{k: None for k in keys}, **fields}


def walk(schema):
    yield schema
    for value in schema.get("properties", {}).values():
        yield from walk(value)
    if isinstance(schema.get("items"), dict):
        yield from walk(schema["items"])


def test_every_object_in_the_output_schema_is_closed_and_fully_required():
    for node in walk(OUTPUT_SCHEMA):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])


def test_flat_ops_become_canonical_ops():
    flat = [
        nulls(op="create_expense", amount_cents=4200, date="2026-02-23",
              category="Groceries", description="groceries", suggestions=None),
        nulls(op="update", ref="t1", due_date="2026-02-27", suggestions=None),
        nulls(op="note", text="the thing with Marta", suggestions=[
            {"label": "Task: Marta", "op": nulls(op="create_task", title="Marta")}]),
    ]
    ops = from_model(flat)
    assert ops == [
        {"op": "create_expense", "amount_cents": 4200, "date": "2026-02-23",
         "category": "Groceries", "description": "groceries"},
        {"op": "update", "ref": "t1", "set": {"due_date": "2026-02-27"}},
        {"op": "note", "text": "the thing with Marta", "suggestions": [
            {"label": "Task: Marta", "op": {"op": "create_task", "title": "Marta"}}]},
    ]
    assert shape_problems(ops) == []


class FakeMessages:
    def __init__(self, response):
        self.response, self.kwargs = response, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def fake_client(text, stop_reason="end_turn"):
    response = SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=900, output_tokens=120))
    return SimpleNamespace(messages=FakeMessages(response))


REQUEST = {"capture_id": "c1", "text": "coffee 3.50", "source": "typed",
           "captured_at": "2026-02-23T09:00:00", "tz": "Europe/Lisbon", "currency": "EUR",
           "context": {}}


def test_the_request_carries_the_capture_as_data_with_structured_output():
    client = fake_client(json.dumps({"ops": [nulls(
        op="create_expense", amount_cents=350, date="2026-02-23", category="Eating out",
        description="coffee", suggestions=None)]}))
    reply = AnthropicModel(name="claude-haiku-5-5", effort="medium", client=client) \
        .propose(REQUEST)
    sent = client.messages.kwargs
    assert sent["model"] == "claude-haiku-5-5"
    assert sent["output_config"]["format"] == {"type": "json_schema",
                                               "schema": OUTPUT_SCHEMA}
    assert "temperature" not in sent
    assert json.loads(sent["messages"][0]["content"])["text"] == "coffee 3.50"
    assert reply.ops[0]["amount_cents"] == 350 and reply.input_tokens == 900


@pytest.mark.parametrize("text,stop", [("not json", "end_turn"), ("{}", "end_turn"),
                                       ('{"ops": []}', "max_tokens"),
                                       ('{"ops": []}', "refusal")])
def test_unreadable_output_is_a_model_output_error(text, stop):
    with pytest.raises(ModelOutputError):
        AnthropicModel(name="m", effort="low", client=fake_client(text, stop)).propose(REQUEST)
