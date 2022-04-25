from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import DecimalException
from enum import Enum

from dateutil import parser
from decimal import Decimal
from typing import cast, Any, Callable, Dict, Generic, List, Optional, Tuple, TypeVar, Union

from pyhocon import ConfigFactory, ConfigTree
from pytyped.macros.boxed import Boxed
from pytyped.macros.extractor import Extractor
from pytyped.macros.extractor import WithDefault


HoconValue = Union[None, bool, int, float, Decimal, str, List[Any], ConfigTree]


class HoconDecodeError(metaclass=ABCMeta):
    @abstractmethod
    def get_message(self) -> str:
        pass

    def to_string(self) -> str:
        return "Error when decoding HOCON: " + self.get_message()


@dataclass
class HoconDecodeErrorFinal(HoconDecodeError):
    message: str

    def get_message(self) -> str:
        return ": " + self.message


@dataclass
class HoconDecodeErrorInField(HoconDecodeError):
    field_name: str
    error: HoconDecodeError

    def get_message(self) -> str:
        return "." + self.field_name + self.error.get_message()


@dataclass
class HoconDecodeErrorInArray(HoconDecodeError):
    index: int
    error: HoconDecodeError

    def get_message(self) -> str:
        return "[" + str(self.index) + "]" + self.error.get_message()


class HoconDecodeException(Exception):
    errors: List[HoconDecodeError]

    def __init__(self, errors: List[HoconDecodeError]) -> None:
        self.errors = errors

    def __str__(self) -> str:
        return "Found %d errors while validating JSON: [\n  %s]" % (
            len(self.errors),
            ",\n  ".join([e.to_string() for e in self.errors]),
        )


T = TypeVar("T")
TOrError = Union[Boxed[T], List[HoconDecodeError]]


class HoconDecoder(Generic[T], metaclass=ABCMeta):
    @classmethod
    def decodes_none(cls) -> bool:
        """
        Returns true if the decoder is able to deal with `None` values.
        """
        return False

    @abstractmethod
    def decode(self, hocon: HoconValue) -> TOrError[T]:
        pass

    def from_file(self, file_path: str, root: Optional[str] = None) -> T:
        hocon = ConfigFactory.parse_file(file_path)
        if root is not None:
            hocon = hocon[root]
        t_or_error = self.decode(hocon, [])
        if isinstance(t_or_error, Boxed):
            return t_or_error.t
        else:
            raise HoconDecodeException(t_or_error)


@dataclass
class HoconObjectDecoder(HoconDecoder[T]):
    field_decoders: Dict[str, HoconDecoder[Any]]
    field_defaults: Dict[str, Union[Boxed[Any], Callable[[], Any]]]
    constructor: Callable[[Dict[str, Any]], T]

    def decode(self, hocon: HoconValue) -> TOrError[T]:
        if not isinstance(hocon, ConfigTree):
            return [
                HoconDecodeErrorFinal(f"Expected a Hocon config tree but received something of type {type(hocon)}.")
            ]
        decoded_fields: Dict[str, Any] = {}
        decoding_errors: List[HoconDecodeError] = []
        for field_name, field_decoder in self.field_decoders.items():
            field_hocon = hocon.get(field_name, default=None)
            if field_hocon is None:
                if field_decoder.decodes_none():
                    decoded_fields[field_name] = field_decoder.decode(None)
                elif field_name in self.field_defaults:
                    def_or_fac = self.field_defaults[field_name]
                    decoded_fields[field_name] = def_or_fac.t if isinstance(def_or_fac, Boxed) else def_or_fac()
                else:
                    decoding_errors.append(
                        HoconDecodeErrorInField(field_name, HoconDecodeErrorFinal("Non-optional field was not found"))
                    )
            else:
                decoded_field = field_decoder.decode(field_hocon)
                if isinstance(decoded_field, Boxed):
                    decoded_fields[field_name] = decoded_field.t
                else:
                    decoding_errors.extend([HoconDecodeErrorInField(field_name, err) for err in decoded_field])

        if len(decoding_errors) > 0:
            return decoding_errors
        else:
            return Boxed(self.constructor(decoded_fields))


