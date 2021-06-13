import json
from typing import Dict
from typing import Tuple
from typing import Union
from typing import cast

from typing import List, Optional
import pytest

from pytyped.json.decoder import JsDecodeException
from pytyped.json.decoder import JsDecodeErrorInArray
from pytyped.json.decoder import JsDecodeErrorInField
from pytyped.json.decoder import JsDecodeErrorFinal
from pytyped.json.decoder import JsonDecoder
from pytyped.json.decoder import JsonErrorAsDefaultDecoder
from pytyped.json.decoder import JsonMappedDecoder
from tests.json import common
from tests.json.common import C1, G, G2, IntBinaryTree, auto_json_decoder, valid_binary_int_tree_jsons, valid_int_trees, \
    valid_wide_trees, Tree, WideTree

default_a = common.A(d=None, dt=None, e=None, x=100, y=False, t=("t_str2", 20), z="default")
a_with_default_decoder = JsonErrorAsDefaultDecoder(common.a_decoder, default_a)

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
    '{"a_list": ' + valid_a_json + "}" for valid_a_json in common.valid_a_jsons
]


def test_json_decoder_valid() -> None:
    for a_json in common.valid_a_jsons:
        try:
            decoded_a = common.a_decoder.read(json.loads(a_json))
            assert isinstance(decoded_a, common.A)
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

    for b_json in common.b_with_a_json_possibilities:
        try:
            decoded_b = common.b_decoder.read(json.loads(b_json))
            assert isinstance(decoded_b, common.B)
            assert len(decoded_b.a_list) in {1, len(common.valid_a_jsons)}
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

    for b_json in common.b_without_a_json_possibilities:
        try:
            decoded_b = common.b_decoder.read(json.loads(b_json))
            assert isinstance(decoded_b, common.B)
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
            x = common.a_decoder.read(json.loads(invalid_a_json))
            assert False, "Invalid JSON %s was successfully decoded as %s!" % (
                invalid_a_json,
                str(x),
            )
        except JsDecodeException as e:
            assert len(e.errors) == 1

    for invalid_b_json in invalid_b_jsons_set_1:
        try:
            _ = common.b_decoder.read(json.loads(invalid_b_json))
            assert False, "Invalid JSON was successfully decoded!"
        except JsDecodeException as e:
            assert len(e.errors) == 1
            assert isinstance(e.errors[0], JsDecodeErrorInField)

    for invalid_b_json in invalid_b_jsons_set_2:
        try:
            _ = common.b_decoder.read(json.loads(invalid_b_json))
            assert False, "Invalid JSON was successfully decoded!"
        except JsDecodeException as e:
            assert len(e.errors) == 1
            assert str(e).startswith("Found 1 error")
            error = e.errors[0]
            assert isinstance(error, JsDecodeErrorInField)
            assert isinstance(error.error, JsDecodeErrorInArray)

    for invalid_b_json in invalid_b_jsons_set_3:
        try:
            _ = common.b_decoder.read(json.loads(invalid_b_json))
            assert False, "Invalid JSON was successfully decoded!"
        except JsDecodeException as e:
            assert len(e.errors) == 1
            assert str(e).startswith("Found 1 error")
            error = e.errors[0]
            assert isinstance(error, JsDecodeErrorInField)
            assert isinstance(error.error, JsDecodeErrorFinal)


def test_boxed_decoder() -> None:
    for a_json in common.valid_a_jsons:
        try:
            decoded_boxed_a = common.boxed_a_decoder.read(json.loads(a_json))
            assert isinstance(decoded_boxed_a, common.BoxedA)
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
            _ = common.boxed_a_decoder.read(json.loads(invalid_a_json))
            assert False, "Invalid JSON was successfully decoded!"
        except JsDecodeException as e:
            assert len(e.errors) == 1


def test_error_as_default_decoder() -> None:
    for a_json in common.valid_a_jsons:
        a = a_with_default_decoder.read(json.loads(a_json))
        assert a.x == 1
        assert not a.y
        assert (a.z == "abc") or (a.z == "xyz")

    for invalid_a_json in invalid_a_jsons:
        a = a_with_default_decoder.read(json.loads(invalid_a_json))
        assert a == default_a


def test_optional_decoder_none() -> None:
    assert common.auto_json_decoder.extract(cast(type, Optional[common.A])).read(json.loads("null")) is None


def valid_c_test_cases(decoder: JsonDecoder[common.C], valid_jsons: List[str]) -> None:
    for s in valid_jsons:
        try:
            c: common.C = decoder.read(json.loads(s))
            assert c.common == 10
            if isinstance(c, common.C1):
                assert c.c1_specific == "abc"
            else:
                assert isinstance(c, common.C2)
                assert c.c2_specific == "def"
        except JsDecodeException:
            assert False, "Valid JSON failed to be decoded: '%s'." % s


def invalid_c_test_cases(decoder: JsonDecoder[common.C], invalid_jsons: List[str]) -> None:
    for s in invalid_jsons:
        try:
            decoder.read(json.loads(s))
            assert False, "Invalid JSON was decoded successfully: '%s'." % s
        except JsDecodeException:
            pass


