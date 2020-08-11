from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Callable
from typing import cast, Tuple
from typing import Any
from typing import Dict
from typing import Generic
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import TypeVar
from typing import Union

from pytyped.macros.boxed import Boxed
from pytyped.macros.extractor import Extractor
from pytyped.macros.extractor import WithDefault
from pytyped.json.common import JsValue


@dataclass
class JsonEncoderException(Exception):
    message: str


T = TypeVar("T")


class JsonEncoder(Generic[T], metaclass=ABCMeta):
    is_optional: bool = False

    @abstractmethod
    def encode(self, t: T) -> JsValue:
        pass

    def write(self, t: T) -> JsValue:
        return self.encode(t)


@dataclass
class JsonObjectEncoder(JsonEncoder[T]):
    field_encoders: Dict[str, JsonEncoder[Any]]

    def encode(self, t: T) -> JsValue:
        d: Dict[str, Any]
        if hasattr(t, "_asdict"):
            d = cast(NamedTuple, t)._asdict()
        else:
            d = t.__dict__

        return {
            field_name: field_encoder.encode(d[field_name])
            for field_name, field_encoder in self.field_encoders.items()
        }


@dataclass
class JsonTupleEncoder(JsonEncoder[Tuple[Any, ...]]):
    field_encoders: List[JsonEncoder[Any]]

    def encode(self, t: Tuple[Any, ...]) -> JsValue:
        return [e.encode(v) for (v, e) in zip(t, self.field_encoders)]


@dataclass
class JsonTaggedEncoder(JsonEncoder[T]):
    branches: Dict[str, Tuple[type, JsonEncoder[Any]]]
    tag_field_name: str = "tag"
    value_field_name: Optional[str] = None

    def encode(self, t: T) -> JsValue:
        for branch_name, (branch_type, encoder) in self.branches.items():
            if isinstance(t, branch_type):
                encoded_value: JsValue = encoder.encode(t)
                if self.value_field_name is not None:
                    encoded_value = {self.value_field_name: encoded_value}
                if not isinstance(encoded_value, dict):
                    raise JsonEncoderException("Only JSON objects are supported as encoded value of named sum types.")
                encoded_value[self.tag_field_name] = branch_name
                return encoded_value

        raise JsonEncoderException("Unknown subclass (known subclasses are %s)" % (", ".join(self.branches.keys())))


@dataclass
class JsonPriorityEncoder(JsonEncoder[T]):
    branches: List[Tuple[type, JsonEncoder[Any]]]

    def encode(self, t: T) -> JsValue:
        for branch_type, encoder in self.branches:
            if isinstance(t, branch_type):
                return encoder.encode(t)

        raise JsonEncoderException(
            "Unknown sub-type (known sub-types are %s)" % (", ".join([str(t) for (t, _) in self.branches]))
        )


@dataclass
class JsonOptionalEncoder(JsonEncoder[Optional[T]]):
    inner_encoder: JsonEncoder[T]

    def encode(self, t: Optional[T]) -> JsValue:
        if t is None:
            return None

        return self.inner_encoder.encode(t)


U = TypeVar("U")


@dataclass
class JsonMappedEncoder(JsonEncoder[T], Generic[T, U]):
    u_encoder: JsonEncoder[U]
    t_to_u: Callable[[T], U]

    def encode(self, t: T) -> JsValue:
        transformer = cast(Callable[[T], U], self.t_to_u)
        return self.u_encoder.encode(transformer(t))


@dataclass
class JsonBoxedEncoder(JsonEncoder[T]):
    field_name: str
    field_encoder: JsonEncoder[Any]

    def encode(self, t: T) -> JsValue:
        d = cast(NamedTuple, t)._asdict()
        return self.field_encoder.encode(d[self.field_name])


@dataclass
class JsonListEncoder(JsonEncoder[List[T]]):
    element_encoder: JsonEncoder[T]

    def encode(self, list: List[T]) -> JsValue:
        return [self.element_encoder.encode(i) for i in list]


@dataclass
class JsonStringDictionaryEncoder(JsonEncoder[Dict[str, T]]):
    element_encoder: JsonEncoder[T]

    def encode(self, d: Dict[str, T]) -> JsValue:
        return {k: self.element_encoder.encode(v) for k, v in d.items()}