@dataclass
class HoconTupleDecoder(HoconDecoder[Tuple[Any, ...]]):
    field_decoders: List[HoconDecoder[Any]]

    def decode(self, hocon: HoconValue) -> TOrError[Tuple[Any, ...]]:
        if not isinstance(hocon, list):
            return [HoconDecodeErrorFinal(f"Expected a Hocon array but received something of type {type(hocon)}.")]
        if len(hocon) != len(self.field_decoders):
            return [HoconDecodeErrorFinal(
                f"Expected a HOCON array of size {len(self.field_decoders)} but received one of size {len(hocon)}."
            )]

        decoded_fields: List[Any] = []
        decoding_errors: List[HoconDecodeError] = []
        for index, field_decoder in enumerate(self.field_decoders):
            # The field_name is a key and its associated value is not None. So, it should be decoded.
            field_hocon = cast(HoconValue, hocon[index])
            decoded_field = field_decoder.decode(field_hocon)
            if isinstance(decoded_field, Boxed):
                decoded_fields.append(decoded_field.t)
            else:
                decoding_errors.extend([HoconDecodeErrorInArray(index, err) for err in decoded_field])

        if len(decoding_errors) > 0:
            return decoding_errors
        else:
            return Boxed(tuple(decoded_fields))


@dataclass
class HoconTaggedDecoder(HoconDecoder[Any]):
    branch_decoders: Dict[str, HoconDecoder[Any]]
    tag_field_name: str = "tag"
    value_field_name: Optional[str] = None  # None means the value is in the same object file

    def decode(self, hocon: HoconValue) -> TOrError[T]:
        if not isinstance(hocon, ConfigTree):
            return [HoconDecodeErrorFinal("Expected a Hocon object but received something else.")]

        tag_value = hocon.get(self.tag_field_name)
        if tag_value is None:
            return [HoconDecodeErrorInField(
                field_name=self.tag_field_name,
                error=HoconDecodeErrorFinal(f"Required tag field {self.tag_field_name} not found.")
            )]
        if not isinstance(tag_value, str):
            return [HoconDecodeErrorInField(
                field_name=self.tag_field_name,
                error=HoconDecodeErrorFinal(f"Expected tag field {self.tag_field_name} to be a string but found type {type(tag_value)}.")
            )]

        decoder = self.branch_decoders.get(tag_value)
        if decoder is None:
            return [HoconDecodeErrorInField(
                field_name=self.tag_field_name,
                error=HoconDecodeErrorFinal(f"Unknown tag value {tag_value} (possible values are: {', '.join(self.branch_decoders.keys())}).")
            )]

        if self.value_field_name is None:
            return decoder.decode(hocon)

        value_field = cast(HoconValue, hocon.get(self.value_field_name))
        return decoder.decode(value_field)


@dataclass
class HoconOptionalDecoder(HoconDecoder[Optional[T]]):
    inner_decoder: HoconDecoder[T]

    @classmethod
    def decodes_none(cls) -> bool:
        return True

    def decode(self, hocon: HoconValue) -> TOrError[Optional[T]]:
        if hocon is None:
            return Boxed(None)
        return self.inner_decoder.decode(hocon)


@dataclass
class HoconErrorAsDefaultDecoder(HoconDecoder[T]):
    inner_decoder: HoconDecoder[T]
    default: T

    def decode(self, hocon: HoconValue) -> TOrError[T]:
        result = self.inner_decoder.decode(hocon)
        if isinstance(result, Boxed):
            return result
        return Boxed(self.default)


@dataclass
class HoconPriorityDecoder(HoconDecoder[Any]):
    # Decoders in the order of priority. The head of the list has more priority.
    inner_decoders: List[HoconDecoder[Any]]

    def decode(self, hocon: HoconValue) -> TOrError[Any]:
        errors: List[HoconDecodeError] = []
        for inner_decoder in self.inner_decoders:
            result = inner_decoder.decode(hocon)
            if isinstance(result, Boxed):
                return result
            errors.extend(result)

        return errors


