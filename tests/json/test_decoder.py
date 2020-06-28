import json
from typing import Dict
from typing import Tuple
from typing import Union
from typing import cast

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
from pytyped.json.decoder import JsonDecoder
from pytyped.json.decoder import JsonErrorAsDefaultDecoder
from pytyped.json.decoder import AutoJsonDecoder
from pytyped.json.decoder import JsonMappedDecoder
from pytyped.json.decoder import JsonTaggedDecoder


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
    t: Tuple[str, int] = ("t_str", 10)
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


@dataclass
class C:
    common: int


@dataclass
class C1(C):
    c1_specific: str


@dataclass
class C2(C):
    c2_specific: str


@dataclass
class D:
    common: int
    c1_specific: Optional[str]
    c2_specific: Optional[str]


auto_json_decoder = AutoJsonDecoder()
a_decoder = auto_json_decoder.extract(A)
b_decoder = auto_json_decoder.extract(B)
boxed_a_decoder = JsonBoxedDecoder("value", a_decoder, lambda d: BoxedA(**d))
default_a = A(d=None, dt=None, e=None, x=100, y=False, t=("t_str2", 20), z="default")
a_with_default_decoder = JsonErrorAsDefaultDecoder(a_decoder, default_a)

valid_a_jsons = [
    '{"x": 1, "y": false, "z": "xyz"}',
    '{"x": 1, "y": false, "t": ["abc", 8]}',
    '{"x": 1, "y": false}',
    '{"x": "1", "y": false}',
    '{"x": 1, "y": false, "z": null}',
    '{"e": "A", "x": 1, "y": false}',
    '{"d": "2019-01-20", "x": 1, "y": false}',
    '{"dt": "2019-01-20T11:11:11", "x": 1, "y": false}',
]
invalid_a_jsons = [
    '{"x": [], "y": false}',  # expected integer, received JsArray
    '{"x": 1.5, "y": false}',  # non-integral integer
    '{"x": 1, "y": "string"}',  # Boolean expected but string found
    '{"x": 1, "z": "abc"}',  # Required field missing
    '{"x": 1, "y": false, "z": 1}',  # Expected string but received numeric
    '{"x": 1, "y": false, "t": "abc"}',  # A tuple is supposed to be encoded as a JsArray.
    '{"x": 1, "y": false, "t": {}}',  # A tuple is supposed to be encoded as a JsArray.
    '{"x": 1, "y": false, "t": ["abc"]}',  # Wrong number of arguments for tuple
    '{"x": 1, "y": false, "t": ["abc", 10, "efg"]}',  # Wrong number of arguments for tuple
    '{"x": 1, "y": false, "t": [1, 10]}',  # Wrong type of argument in tuple
    '{"x": 1, "y": false, "t": ["abc", "def"]}',  # Wrong type of argument in tuple
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
            assert decoded_a.t[0] in ["t_str", "abc"]
            assert decoded_a.t[1] in [8, 10]
            assert decoded_a.z in ["abc", "xyz"]
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


def test_optional_decoder_none() -> None:
    assert auto_json_decoder.extract(Optional[A]).read(json.loads("null")) is None


def valid_c_test_cases(decoder: JsonDecoder[C], valid_jsons: List[str]) -> None:
    for s in valid_jsons:
        try:
            c: C = decoder.read(json.loads(s))
            assert c.common == 10
            if isinstance(c, C1):
                assert c.c1_specific == "abc"
            else:
                assert isinstance(c, C2)
                assert c.c2_specific == "def"
        except JsDecodeException:
            assert False, "Valid JSON failed to be decoded: '%s'." % s


def invalid_c_test_cases(decoder: JsonDecoder[C], invalid_jsons: List[str]) -> None:
    for s in invalid_jsons:
        try:
            decoder.read(json.loads(s))
            assert False, "Invalid JSON was decoded successfully: '%s'." % s
        except JsDecodeException:
            pass


def valid_d_test_cases(decoder: JsonDecoder[D], valid_jsons: List[str]) -> None:
    for s in valid_jsons:
        try:
            d: D = decoder.read(json.loads(s))
            assert d.common == 10
            assert d.c1_specific in [None, "abc"]
            assert d.c2_specific in [None, "def"]
            assert None in [d.c1_specific, d.c2_specific]
        except JsDecodeException:
            assert False, "Valid JSON failed to be decoded: '%s'." % s


def invalid_d_test_cases(decoder: JsonDecoder[D], invalid_jsons: List[str]) -> None:
    for s in invalid_jsons:
        try:
            decoder.read(json.loads(s))
            assert False, "Invalid JSON was decoded successfully: '%s'." % s
        except JsDecodeException:
            pass


c_valid_flat_json_strs: List[str] = [
    '{"common": 10, "c1_specific": "abc", "C": "C1"}',
    '{"common": 10, "c2_specific": "def", "C": "C2"}'
]
c_invalid_flat_json_strs: List[str] = [
    '[]',  # named unions are expected to be JsObjects
    '10',  # named unions are expected to be JsObjects
    'null',  # named unions are expected to be JsObjects
    '"C1"',  # named unions are expected to be JsObjects
    '[{"common": 10, "c1_specific": "abc", "C": "C1"}]',  # named unions are expected to be JsObjects
    '{"common": 10, "c1_specific": "abc", "C": 10}',  # tag is supposed to be a string
    '{"common": 10, "c1_specific": "abc"}',  # tag is missing
    '{"common": 10, "c1_specific": "def", "C": "C3"}',  # unknown tag
    '{"common": 10, "c2_specific": "def", "C": "C3"}',  # unknown tag
    '{"common": "abc", "c1_specific": "def", "C": "C1"}',  # expected integer but received string
    '{"common": 10, "c1_specific": 10, "C": "C1"}',  # expected string but received integer
    '{"common": "abc", "c2_specific": "def", "C": "C2"}',  # expected integer but received string
    '{"common": 10, "c2_specific": 10, "C": "C2"}',  # expected string but received integer
    '{"common": "abc", "c2_specific": "def", "C": "C1"}',  # incorrect tag
    '{"common": "abc", "c1_specific": "def", "C": "C2"}',  # incorrect tag
]

c_valid_nested_json_strs: List[str] = [
    '{"value": {"common": 10, "c1_specific": "abc"}, "tag": "C1"}',
    '{"value": {"common": 10, "c2_specific": "def"}, "tag": "C2"}'
]
c_invalid_nested_json_strs: List[str] = [
    '[]',  # named unions are expected to be JsObjects
    '10',  # named unions are expected to be JsObjects
    'null',  # named unions are expected to be JsObjects
    '"C1"',  # named unions are expected to be JsObjects
    '[{"common": 10, "c1_specific": "abc", "tag": "C1"}]',  # named unions are expected to be JsObjects
    '{"common": 10, "c1_specific": "abc", "tag": 10}',  # tag is supposed to be a string
    '{"common": 10, "c1_specific": "abc", "tag": "C1"}',  # flat encoding instead of nested encoding
    '{"value": {"common": 10, "c1_specific": "abc"}}',  # tag is missing
    '{"value": {"common": 10, "c1_specific": "def"}, "tag": "C3"}',  # unknown tag
    '{"value": {"common": 10, "c2_specific": "def"}, "tag": "C3"}',  # unknown tag
    '{"value": {"common": "abc", "c1_specific": "def"}, "tag": "C1"}',  # expected integer but received string
    '{"value": {"common": 10, "c1_specific": 10}, "tag": "C1"}',  # expected string but received integer
    '{"value": {"common": "abc", "c2_specific": "def"}, "tag": "C2"}',  # expected integer but received string
    '{"value": {"common": 10, "c2_specific": 10}, "tag": "C2"}',  # expected string but received integer
    '{"value": {"common": "abc", "c2_specific": "def"}, "tag": "C1"}',  # incorrect tag
    '{"value": {"common": "abc", "c1_specific": "def"}, "tag": "C2"}',  # incorrect tag
]

c_valid_untagged_json_strs: List[str] = [
    '{"common": 10, "c1_specific": "abc"}',
    '{"common": 10, "c2_specific": "def"}'
]
c_invalid_untagged_json_strs: List[str] = [
    '[]',  # not decodable as either C1 or C2
    '10',  # not decodable as either C1 or C2
    'null',  # not decodable as either C1 or C2
    '"C1"',  # not decodable as either C1 or C2
    '[{"common": 10, "c1_specific": "abc"}]',  # not decodable as either C1 or C2
    '{"common": "abc", "c1_specific": "def"}',  # expected integer but received string
    '{"common": 10, "c1_specific": 10}',  # expected string but received integer
    '{"common": "abc", "c2_specific": "def"}',  # expected integer but received string
    '{"common": 10, "c2_specific": 10}'  # expected string but received integer
]

c_flat_decoder = auto_json_decoder.extract(C)
c_nested_decoder = cast(
    JsonDecoder[C],
    JsonTaggedDecoder(
        branch_decoders={
            "C1": auto_json_decoder.extract(C1),
            "C2": auto_json_decoder.extract(C2)
        },
        tag_field_name="tag",
        value_field_name="value"
    )
)
c_untagged_decoder = cast(JsonDecoder[C], auto_json_decoder.extract(Union[C1, C2]))

c_decoding_tests: List[Tuple[JsonDecoder[C], List[str], List[str]]] = [
    (c_flat_decoder, c_valid_flat_json_strs, c_invalid_flat_json_strs),
    (c_nested_decoder, c_valid_nested_json_strs, c_invalid_nested_json_strs),
    (c_untagged_decoder, c_valid_untagged_json_strs, c_invalid_untagged_json_strs)
]


def test_c_decoders() -> None:
    for decoder, valid_jsons, invalid_jsons in c_decoding_tests:
        valid_c_test_cases(decoder, valid_jsons)
        invalid_c_test_cases(decoder, invalid_jsons)


def c_to_d(c: C) -> D:
    return D(
        common=c.common,
        c1_specific=c.c1_specific if isinstance(c, C1) else None,
        c2_specific=c.c2_specific if isinstance(c, C2) else None
    )


d_decoding_tests: List[Tuple[JsonDecoder[D], List[str], List[str]]] = [
    (JsonMappedDecoder(decoder, c_to_d), valids, invalids) for (decoder, valids, invalids) in c_decoding_tests
]


def test_d_decoding() -> None:
    for decoder, valid_jsons, invalid_jsons in d_decoding_tests:
        valid_d_test_cases(decoder, valid_jsons)
        invalid_d_test_cases(decoder, invalid_jsons)


def test_string_dictionary_decoder() -> None:
    decoder = auto_json_decoder.extract(Dict[str, int])
    valid_json_strs: List[str] = [
        '{}',
        '{"a": 1, "b": 2}',
        '{"c": 1, "b": 2}',
    ]
    invalid_json_strs: List[str] = [
        '[]',
        'null',
        '10',
        '"abc"',
        '[{}]',
        '{"a": "abc", "b": 2}'
    ]

    for json_str in valid_json_strs:
        try:
            decoder.read(json.loads(json_str))
        except JsDecodeException:
            assert False, "Valid JSON failed to be deserialized: '%s'." % json_str

    for json_str in invalid_json_strs:
        try:
            decoder.read(json.loads(json_str))
            assert False, "Invalid JSON was successfully deserialized: '%s'." % json_str
        except JsDecodeException:
            pass
