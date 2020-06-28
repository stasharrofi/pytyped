import json
import pytest  # type: ignore

from dataclasses import dataclass
from dataclasses import field

from datetime import date
from datetime import datetime
from enum import Enum
from typing import List, NamedTuple, Optional

from pytyped.json.decoder import JsDecodeException
from pytyped.json.decoder import JsDecodeErrorInArray
from pytyped.json.decoder import JsDecodeErrorInField
from pytyped.json.decoder import JsonBoxedDecoder
from pytyped.json.decoder import JsDecodeErrorFinal
from pytyped.json.decoder import JsonErrorAsDefaultDecoder
from pytyped.json.decoder import AutoJsonDecoder


class E(Enum):
    X = "A"
    Y = "B"
    Z = "C"


@dataclass
class A:
    d: Optional[date]
    dt: Optional[datetime]
    e: Optional[E]
    x: int
    y: bool
    z: str = "abc"


@dataclass
class B:
    maybe_a: Optional[A]
    a_list: List[A] = field(default_factory=lambda: [A(
        date(2019, 1, 1),
        datetime(2019, 1, 1, 0, 0, 0, 0, None),
        E.Z,
        10,
        True,
        "List[A]",
    )])


class BoxedA(NamedTuple):
    value: A


auto_json_decoder = AutoJsonDecoder()
a_decoder = auto_json_decoder.extract(A)
b_decoder = auto_json_decoder.extract(B)
boxed_a_decoder = JsonBoxedDecoder("value", a_decoder, lambda d: BoxedA(**d))
default_a = A(d=None, dt=None, e=None, x=100, y=False, z="default")
a_with_default_decoder = JsonErrorAsDefaultDecoder(a_decoder, default_a)

valid_a_jsons = [
    '{"x": 1, "y": false, "z": "xyz"}',
    '{"x": 1, "y": false, "z": "xyz", "ts":"2019-01-02"}',
    '{"x": 1, "y": false, "z": "xyz", "ts": 1546405200.001}',
    '{"x": 1, "y": false, "z": "xyz", "ts": 1546405200001}',
    '{"x": 1, "y": false}',
    '{"x": "1", "y": false}',
    '{"x": 1, "y": false, "z": null}',
    '{"e": "A", "x": 1, "y": false}',
    '{"d": "2019-01-20", "x": 1, "y": false}',
    '{"dt": "2019-01-20T11:11:11", "x": 1, "y": false}',
]
invalid_a_jsons = [
    '{"x": 1.5, "y": false}',  # non-integral integer
    '{"x": 1, "y": "string"}',  # Boolean expected but string found
    '{"x": 1, "z": "abc"}',  # Required field missing
    '{"x": 1, "y": false, "z": 1}',  # Expected string but received numeric
    '{"e": 1, "x": 1, "y": false}',  # Expected enum E but received numeric
    '{"e": "X", "x": 1, "y": false}',  # Expected enum E but received string that cannot be decoded into date
    '{"d": 1, "x": 1, "y": false}',  # Expected date but received numeric
    '{"d": "abc", "x": 1, "y": false}',  # Expected date but received string that cannot be decoded into date
    '{"dt": 1, "x": 1, "y": false}',  # Expected datetime but received numeric
    '{"dt": "abc", "x": 1, "y": false}',  # Expected datetime but received string that cannot be decoded into date
    '[{"x": 1, "z": "abc"}]',  # Expected JsObject but received JsArray
]

invalid_b_jsons_set_1 = [
    '{"maybe_a": ' + invalid_a_json + "}" for invalid_a_json in invalid_a_jsons
]
invalid_b_jsons_set_2 = [
    '{"a_list": [' + invalid_a_json + "]}"
    for invalid_a_json in invalid_a_jsons
]
invalid_b_jsons_set_3 = [
    '{"a_list": ' + valid_a_json + "}" for valid_a_json in valid_a_jsons
]