U = TypeVar("U")


@dataclass
class HoconMappedDecoder(HoconDecoder[T], Generic[T, U]):
    u_decoder: HoconDecoder[U]
    u_to_t: Callable[[U], T]

    def decode(self, hocon: HoconValue) -> TOrError[T]:
        result = self.u_decoder.decode(hocon)
        if isinstance(result, Boxed):
            transformer = cast(Callable[[U], T], self.u_to_t)
            return Boxed(transformer(result.t))
        return result


@dataclass
class HoconFlatMappedDecoder(HoconDecoder[T], Generic[T, U]):
    u_decoder: HoconDecoder[U]
    u_to_t: Callable[[U], TOrError[T]]

    def decode(self, hocon: HoconValue) -> TOrError[T]:
        result = self.u_decoder.decode(hocon)
        if isinstance(result, Boxed):
            transformer = cast(Callable[[U], TOrError[T]], self.u_to_t)
            return transformer(result.t)
        return result


@dataclass
class HoconListDecoder(HoconDecoder[List[T]]):
    element_decoder: HoconDecoder[T]

    def decode(self, hocon: HoconValue) -> TOrError[List[T]]:
        if not isinstance(hocon, list):
            return [HoconDecodeErrorFinal(f"Expected a Hocon array but received something of type {type(hocon)}.")]
        decoded_elements: List[Any] = []
        decoding_errors: List[HoconDecodeError] = []
        for index, element_hocon in enumerate(hocon):
            element_hocon = cast(HoconValue, element_hocon)
            decoded_element = self.element_decoder.decode(element_hocon)
            if isinstance(decoded_element, Boxed):
                decoded_elements.append(decoded_element.t)
            else:
                decoding_errors.extend([HoconDecodeErrorInArray(index, err) for err in decoded_element])

        if len(decoding_errors) > 0:
            return decoding_errors
        else:
            return Boxed(decoded_elements)


@dataclass
class HoconStringDictionaryDecoder(HoconDecoder[Dict[str, T]]):
    element_decoder: HoconDecoder[T]

    def decode(self, hocon: HoconValue) -> TOrError[Dict[str, T]]:
        if not isinstance(hocon, ConfigTree):
            return [HoconDecodeErrorFinal(f"Expected a Hocon config tree but received something of type {type(hocon)}.")]
        decoded_elements: Dict[str, Any] = {}
        decoding_errors: List[HoconDecodeError] = []
        for key, value_hocon in hocon.items():
            if type(key) is not str:
                decoding_errors.append(HoconDecodeErrorFinal(f"Found non-string key {key}  with type: {type(key)}."))
            else:
                value_hocon = cast(HoconValue, value_hocon)
                decoded_value = self.element_decoder.decode(value_hocon)
                if isinstance(decoded_value, Boxed):
                    decoded_elements[key] = decoded_value.t
                else:
                    decoding_errors.extend([HoconDecodeErrorInField(key, err) for err in decoded_value])

        if len(decoding_errors) > 0:
            return decoding_errors
        else:
            return Boxed(decoded_elements)


@dataclass
class HoconStringDecoder(HoconDecoder[str]):
    def decode(self, hocon: HoconValue) -> TOrError[str]:
        if not isinstance(hocon, str):
            return [HoconDecodeErrorFinal(f"Expected a string but received something of type {type(hocon)}.")]
        return Boxed(hocon)


@dataclass
class HoconNumberDecoder(HoconDecoder[Decimal]):
    def decode(self, hocon: HoconValue) -> TOrError[Decimal]:
        if isinstance(hocon, Decimal):
            return Boxed(hocon)
        elif isinstance(hocon, (float, int, str)):
            try:
                return Boxed(Decimal(hocon))
            except DecimalException:
                return [HoconDecodeErrorFinal(f"Value not convertible to decimal: '{hocon}'.")]

        return [HoconDecodeErrorFinal(f"Expected a number but received something of type {type(hocon)}.")]


