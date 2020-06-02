from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
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
class JsonOptionalEncoder(JsonEncoder[Optional[T]]):
    inner_encoder: JsonEncoder[T]

    def encode(self, t: Optional[T]) -> JsValue:
        if t is None:
            return None

        return self.inner_encoder.encode(t)


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


class AutoJsonEncoder(Extractor[JsonEncoder[Any]]):
    json_basic_encoder: JsonBasicEncoder = JsonBasicEncoder()
    json_decimal_encoder: JsonDecimalEncoder = JsonDecimalEncoder()
    json_date_encoder: JsonDateEncoder = JsonDateEncoder()
    json_enum_encoder: JsonEnumEncoder = JsonEnumEncoder()

    basic_encoders: Dict[type, Boxed[JsonEncoder[Any]]] = {
        bool: Boxed(json_basic_encoder),
        str: Boxed(json_basic_encoder),
        int: Boxed(json_basic_encoder),
        Decimal: Boxed(json_decimal_encoder),
        datetime: Boxed(json_date_encoder),
        date: Boxed(json_date_encoder)
    }

    @property
    def basics(self) -> Dict[type, Boxed[JsonEncoder[Any]]]:
        return self.basic_encoders

    def product_extractor(self, t: type, fields: Dict[str, WithDefault[JsonEncoder[Any]]]) -> JsonEncoder[Any]:
        field_encoders: Dict[str, JsonEncoder[Any]] = {
            n: v.t for (n, v) in fields.items()
        }
        return JsonObjectEncoder(field_encoders=field_encoders)

    def sum_extractor(self, t: type, branches: Dict[type, T]) -> T:
        raise NotImplemented()

    def optional_extractor(self, t: JsonEncoder[T]) -> JsonEncoder[Optional[T]]:
        return JsonOptionalEncoder(t)

    def list_extractor(self, t: JsonEncoder[T]) -> JsonEncoder[List[T]]:
        return JsonListEncoder(t)

    def enum_extractor(self, enum_name: str, enum_values: List[Tuple[str, Any]]) -> JsonEncoder[Any]:
        return self.json_enum_encoder

