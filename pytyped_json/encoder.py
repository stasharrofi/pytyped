from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import cast
from typing import Any
from typing import Dict
from typing import Generic
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import TypeVar
from typing import Union

from pytyped_common.boxed import Boxed
from pytyped_common import extractor
from pytyped_json.common import JsValue

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
        d = cast(NamedTuple, t)._asdict()

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


class AutoJsonEncoder:
    json_basic_encoder: JsonBasicEncoder = JsonBasicEncoder()
    json_decimal_encoder: JsonDecimalEncoder = JsonDecimalEncoder()
    json_date_encoder: JsonDateEncoder = JsonDateEncoder()

    def build_encoder(
        self, in_typ: type, special_encoders: Dict[type, JsonEncoder[Any]] = {}
    ) -> JsonEncoder[Any]:

        basic_encoders = self.__build_basic_encoders()

        return extractor.auto_extractor(
            in_typ=in_typ,
            basics={n: Boxed(d) for (n, d) in basic_encoders.items()},
            specials={n: Boxed(d) for (n, d) in special_encoders.items()},
            product_extractor=self.__product_extractor,
            optional_extractor=lambda d: JsonOptionalEncoder(d),
            list_extractor=lambda d: JsonListEncoder(d),
            enum_extractor=lambda name, values: JsonEnumEncoder(),
        )

    def __build_basic_encoders(self) -> Dict[type, JsonEncoder[Any]]:
        return {
            bool: self.json_basic_encoder,
            str: self.json_basic_encoder,
            int: self.json_basic_encoder,
            Decimal: self.json_decimal_encoder,
            datetime: self.json_date_encoder,
            date: self.json_date_encoder,
        }

    def __product_extractor(
        self,
        named_tuple: type,
        fields: Dict[str, extractor.WithDefault[JsonEncoder[Any]]],
    ) -> JsonObjectEncoder[Any]:
        field_encoders: Dict[str, JsonEncoder[Any]] = {
            n: v.t for (n, v) in fields.items()
        }
        return JsonObjectEncoder(field_encoders=field_encoders)