def test_json_decoder_valid() -> None:
    a_list_json = "[" + (", ".join(valid_a_jsons)) + "]"

    b_with_a_json_possibilities = (
        [
            '{"maybe_a": ' + a_possibility + "}"
            for a_possibility in valid_a_jsons
        ]
        + [
            '{"maybe_a": ' + a_possibility + ', "a_list": null}'
            for a_possibility in valid_a_jsons
        ]
        + [
            '{"maybe_a": ' + a_possibility + ', "a_list": ' + a_list_json + "}"
            for a_possibility in valid_a_jsons
        ]
    )
    b_without_a_json_possibilities = [
        "{}",
        '{"maybe_a": null, "a_list": null}',
        '{"a_list": ' + a_list_json + "}",
        '{"maybe_a": null, "a_list": ' + a_list_json + "}",
    ]

    for a_json in valid_a_jsons:
        try:
            decoded_a = a_decoder.read(json.loads(a_json))
            assert isinstance(decoded_a, A)
            assert decoded_a.x == 1
            assert not decoded_a.y
            assert (decoded_a.z == "abc") or (decoded_a.z == "xyz")
        except Exception as e:
            assert False, (
                "Caught an exception while decoding valid JSONs. Exception: %s"
                % str(e)
            )

    for b_json in b_with_a_json_possibilities:
        try:
            decoded_b = b_decoder.read(json.loads(b_json))
            assert isinstance(decoded_b, B)
            assert len(decoded_b.a_list) in set([1, len(valid_a_jsons)])
            if len(decoded_b.a_list) == 1:
                assert decoded_b.a_list[0].x == 10
                assert decoded_b.a_list[0].y
            else:
                assert decoded_b.a_list[0].x == 1
                assert not decoded_b.a_list[0].y
            assert decoded_b.maybe_a is not None
            assert decoded_b.maybe_a.x == 1
            assert not decoded_b.maybe_a.y
            assert (decoded_b.maybe_a.z == "abc") or (
                decoded_b.maybe_a.z == "xyz"
            )
        except Exception as e:
            assert False, (
                "Caught an exception while decoding valid JSONs. Exception: %s"
                % str(e)
            )

    for b_json in b_without_a_json_possibilities:
        try:
            decoded_b = b_decoder.read(json.loads(b_json))
            assert isinstance(decoded_b, B)
            if len(decoded_b.a_list) == 1:
                assert decoded_b.a_list[0].x == 10
                assert decoded_b.a_list[0].y
            else:
                assert decoded_b.a_list[0].x == 1
                assert not decoded_b.a_list[0].y
            assert decoded_b.maybe_a is None
        except Exception as e:
            assert False, (
                "Caught an exception while decoding valid JSONs. Exception: %s"
                % str(e)
            )


def test_json_decoder_invalid() -> None:
    for invalid_a_json in invalid_a_jsons:
        try:
            x = a_decoder.read(json.loads(invalid_a_json))
            assert False, "Invalid JSON %s was successfully decoded as %s!" % (
                invalid_a_json,
                str(x),
            )
        except JsDecodeException as e:
            assert len(e.errors) == 1

    for invalid_b_json in invalid_b_jsons_set_1:
        try:
            _ = b_decoder.read(json.loads(invalid_b_json))
            assert False, "Invalid JSON was successfully decoded!"
        except JsDecodeException as e:
            assert len(e.errors) == 1
            assert isinstance(e.errors[0], JsDecodeErrorInField)

    for invalid_b_json in invalid_b_jsons_set_2:
        try:
            _ = b_decoder.read(json.loads(invalid_b_json))
            assert False, "Invalid JSON was successfully decoded!"
        except JsDecodeException as e:
            assert len(e.errors) == 1
            assert str(e).startswith("Found 1 error")
            error = e.errors[0]
            assert isinstance(error, JsDecodeErrorInField)
            assert isinstance(error.error, JsDecodeErrorInArray)

    for invalid_b_json in invalid_b_jsons_set_3:
        try:
            _ = b_decoder.read(json.loads(invalid_b_json))
            assert False, "Invalid JSON was successfully decoded!"
        except JsDecodeException as e:
            assert len(e.errors) == 1
            assert str(e).startswith("Found 1 error")
            error = e.errors[0]
            assert isinstance(error, JsDecodeErrorInField)
            assert isinstance(error.error, JsDecodeErrorFinal)


def test_boxed_decoder() -> None:
    for a_json in valid_a_jsons:
        try:
            decoded_boxed_a = boxed_a_decoder.read(json.loads(a_json))
            assert isinstance(decoded_boxed_a, BoxedA)
            assert decoded_boxed_a.value.x == 1
            assert not decoded_boxed_a.value.y
            assert (decoded_boxed_a.value.z == "abc") or (
                decoded_boxed_a.value.z == "xyz"
            )
        except Exception as e:
            assert False, (
                "Caught an exception while decoding valid JSONs. Exception: %s"
                % str(e)
            )

    for invalid_a_json in invalid_a_jsons:
        try:
            _ = boxed_a_decoder.read(json.loads(invalid_a_json))
            assert False, "Invalid JSON was successfully decoded!"
        except JsDecodeException as e:
            assert len(e.errors) == 1


def test_error_as_default_decoder() -> None:
    for a_json in valid_a_jsons:
        a = a_with_default_decoder.read(json.loads(a_json))
        assert a.x == 1
        assert not a.y
        assert (a.z == "abc") or (a.z == "xyz")

    for invalid_a_json in invalid_a_jsons:
        a = a_with_default_decoder.read(json.loads(invalid_a_json))
        assert a == default_a