def valid_d_test_cases(decoder: JsonDecoder[common.D], valid_jsons: List[str]) -> None:
    for s in valid_jsons:
        try:
            d: common.D = decoder.read(json.loads(s))
            assert d.common == 10
            assert d.c1_specific in [None, "abc"]
            assert d.c2_specific in [None, "def"]
            assert None in [d.c1_specific, d.c2_specific]
        except JsDecodeException:
            assert False, "Valid JSON failed to be decoded: '%s'." % s


def invalid_d_test_cases(decoder: JsonDecoder[common.D], invalid_jsons: List[str]) -> None:
    for s in invalid_jsons:
        try:
            decoder.read(json.loads(s))
            assert False, "Invalid JSON was decoded successfully: '%s'." % s
        except JsDecodeException:
            pass


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


c_decoding_tests: List[Tuple[JsonDecoder[common.C], List[str], List[str]]] = [
    (common.c_flat_decoder, common.c_valid_flat_json_strs, c_invalid_flat_json_strs),
    (common.c_nested_decoder, common.c_valid_nested_json_strs, c_invalid_nested_json_strs),
    (common.c_untagged_decoder, common.c_valid_untagged_json_strs, c_invalid_untagged_json_strs)
]


def test_c_decoders() -> None:
    for decoder, valid_jsons, invalid_jsons in c_decoding_tests:
        valid_c_test_cases(decoder, valid_jsons)
        invalid_c_test_cases(decoder, invalid_jsons)


def c_to_d(c: common.C) -> common.D:
    return common.D(
        common=c.common,
        c1_specific=c.c1_specific if isinstance(c, common.C1) else None,
        c2_specific=c.c2_specific if isinstance(c, common.C2) else None
    )


d_decoding_tests: List[Tuple[JsonDecoder[common.D], List[str], List[str]]] = [
    (JsonMappedDecoder(decoder, c_to_d), valids, invalids) for (decoder, valids, invalids) in c_decoding_tests
]


def test_d_decoding() -> None:
    for decoder, valid_jsons, invalid_jsons in d_decoding_tests:
        valid_d_test_cases(decoder, valid_jsons)
        invalid_d_test_cases(decoder, invalid_jsons)


def test_string_dictionary_decoder() -> None:
    invalid_json_strs: List[str] = [
        '[]',
        'null',
        '10',
        '"abc"',
        '[{}]',
        '{"a": "abc", "b": 2}'
    ]

    for json_str in common.valid_string_dictionary_jsons:
        try:
            common.string_to_int_dic_json_decoder.read(json.loads(json_str))
        except JsDecodeException:
            assert False, "Valid JSON failed to be deserialized: '%s'." % json_str

    for json_str in invalid_json_strs:
        try:
            common.string_to_int_dic_json_decoder.read(json.loads(json_str))
            assert False, "Invalid JSON was successfully deserialized: '%s'." % json_str
        except JsDecodeException:
            pass


def test_composite_decoder() -> None:
    for json_str in common.valid_composite_jsons:
        composite = common.composite_decoder.read(json.loads(json_str))
        assert isinstance(composite.int_g.generic_field, int)
        assert isinstance(composite.str_g.generic_field, str)
        assert isinstance(composite.int_list_g.generic_field, list)
        for n in composite.int_list_g.generic_field:
            assert isinstance(n, int)


def test_nested_generics() -> None:
    # The following just tests that extractor does not go into an infinite loop
    auto_json_decoder.extract(G2[C1])
    auto_json_decoder.extract(G[G[C1]])
    auto_json_decoder.extract(G[G[G[C1]]])


@pytest.mark.parametrize("json_str", valid_binary_int_tree_jsons)
def test_int_binary_tree(json_str: str) -> None:
    json_obj = json.loads(json_str)
    decoder = auto_json_decoder.extract(IntBinaryTree)
    tree_instance = decoder.read(json_obj)
    assert tree_instance.value == 0
    assert tree_instance.left.value == 1
    assert tree_instance.right.value == 2
    assert tree_instance.right.left.value == 3
    assert tree_instance.right.right.value == 4


@pytest.mark.parametrize("json_str", valid_int_trees)
def test_binary_tree_int(json_str: str) -> None:
    json_obj = json.loads(json_str)
    decoder = auto_json_decoder.extract(Tree[int])
    tree_instance = decoder.read(json_obj)
    assert tree_instance.value == 0
    assert tree_instance.left.value == 1
    assert tree_instance.right.value == 2
    assert tree_instance.right.left.value == 3
    assert tree_instance.right.right.value == 4


@pytest.mark.parametrize("json_str", valid_wide_trees)
def test_wide_tree_str(json_str: str) -> None:
    json_obj = json.loads(json_str)
    decoder = auto_json_decoder.extract(WideTree[str])
    tree_instance = decoder.read(json_obj)
    assert tree_instance.collect() == ["abc", ["def", "ghi"], "jkl"]