@dataclass
class HoconBooleanDecoder(HoconDecoder[bool]):
    def decode(self, hocon: HoconValue) -> TOrError[bool]:
        if isinstance(hocon, bool):
            return Boxed(hocon)
        elif isinstance(hocon, int):
            if hocon == 1:
                return Boxed(True)
            if hocon == 0:
                return Boxed(False)
            return [HoconDecodeErrorFinal(f"Received an integer other than 0 or 1 for a Boolean type (value={hocon}).")]
        elif isinstance(hocon, str):
            value = hocon.lower()
            if value in ["y", "yes", "true"]:
                return Boxed(True)
            if value in ["n", "no", "false"]:
                return Boxed(False)
            return [HoconDecodeErrorFinal(f"Expected a Boolean value but received a string with value={hocon}.")]
        return [HoconDecodeErrorFinal(f"Expected a Boolean value but received a value of type {type(hocon)}.")]


hocon_string_decoder = HoconStringDecoder()
hocon_number_decoder = HoconNumberDecoder()


@dataclass
class HoconIntegerDecoder(HoconDecoder[int]):
    def decode(self, hocon: HoconValue) -> TOrError[int]:
        decimal_or_error = hocon_number_decoder.decode(hocon)
        if isinstance(decimal_or_error, Boxed):
            d = decimal_or_error.t
            if int(d) == d:
                return Boxed(int(d))
            else:
                return [HoconDecodeErrorFinal(f"Expected an integral number but received number {d}.")]
        else:
            return decimal_or_error


@dataclass
class HoconDateDecoder(HoconDecoder[date]):
    def decode(self, hocon: HoconValue) -> TOrError[date]:
        string_or_error = hocon_string_decoder.decode(hocon)
        if isinstance(string_or_error, Boxed):
            s = string_or_error.t
            try:
                return Boxed(parser.isoparse(s).date())
            except ValueError:
                return [HoconDecodeErrorFinal(f"Expected a string representing a date but received '{s}'.")]
        else:
            return string_or_error


@dataclass
class HoconDatetimeDecoder(HoconDecoder[datetime]):
    def decode(self, hocon: HoconValue) -> TOrError[datetime]:
        string_or_error = hocon_string_decoder.decode(hocon)
        if isinstance(string_or_error, Boxed):
            s = string_or_error.t
            try:
                return Boxed(parser.isoparse(s))
            except ValueError:
                return [HoconDecodeErrorFinal(f"Expected a string representing a datetime but received '{s}'.")]
        else:
            return string_or_error


@dataclass
class HoconEnumDecoder(HoconDecoder[T]):
    enum_name: str
    enum_values: Dict[str, T]

    def decode(self, hocon: HoconValue) -> TOrError[T]:
        string_or_error = hocon_string_decoder.decode(hocon)
        if isinstance(string_or_error, Boxed):
            s = string_or_error.t
            enum_value = self.enum_values.get(s)
            if enum_value is None:
                return [HoconDecodeErrorFinal(f"Unexpected value {s} while deserializing enum {self.enum_name}.")]
            else:
                return Boxed(enum_value)
        else:
            return string_or_error


@dataclass
class HoconNoneDecoder(HoconDecoder[None]):
    def decode(self, hocon: HoconValue) -> TOrError[None]:
        return Boxed(None)


@dataclass
class HoconAnyDecoder(HoconDecoder[Any]):
    """
    UNSAFE: Avoid using this class as much as possible.
    Returns the raw hocon for cases where the structure of Hocon is not known in advance.
    Does not do any validation and, so, errors are possible if the input is not valid JSON.
    """
    def decode(self, hocon: HoconValue) -> TOrError[Any]:
        return Boxed(hocon)