@dataclass
class JsonBasicEncoder(
    JsonEncoder[Union[str, int, bool, float, Decimal, None]]
):
    def encode(
        self, t: Union[str, int, bool, float, Decimal, None]
    ) -> JsValue:
        return t


@dataclass
class JsonDecimalEncoder(JsonEncoder[Decimal]):
    def encode(self, t: Decimal) -> JsValue:
        return str(t)


@dataclass
class JsonDateEncoder(JsonEncoder[Union[date, datetime]]):
    def encode(self, d: Union[date, datetime]) -> JsValue:
        return d.isoformat()


@dataclass
class JsonEnumEncoder(JsonEncoder[Enum]):
    def encode(self, t: Enum) -> JsValue:
        return str(t.value)


@dataclass
class JsonNoneEncoder(JsonEncoder[None]):
    def encode(self, t: None) -> JsValue:
        return {}


class AutoJsonEncoder(Extractor[JsonEncoder[Any]]):
    json_basic_encoder: JsonBasicEncoder = JsonBasicEncoder()
    json_decimal_encoder: JsonDecimalEncoder = JsonDecimalEncoder()
    json_date_encoder: JsonDateEncoder = JsonDateEncoder()
    json_enum_encoder: JsonEnumEncoder = JsonEnumEncoder()

    basic_encoders: Dict[type, Boxed[JsonEncoder[Any]]] = {
        bool: Boxed(json_basic_encoder),
        str: Boxed(json_basic_encoder),
        int: Boxed(json_basic_encoder),
        float: Boxed(json_basic_encoder),
        Decimal: Boxed(json_decimal_encoder),
        datetime: Boxed(json_date_encoder),
        date: Boxed(json_date_encoder),
        type(None): Boxed(JsonNoneEncoder())
    }

    def __init__(self) -> None:
        super().__init__()

    @property
    def basics(self) -> Dict[type, Boxed[JsonEncoder[Any]]]:
        return self.basic_encoders

    def named_product_extractor(self, t: type, fields: Dict[str, WithDefault[JsonEncoder[Any]]]) -> JsonEncoder[Any]:
        field_encoders: Dict[str, JsonEncoder[Any]] = {
            n: v.t for (n, v) in fields.items()
        }
        return JsonObjectEncoder(field_encoders=field_encoders)

    def unnamed_product_extractor(self, t: type, fields: List[JsonEncoder[Any]]) -> JsonEncoder[Tuple[Any, ...]]:
        return JsonTupleEncoder(fields)

    def named_sum_extractor(self, t: type, branches: Dict[str, Tuple[type, JsonEncoder[Any]]]) -> JsonEncoder[Any]:
        return JsonTaggedEncoder(
            branches=branches,
            tag_field_name=t.__name__,
            value_field_name=None
        )

    def unnamed_sum_extractor(self, t: type, branches: List[Tuple[type, JsonEncoder[Any]]]) -> JsonEncoder[Any]:
        return JsonPriorityEncoder(branches)

    def optional_extractor(self, t: JsonEncoder[T]) -> JsonEncoder[Optional[T]]:
        return JsonOptionalEncoder(t)

    def list_extractor(self, t: JsonEncoder[T]) -> JsonEncoder[List[T]]:
        return JsonListEncoder(t)

    def dictionary_extractor(
        self,
        key: type,
        value: type,
        key_ext: JsonEncoder[Any],
        val_ext: JsonEncoder[Any]
    ) -> JsonEncoder[Dict[Any, Any]]:
        def to_str_dict(d: Dict[Enum, Any]) -> Dict[str, Any]:
            return {cast(str, k.value): v for k, v in d.items()}

        if key is str:
            return JsonStringDictionaryEncoder(val_ext)
        if issubclass(key, Enum):
            return JsonMappedEncoder(JsonStringDictionaryEncoder(val_ext), to_str_dict)
        raise NotImplementedError()

    def enum_extractor(self, enum_name: str, enum_values: List[Tuple[str, Any]]) -> JsonEncoder[Any]:
        return self.json_enum_encoder

