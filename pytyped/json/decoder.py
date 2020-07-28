from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from decimal import DecimalException
from enum import Enum

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
    field_defaults: Dict[str, Union[Boxed[Any], Callable[[], Any]]]
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
                    def_or_fac = self.field_defaults[field_name]
                    decoded_fields[field_name] = def_or_fac.t if isinstance(def_or_fac, Boxed) else def_or_fac()
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
class JsonTupleDecoder(JsonDecoder[Tuple[Any, ...]]):
    field_decoders: List[JsonDecoder[Any]]

    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[Tuple[Any, ...]]:
        if not isinstance(json, list):
            return [
                JsDecodeErrorFinal(
                    "Expected a JSON array but received something else."
                )
            ]
        if len(json) != len(self.field_decoders):
            return [
                JsDecodeErrorFinal(
                    "Expected a JSON array of size %d but received one of size %d." % (len(self.field_decoders), len(json))
                )
            ]

        decoded_fields: List[Any] = []
        decoding_errors: List[JsDecodeError] = []
        for index, field_decoder in enumerate(self.field_decoders):
            # The field_name is a key and its associated value is not None. So, it should be decoded.
            field_json = cast(JsValue, json[index])
            decoded_field = field_decoder.decode(field_json, [cast(JsValue, json)] + ancestors)
            if isinstance(decoded_field, Boxed):
                decoded_fields.append(decoded_field.t)
            else:
                for err in decoded_field:
                    decoding_errors.append(
                        JsDecodeErrorInArray(index, err)
                    )

        if len(decoding_errors) > 0:
            return decoding_errors
        else:
            return Boxed(tuple(decoded_fields))


