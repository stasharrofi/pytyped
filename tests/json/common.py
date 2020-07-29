from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict
from typing import Generic
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Tuple
from typing import TypeVar
from typing import Union
from typing import cast

from pytyped.json.decoder import AutoJsonDecoder
from pytyped.json.decoder import JsonBoxedDecoder
from pytyped.json.decoder import JsonDecoder
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
    dec: Decimal = Decimal("10.123")
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
        z="List[A]",
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


T = TypeVar("T")


@dataclass
class G(Generic[T]):
    non_generic_field: str
    generic_field: T


@dataclass
class G2(Generic[T]):
    gs: List[G[T]]


@dataclass
class Composite:
    some_field: int
    int_g: G[int]
    str_g: G[str]
    int_list_g: G[List[int]]


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
valid_b_jsons: List[str] = b_with_a_json_possibilities + b_without_a_json_possibilities

c_valid_flat_json_strs: List[str] = [
    '{"common": 10, "c1_specific": "abc", "C": "C1"}',
    '{"common": 10, "c2_specific": "def", "C": "C2"}'
]
c_valid_nested_json_strs: List[str] = [
    '{"value": {"common": 10, "c1_specific": "abc"}, "tag": "C1"}',
    '{"value": {"common": 10, "c2_specific": "def"}, "tag": "C2"}'
]
c_valid_untagged_json_strs: List[str] = [
    '{"common": 10, "c1_specific": "abc"}',
    '{"common": 10, "c2_specific": "def"}'
]

valid_string_dictionary_jsons: List[str] = [
    '{}',
    '{"a": 1, "b": 2}',
    '{"c": 1, "b": 2}',
]

valid_composite_jsons: List[str] = [
    """{
    "some_field": 10,
    "int_g": {"non_generic_field": "abc", "generic_field": 17},
    "str_g": {"non_generic_field": "def", "generic_field": "some_string"},
    "int_list_g": {"non_generic_field": "ghi", "generic_field": [10, 11, 12]}
}"""
]

auto_json_decoder = AutoJsonDecoder()

a_decoder = auto_json_decoder.extract(A)
b_decoder = auto_json_decoder.extract(B)
boxed_a_decoder = JsonBoxedDecoder("value", a_decoder, lambda d: BoxedA(**d))

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
c_untagged_decoder = cast(JsonDecoder[C], auto_json_decoder.extract(cast(type, Union[C1, C2])))

string_to_int_dic_json_decoder = auto_json_decoder.extract(Dict[str, int])

composite_decoder = cast(JsonDecoder[Composite], auto_json_decoder.extract(Composite))
