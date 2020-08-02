import json
from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union
from typing import cast

from pytyped.json.decoder import JsonDecoder
from pytyped.json.decoder import JsonNoneDecoder
from pytyped.json.encoder import AutoJsonEncoder
from pytyped.json.encoder import JsonBoxedEncoder
from pytyped.json.encoder import JsonEncoder
from pytyped.json.encoder import JsonEncoderException
from pytyped.json.encoder import JsonNoneEncoder
from pytyped.json.encoder import JsonTaggedEncoder
from tests.json import common
from tests.json.common import C1
from tests.json.common import G
from tests.json.common import G2

auto_json_encoder = AutoJsonEncoder()

a_encoder = auto_json_encoder.extract(common.A)
b_encoder = auto_json_encoder.extract(common.B)
boxed_a_encoder: JsonBoxedEncoder[common.A] = JsonBoxedEncoder("value", a_encoder)
c_flat_encoder = auto_json_encoder.extract(common.C)
c_nested_encoder = cast(
    JsonEncoder[common.C],
    JsonTaggedEncoder(
        branches={
            "C1": (common.C1, auto_json_encoder.extract(common.C1)),
            "C2": (common.C2, auto_json_encoder.extract(common.C2))
        },
        tag_field_name="tag",
        value_field_name="value"
    )
)
c_untagged_encoder = cast(JsonEncoder[common.C], auto_json_encoder.extract(cast(type, Union[common.C1, common.C2])))
str2int_dic_encoder = auto_json_encoder.extract(Dict[str, int])


test_cases: List[Tuple[JsonEncoder[Any], JsonDecoder[Any], List[str]]] = [
    (a_encoder, common.a_decoder, common.valid_a_jsons),
    (b_encoder, common.b_decoder, common.valid_b_jsons),
    (boxed_a_encoder, common.boxed_a_decoder, common.valid_a_jsons),
    (c_flat_encoder, common.c_flat_decoder, common.c_valid_flat_json_strs),
    (c_nested_encoder, common.c_nested_decoder, common.c_valid_nested_json_strs),
    (c_untagged_encoder, common.c_untagged_decoder, common.c_valid_untagged_json_strs),
    (str2int_dic_encoder, common.string_to_int_dic_json_decoder, common.valid_string_dictionary_jsons),
    (JsonNoneEncoder(), JsonNoneDecoder(), ['{}', 'null']),
    (auto_json_encoder.extract(common.Composite), common.composite_decoder, common.valid_composite_jsons)
]


def test_json_encoding() -> None:
    for (index, (encoder, decoder, json_strs)) in enumerate(test_cases):
        for json_str in json_strs:
            try:
                decoded_value = decoder.read(json.loads(json_str))
                re_encoded_str = json.dumps(encoder.write(decoded_value))
                re_decoded_value = decoder.read(json.loads(re_encoded_str))
                assert decoded_value == re_decoded_value, "Encoding + decoding =/= identity (for '%s')." % json_str
            except Exception:
                assert False, "Exception while proving encoding + decoding = identity (example: '%s')." % json_str


@dataclass
class C3(common.C):
    c3_specific: int


def test_unknown_subclass() -> None:
    c3 = C3(common=10, c3_specific=20)
    for c_encoder in [c_flat_encoder, c_nested_encoder, c_untagged_encoder]:
        try:
            c_encoder.write(c3)
            assert False, "Unknown class C3 (at the time of encoder extraction) was successfully serialized"
        except JsonEncoderException:
            pass


def test_nested_generics() -> None:
    # The following just tests that extractor does not go into an infinite loop
    auto_json_encoder.extract(G2[C1])
    auto_json_encoder.extract(G[G[C1]])
    auto_json_encoder.extract(G[G[G[C1]]])
