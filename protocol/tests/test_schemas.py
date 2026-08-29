"""The wire format, as an executable spec.

`docs/hub-envelope.md` describes the protocol in prose; these schemas are the
machine-readable half, and this file is what keeps all three -- schema, prose
and SDK -- honest. Before this, the only definition of an envelope was whatever
`build_message_envelope` happened to emit, so a change there could not be
detected as a protocol change.
"""

import json
import pathlib

import pytest
from jsonschema import Draft202012Validator

from protocol.error_codes import DESCRIPTIONS, ErrorCode
from protocol.star_client_v2.base import BaseWebSocketClient
from protocol.star_client_v2.types import ClientInfo, ClientType, MessageType

SCHEMA_DIR = pathlib.Path(__file__).resolve().parents[1] / "schemas"


def _load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text())


ENVELOPE = _load("envelope.schema.json")
PAYLOADS = _load("payloads.schema.json")
ERROR_CODES = _load("error_codes.schema.json")


def _payload_validator(defn: str) -> Draft202012Validator:
    """Validator for one payload type, resolvable against the shared $defs."""
    schema = dict(PAYLOADS)
    schema.pop("oneOf", None)
    schema["$ref"] = f"#/$defs/{defn}"
    return Draft202012Validator(schema)


# ----------------------------------------------------------- schemas are valid


@pytest.mark.parametrize(
    "schema", [ENVELOPE, PAYLOADS, ERROR_CODES], ids=["envelope", "payloads", "errors"]
)
def test_schema_is_itself_valid(schema):
    Draft202012Validator.check_schema(schema)


# ------------------------------------------------- the SDK matches the schema


class _Client(BaseWebSocketClient):
    """`build_message_envelope` is on the base class; the transport is not used."""

    def url(self) -> str:
        return "ws://test"

    async def connect(self) -> bool:
        raise NotImplementedError

    async def disconnect(self) -> bool:
        raise NotImplementedError

    async def send_message(self, instruction, data, target=None) -> bool:
        raise NotImplementedError


@pytest.fixture
def agent():
    return _Client("ws://test", ClientInfo(type=ClientType.AGENT, id="agent_1"))


def test_sdk_envelope_matches_the_schema(agent):
    envelope = agent.build_message_envelope(
        MessageType.MESSAGE.value,
        {"type": "action", "id": "1", "action": "move", "parameters": {}},
        target={"type": "env", "id": "env_1"},
    )
    Draft202012Validator(ENVELOPE).validate(envelope)


def test_sdk_envelope_defaults_to_the_hub(agent):
    envelope = agent.build_message_envelope(MessageType.HEARTBEAT.value, {"t": 1})
    Draft202012Validator(ENVELOPE).validate(envelope)
    assert envelope["recipient"] == {"type": "hub", "id": ""}


def test_sdk_envelope_accepts_a_client_info_target(agent):
    envelope = agent.build_message_envelope(
        MessageType.MESSAGE.value,
        {"type": "action", "id": 1, "action": "rest"},
        target=ClientInfo(type=ClientType.ENVIRONMENT, id="env_1"),
    )
    Draft202012Validator(ENVELOPE).validate(envelope)
    assert envelope["recipient"] == {"type": "env", "id": "env_1"}


def test_every_message_type_is_a_legal_envelope_type(agent):
    """The enum and the schema must agree on the transport instructions."""
    allowed = set(ENVELOPE["properties"]["type"]["enum"])
    assert {m.value for m in MessageType} == allowed


def test_every_client_type_is_a_legal_client_ref(agent):
    allowed = set(ENVELOPE["$defs"]["clientRef"]["properties"]["type"]["enum"])
    assert {c.value for c in ClientType} == allowed


# ------------------------------------------------------------ payload shapes


def test_valid_action_payloads():
    validator = _payload_validator("action")
    for payload in [
        {"type": "action", "id": 1, "action": "move", "parameters": {"unit_id": 3}},
        {"type": "action", "id": "42-7", "action": "get_action_list"},
    ]:
        validator.validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "action", "id": 1},  # no action name
        {"type": "action", "action": "move"},  # no id
        {"type": "action", "id": 1, "action": ""},  # empty verb
        {"type": "action", "id": 1, "action": "move", "parameters": []},  # not an object
        {"type": "action", "id": 1, "action": "move", "extra": 1},  # unknown field
        {"type": "action", "id": None, "action": "move"},  # id must be int or string
    ],
)
def test_invalid_action_payloads_are_rejected(payload):
    with pytest.raises(Exception):
        _payload_validator("action").validate(payload)


def test_valid_action_batch_payload():
    _payload_validator("actionBatch").validate(
        {
            "type": "action_batch",
            "id": "batch-1",
            "actions": [
                {"id": "toolcall_a", "action": "move", "parameters": {"unit_id": 1}},
                {"id": 2, "action": "rest"},
            ],
        }
    )


def test_empty_action_batch_is_rejected():
    with pytest.raises(Exception):
        _payload_validator("actionBatch").validate(
            {"type": "action_batch", "id": "b", "actions": []}
        )


def test_valid_outcome_payloads():
    validator = _payload_validator("outcome")
    validator.validate({"type": "outcome", "id": 1, "outcome": {"success": True}})
    # `outcome_type: "str"` means the body is a JSON string.
    validator.validate(
        {
            "type": "outcome",
            "id": "1",
            "outcome": '{"success": true}',
            "outcome_type": "str",
        }
    )


def test_outcome_requires_an_id():
    """Without it there is nothing to correlate against."""
    with pytest.raises(Exception):
        _payload_validator("outcome").validate(
            {"type": "outcome", "outcome": {"success": True}}
        )


def test_error_outcome_body_shape():
    _payload_validator("outcomeBody").validate(
        {
            "success": False,
            "error": "Internal service error",
            "error_code": int(ErrorCode.INTERNAL_ERROR),
            "message": "Action move failed: boom",
        }
    )


def test_turn_start_payload():
    _payload_validator("turnStart").validate(
        {
            "type": "turn_start",
            "faction": "wei",
            "turn_number": 3,
            "timestamp": 1.0,
            "message": "Your turn starts.",
        }
    )


def test_turn_start_rejects_an_unknown_faction():
    with pytest.raises(Exception):
        _payload_validator("turnStart").validate(
            {"type": "turn_start", "faction": "qin"}
        )


# --------------------------------------------------- error codes cannot drift


def test_error_code_schema_matches_the_enum():
    """The schema is generated from the enum; this catches a stale checked-in copy."""
    from_schema = {
        entry["const"]: (
            entry["title"],
            entry["description"],
            entry["retryable"],
            entry["rejectedBeforeDispatch"],
        )
        for entry in ERROR_CODES["oneOf"]
    }
    from_enum = {
        int(code): (
            code.name,
            DESCRIPTIONS[code],
            code.retryable,
            code.rejected_before_dispatch,
        )
        for code in ErrorCode
    }
    assert from_schema == from_enum


def test_every_error_code_validates_against_the_schema():
    validator = Draft202012Validator(ERROR_CODES)
    for code in ErrorCode:
        validator.validate(int(code))


def test_an_undefined_error_code_is_rejected():
    with pytest.raises(Exception):
        Draft202012Validator(ERROR_CODES).validate(9999)
