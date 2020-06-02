from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from dateutil import parser
from decimal import Decimal
from typing import Tuple
from typing import cast
from typing import Any
from typing import Callable
from typing import Dict
from typing import Generic
from typing import List
from typing import Optional
from typing import TypeVar
from typing import Union

from pytyped.macros.boxed import Boxed
from pytyped.macros.extractor import Extractor
from pytyped.macros.extractor import WithDefault
from pytyped.json.common import JsValue


class JsDecodeError(metaclass=ABCMeta):
    @abstractmethod
    def get_message(self) -> str:
        pass

    def to_string(self) -> str:
        return "Error when decoding JSON: " + self.get_message()


@dataclass
class JsDecodeErrorFinal(JsDecodeError):
    message: str

    def get_message(self) -> str:
        return ": " + self.message


@dataclass
class JsDecodeErrorInField(JsDecodeError):
    field_name: str
    error: JsDecodeError

    def get_message(self) -> str:
        return "/" + self.field_name + self.error.get_message()


@dataclass
class JsDecodeErrorInArray(JsDecodeError):
    index: int
    error: JsDecodeError

    def get_message(self) -> str:
        return "[" + str(self.index) + "]" + self.error.get_message()


class JsDecodeException(Exception):
    errors: List[JsDecodeError]

    def __init__(self, errors: List[JsDecodeError]) -> None:
        self.errors = errors

    def __str__(self) -> str:
        return "Found %d errors while validating JSON: [\n  %s]" % (
            len(self.errors),
            ",\n  ".join([e.to_string() for e in self.errors]),
        )


T = TypeVar("T")
TOrError = Union[Boxed[T], List[JsDecodeError]]


class JsonDecoder(Generic[T], metaclass=ABCMeta):
    is_optional: bool = False

    @abstractmethod
    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[T]:
        pass

    def read(self, json: JsValue) -> T:
        t_or_error = self.decode(json, [])
        if isinstance(t_or_error, Boxed):
            return t_or_error.t
        else:
            raise JsDecodeException(t_or_error)


@dataclass
class JsonObjectDecoder(JsonDecoder[T]):
    field_decoders: Dict[str, JsonDecoder[Any]]
    field_defaults: Dict[str, Any]
    constructor: Callable[[Dict[str, Any]], T]

    def get_constructor(self) -> Callable[[Dict[str, Any]], T]:
        return self.constructor  # type: ignore

    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[T]:
        if not isinstance(json, dict):
            return [
                JsDecodeErrorFinal(
                    "Expected a JSON object but received something else."
                )
            ]
        decoded_fields: Dict[str, Any] = {}
        decoding_errors: List[JsDecodeError] = []
        for field_name, field_decoder in self.field_decoders.items():
            if (field_name not in json) or (json[field_name] is None):
                if isinstance(field_decoder, JsonOptionalDecoder):
                    decoded_fields[field_name] = None
                elif field_name in self.field_defaults:
                    decoded_fields[field_name] = self.field_defaults[
                        field_name
                    ]
                else:
                    decoding_errors.append(
                        JsDecodeErrorInField(
                            field_name,
                            JsDecodeErrorFinal(
                                "Non-optional field was not found"
                            ),
                        )
                    )
            else:
                # The field_name is a key and its associated value is not None. So, it should be decoded.
                field_json = cast(JsValue, json[field_name])
                decoded_field = field_decoder.decode(
                    field_json, [cast(JsValue, json)] + ancestors
                )
                if isinstance(decoded_field, Boxed):
                    decoded_fields[field_name] = decoded_field.t
                else:
                    for err in decoded_field:
                        decoding_errors.append(
                            JsDecodeErrorInField(field_name, err)
                        )

        if len(decoding_errors) > 0:
            return decoding_errors
        else:
            return Boxed(self.get_constructor()(decoded_fields))


@dataclass
class JsonOptionalDecoder(JsonDecoder[Optional[T]]):
    inner_decoder: JsonDecoder[T]

    def decode(
        self, json: JsValue, ancestors: List[JsValue]
    ) -> TOrError[Optional[T]]:
        if json is None:
            return Boxed(None)

        result = self.inner_decoder.decode(json, ancestors)
        if isinstance(result, Boxed):
            return Boxed(result.t)
        else:
            return result