@dataclass
class JsonTaggedDecoder(JsonDecoder[Any]):
    branch_decoders: Dict[str, JsonDecoder[Any]]
    tag_field_name: str = "tag"
    value_field_name: Optional[str] = None  # None means the value is in the same object file

    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[T]:
        if not isinstance(json, dict):
            return [JsDecodeErrorFinal("Expected a JSON object but received something else.")]

        tag_value = json.get(self.tag_field_name)
        if tag_value is None:
            return [
                JsDecodeErrorInField(
                    field_name=self.tag_field_name,
                    error=JsDecodeErrorFinal(
                        "Required tag field not found."
                    )
                )
            ]
        if not isinstance(tag_value, str):
            return [
                JsDecodeErrorInField(
                    field_name=self.tag_field_name,
                    error=JsDecodeErrorFinal(
                        "Expected a Json string for tag field but received something else."
                    )
                )
            ]

        decoder = self.branch_decoders.get(tag_value)
        if decoder is None:
            return [
                JsDecodeErrorInField(
                    field_name=self.tag_field_name,
                    error=JsDecodeErrorFinal(
                        "Unknown tag value %s (possible values are: %s)." % (tag_value, ", ".join(self.branch_decoders.keys()))
                    )
                )
            ]

        if self.value_field_name is None:
            return decoder.decode(json, ancestors)

        value_field = cast(JsValue, json.get(self.value_field_name))
        return decoder.decode(value_field, [value_field] + ancestors)


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
class JsonPriorityDecoder(JsonDecoder[Any]):
    # Decoders in the order of priority. The head of the list has more priority.
    inner_decoders: List[JsonDecoder[Any]]

    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[Any]:
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
class JsonFlatMappedDecoder(JsonDecoder[T], Generic[T, U]):
    u_decoder: JsonDecoder[U]
    u_to_t: Callable[[U], TOrError[T]]

    def decode(self, json: JsValue, ancestors: List[JsValue]) -> TOrError[T]:
        result = self.u_decoder.decode(json, ancestors)
        if isinstance(result, Boxed):
            transformer = cast(Callable[[U], TOrError[T]], self.u_to_t)
            return transformer(result.t)
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
class JsonStringDictionaryDecoder(JsonDecoder[Dict[str, T]]):
    element_decoder: JsonDecoder[T]

    def decode(
        self, json: JsValue, ancestors: List[JsValue]
    ) -> TOrError[Dict[str, T]]:
        if not isinstance(json, dict):
            return [
                JsDecodeErrorFinal(
                    "Expected a JSON object but received something else."
                )
            ]
        decoded_elements: Dict[str, Any] = {}
        decoding_errors: List[JsDecodeError] = []
        for key, value_json in json.items():
            if type(key) is not str:
                decoding_errors.append(
                    JsDecodeErrorFinal("Found non-string key %s in a json object (type: %s)." % (str(key), type(key)))
                )
            else:
                value_json = cast(JsValue, value_json)
                parent: JsValue = json
                decoded_value = self.element_decoder.decode(
                    value_json, [parent] + ancestors
                )
                if isinstance(decoded_value, Boxed):
                    if key not in decoded_elements:
                        decoded_elements[key] = decoded_value.t
                    else:
                        decoding_errors.append(JsDecodeErrorFinal("Found key %s more than once." % key))
                else:
                    for err in decoded_value:
                        decoding_errors.append(JsDecodeErrorInField(key, err))

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
            try:
                return Boxed(Decimal(json))
            except DecimalException:
                return [JsDecodeErrorFinal("Value not convertible to decimal: '%s'." % str(json))]

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
        type(None): Boxed(cast(JsonDecoder[Any], JsonNoneDecoder))
    }

    def __init__(self) -> None:
        super().__init__()

    @property
    def basics(self) -> Dict[type, Boxed[JsonDecoder[Any]]]:
        return self.basic_json_decoders

    def named_product_extractor(self, t: type, fields: Dict[str, WithDefault[JsonDecoder[Any]]]) -> JsonDecoder[Any]:
        field_decoders: Dict[str, JsonDecoder[Any]] = {
            n: v.t for (n, v) in fields.items()
        }
        field_defaults: Dict[str, Union[Boxed[Any], Callable[[], Any]]] = {
            n: v.default for (n, v) in fields.items() if v.default is not None
        }

        return JsonObjectDecoder(
            field_decoders=field_decoders,
            field_defaults=field_defaults,
            constructor=lambda args: t(**args),
        )

    def unnamed_product_extractor(self, t: type, fields: List[JsonDecoder[Any]]) -> JsonDecoder[Tuple[Any, ...]]:
        return JsonTupleDecoder(fields)

    def named_sum_extractor(self, t: type, branches: Dict[str, Tuple[type, JsonDecoder[Any]]]) -> JsonDecoder[Any]:
        return JsonTaggedDecoder(
            branch_decoders={s: t for (s, (_, t)) in branches.items()},
            tag_field_name=t.__name__, value_field_name=None
        )

    def unnamed_sum_extractor(self, t: type, branches: List[Tuple[type, JsonDecoder[Any]]]) -> JsonDecoder[Any]:
        return JsonPriorityDecoder([d for (_, d) in branches])

    def optional_extractor(self, t: JsonDecoder[T]) -> JsonDecoder[Optional[T]]:
        return JsonOptionalDecoder(t)

    def list_extractor(self, t: JsonDecoder[T]) -> JsonDecoder[List[T]]:
        return JsonListDecoder(t)

    def dictionary_extractor(
        self,
        key: type,
        value: type,
        key_ext: JsonDecoder[Any],
        val_ext: JsonDecoder[Any]
    ) -> JsonDecoder[Dict[Any, Any]]:
        def to_enum_dict(d: Dict[str, Any]) -> TOrError[Dict[Any, Any]]:
            result: Dict[Any, Any] = {}
            errors: List[JsDecodeError] = []
            for k, v in d.items():
                try:
                    e = cast(Enum, key_ext.read(k))
                    result[e] = v
                except JsDecodeException as exception:
                    for err in exception.errors:
                        errors.append(err)

            if len(errors) > 0:
                return errors
            return Boxed(result)

        if key is str:
            return JsonStringDictionaryDecoder(val_ext)
        if issubclass(key, Enum):
            return JsonFlatMappedDecoder(JsonStringDictionaryDecoder(val_ext), to_enum_dict)
        raise NotImplementedError()

    def enum_extractor(self, enum_name: str, enum_values: List[Tuple[str, Any]]) -> JsonDecoder[Any]:
        return JsonEnumDecoder(enum_name, {n: v for (n, v) in enum_values})