class AutoHoconDecoder(Extractor[HoconDecoder[Any]]):
    hocon_boolean_decoder = HoconBooleanDecoder()
    hocon_integer_decoder = HoconIntegerDecoder()
    hocon_date_decoder = HoconDateDecoder()
    hocon_datetime_decoder = HoconDatetimeDecoder()

    basic_hocon_decoders: Dict[type, Boxed[HoconDecoder[Any]]] = {
        bool: Boxed(hocon_boolean_decoder),
        str: Boxed(hocon_string_decoder),
        int: Boxed(hocon_integer_decoder),
        Decimal: Boxed(hocon_number_decoder),
        datetime: Boxed(hocon_datetime_decoder),
        date: Boxed(hocon_date_decoder),
        type(None): Boxed(cast(HoconDecoder[Any], HoconNoneDecoder))
    }

    def __init__(self, enable_any: bool = False) -> None:
        super().__init__()
        if enable_any:
            self.add_special(Any, HoconAnyDecoder())

    @property
    def basics(self) -> Dict[type, Boxed[HoconDecoder[Any]]]:
        return self.basic_hocon_decoders

    def named_product_extractor(self, t: type, fields: Dict[str, WithDefault[HoconDecoder[Any]]]) -> HoconDecoder[Any]:
        field_decoders: Dict[str, HoconDecoder[Any]] = {
            n: v.t for (n, v) in fields.items()
        }
        field_defaults: Dict[str, Union[Boxed[Any], Callable[[], Any]]] = {
            n: v.default for (n, v) in fields.items() if v.default is not None
        }

        return HoconObjectDecoder(
            field_decoders=field_decoders,
            field_defaults=field_defaults,
            constructor=lambda args: t(**args),
        )

    def unnamed_product_extractor(self, t: type, fields: List[HoconDecoder[Any]]) -> HoconDecoder[Tuple[Any, ...]]:
        return HoconTupleDecoder(fields)

    def named_sum_extractor(self, t: type, branches: Dict[str, Tuple[type, HoconDecoder[Any]]]) -> HoconDecoder[Any]:
        return HoconTaggedDecoder(
            branch_decoders={s: t for (s, (_, t)) in branches.items()},
            tag_field_name=t.__name__, value_field_name=None
        )

    def unnamed_sum_extractor(self, t: type, branches: List[Tuple[type, HoconDecoder[Any]]]) -> HoconDecoder[Any]:
        return HoconPriorityDecoder([d for (_, d) in branches])

    def optional_extractor(self, t: HoconDecoder[T]) -> HoconDecoder[Optional[T]]:
        return HoconOptionalDecoder(t)

    def list_extractor(self, t: HoconDecoder[T]) -> HoconDecoder[List[T]]:
        return HoconListDecoder(t)

    def dictionary_extractor(
        self,
        key: type,
        value: type,
        key_ext: HoconDecoder[Any],
        val_ext: HoconDecoder[Any]
    ) -> HoconDecoder[Dict[Any, Any]]:
        def to_enum_dict(d: Dict[str, Any]) -> TOrError[Dict[Any, Any]]:
            result: Dict[Any, Any] = {}
            errors: List[HoconDecodeError] = []
            for k, v in d.items():
                e_or_error = cast(TOrError[Enum], key_ext.decode(k))
                if isinstance(e_or_error, Boxed):
                    result[e_or_error.t] = v
                else:
                    errors.extend(e_or_error)

            if len(errors) > 0:
                return errors
            return Boxed(result)

        if key is str:
            return HoconStringDictionaryDecoder(val_ext)
        if issubclass(key, Enum):
            return HoconFlatMappedDecoder(HoconStringDictionaryDecoder(val_ext), to_enum_dict)
        raise NotImplementedError()

    def enum_extractor(self, enum_name: str, enum_values: List[Tuple[str, Any]]) -> HoconDecoder[Any]:
        return HoconEnumDecoder(enum_name, {n: v for (n, v) in enum_values})


@dataclass
class AutoHoconDecodingConfig:
    enable_any: bool = False

    def build(self) -> AutoHoconDecoder:
        return AutoHoconDecoder(enable_any=self.enable_any)