@dataclass
class JsonErrorAsDefaultDecoder(JsonDecoder[T]):
    inner_decoder: JsonDecoder[T]
    default: T

    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[T]:
        result = self.inner_decoder.decode(json, ancestors)
        if isinstance(result, Boxed):
            return result
        return Boxed(self.default)


@dataclass
class JsonPriorityDecoder(JsonDecoder[T]):
    # Decoders in the order of priority. The head of the list has more priority.
    inner_decoders: List[JsonDecoder[T]]

    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[T]:
        errors: List[JsDecodeError] = []
        for inner_decoder in self.inner_decoders:
            result = inner_decoder.decode(json, ancestors)
            if isinstance(result, Boxed):
                return result
            for e in result:
                errors.append(e)

        return errors


U = TypeVar("U")


@dataclass
class JsonMappedDecoder(JsonDecoder[T], Generic[T, U]):
    u_decoder: JsonDecoder[U]
    u_to_t: Callable[[U], T]

    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[T]:
        result = self.u_decoder.decode(json, ancestors)
        if isinstance(result, Boxed):
            transformer = cast(Callable[[U], T], self.u_to_t)
            return Boxed(transformer(result.t))
        return result


@dataclass
class JsonBoxedDecoder(JsonDecoder[T]):
    field_name: str
    field_decoder: JsonDecoder[Any]
    constructor: Callable[[Dict[str, Any]], T]

    def get_constructor(self) -> Callable[[Dict[str, Any]], T]:
        return self.constructor  # type: ignore

    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[T]:
        decoded_field = self.field_decoder.decode(json, ancestors)
        if isinstance(decoded_field, Boxed):
            return Boxed(
                self.get_constructor()({self.field_name: decoded_field.t})
            )
        else:
            return decoded_field


@dataclass
class JsonListDecoder(JsonDecoder[List[T]]):
    element_decoder: JsonDecoder[T]

    def decode(
        self, json: JsValue, ancestors: List[JsValue]
    ) -> TOrError[List[T]]:
        if not isinstance(json, list):
            return [
                JsDecodeErrorFinal(
                    "Expected a JSON array but received something else."
                )
            ]
        decoded_elements: List[Any] = []
        decoding_errors: List[JsDecodeError] = []
        for index, element_json in enumerate(json):
            element_json = cast(JsValue, element_json)
            parent: JsValue = json
            decoded_element = self.element_decoder.decode(
                element_json, [parent] + ancestors
            )
            if isinstance(decoded_element, Boxed):
                decoded_elements.append(decoded_element.t)
            else:
                for err in decoded_element:
                    decoding_errors.append(JsDecodeErrorInArray(index, err))

        if len(decoding_errors) > 0:
            return decoding_errors
        else:
            return Boxed(decoded_elements)


@dataclass
class JsonStringDecoder(JsonDecoder[str]):
    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[str]:
        if not isinstance(json, str):
            return [
                JsDecodeErrorFinal(
                    "Expected a JSON string but received something else."
                )
            ]
        return Boxed(json)


@dataclass
class JsonNumberDecoder(JsonDecoder[Decimal]):
    def decode(
        self, json: JsValue, ancestors: List[JsValue]
    ) -> TOrError[Decimal]:
        if isinstance(json, Decimal):
            return Boxed(json)
        elif (
            isinstance(json, float)
            or isinstance(json, int)
            or isinstance(json, str)
        ):
            return Boxed(Decimal(json))

        return [
            JsDecodeErrorFinal(
                "Expected a JSON number or a JSON string encoding a number but received something of type %s."
                % type(json)
            )
        ]


@dataclass
class JsonBooleanDecoder(JsonDecoder[bool]):
    def decode(
        self, json: JsValue, ancestors: List[JsValue]
    ) -> TOrError[bool]:
        if not isinstance(json, bool):
            return [
                JsDecodeErrorFinal(
                    "Expected a JSON boolean but received something else."
                )
            ]
        return Boxed(json)


json_string_decoder = JsonStringDecoder()
json_number_decoder = JsonNumberDecoder()


@dataclass
class JsonIntegerDecoder(JsonDecoder[int]):
    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[int]:
        decimal_or_error = json_number_decoder.decode(json, ancestors)
        if isinstance(decimal_or_error, Boxed):
            d = decimal_or_error.t
            if int(d) == d:
                return Boxed(int(d))
            else:
                return [
                    JsDecodeErrorFinal(
                        "Expected an integral number but received non-intgeral number."
                    )
                ]
        else:
            return decimal_or_error


@dataclass
class JsonDateDecoder(JsonDecoder[date]):
    def decode(
        self, json: JsValue, ancestors: List[JsValue]
    ) -> TOrError[date]:
        string_or_error = json_string_decoder.decode(json, ancestors)
        if isinstance(string_or_error, Boxed):
            s = string_or_error.t
            try:
                return Boxed(parser.isoparse(s).date())
            except ValueError:
                return [
                    JsDecodeErrorFinal(
                        "Expected a string representing a date but received '%s'."
                        % s
                    )
                ]
        else:
            return string_or_error


@dataclass
class JsonDatetimeDecoder(JsonDecoder[datetime]):
    def decode(
        self, json: JsValue, ancestors: List[JsValue]
    ) -> TOrError[datetime]:
        string_or_error = json_string_decoder.decode(json, ancestors)
        if isinstance(string_or_error, Boxed):
            s = string_or_error.t
            try:
                return Boxed(parser.isoparse(s))
            except ValueError:
                return [
                    JsDecodeErrorFinal(
                        "Expected a string representing a datetime but received '%s'."
                        % s
                    )
                ]
        else:
            return string_or_error


@dataclass
class JsonEnumDecoder(JsonDecoder[T]):
    enum_name: str
    enum_values: Dict[str, T]

    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[T]:
        string_or_error = json_string_decoder.decode(json, ancestors)
        if isinstance(string_or_error, Boxed):
            s = string_or_error.t
            enum_value = self.enum_values.get(s)
            if enum_value is None:
                return [
                    JsDecodeErrorFinal(
                        "Unexpected value %s while deserializing enum %s."
                        % (s, self.enum_name)
                    )
                ]
            else:
                return Boxed(enum_value)
        else:
            return string_or_error


@dataclass
class JsonNoneDecoder(JsonDecoder[None]):
    def decode(
        self, json: JsValue, ancestors: List[JsValue]
    ) -> TOrError[None]:
        return Boxed(None)


class AutoJsonDecoder(Extractor[JsonDecoder[Any]]):
    json_boolean_decoder = JsonBooleanDecoder()
    json_integer_decoder = JsonIntegerDecoder()
    json_date_decoder = JsonDateDecoder()
    json_datetime_decoder = JsonDatetimeDecoder()

    basic_json_decoders: Dict[type, Boxed[JsonDecoder[Any]]] = {
        bool: Boxed(json_boolean_decoder),
        str: Boxed(json_string_decoder),
        int: Boxed(json_integer_decoder),
        Decimal: Boxed(json_number_decoder),
        datetime: Boxed(json_datetime_decoder),
        date: Boxed(json_date_decoder),
        type(None): Boxed(JsonNoneDecoder)
    }

    def __init__(self) -> None:
        super().__init__()

    @property
    def basics(self) -> Dict[type, Boxed[JsonDecoder[Any]]]:
        return self.basic_json_decoders

    def product_extractor(self, t: type, fields: Dict[str, WithDefault[JsonDecoder[Any]]]) -> JsonDecoder[Any]:
        field_decoders: Dict[str, JsonDecoder[Any]] = {
            n: v.t for (n, v) in fields.items()
        }
        field_defaults: Dict[str, Any] = {
            n: v.default.t
            for (n, v) in fields.items()
            if v.default is not None
        }

        return JsonObjectDecoder(
            field_decoders=field_decoders,
            field_defaults=field_defaults,
            constructor=lambda args: t(**args),
        )

    def sum_extractor(self, t: type, branches: Dict[type, JsonDecoder[Any]]) -> JsonDecoder[Any]:
        pass

    def optional_extractor(self, t: JsonDecoder[T]) -> JsonDecoder[Optional[T]]:
        return JsonOptionalDecoder(t)

    def list_extractor(self, t: JsonDecoder[T]) -> JsonDecoder[List[T]]:
        return JsonListDecoder(t)

    def enum_extractor(self, enum_name: str, enum_values: List[Tuple[str, Any]]) -> JsonDecoder[Any]:
        return JsonEnumDecoder(enum_name, {n: v for (n, v) in enum_values})
