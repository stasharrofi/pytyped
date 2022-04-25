from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import DecimalException
from enum import Enum

from dateutil import parser as dateutil_parser
from decimal import Decimal
from typing import cast, Any, Callable, Dict, Generic, List, Optional, Tuple, TypeVar, Union

from pyhocon import ConfigFactory, ConfigTree
from pytyped.macros.boxed import Boxed
from pytyped.macros.extractor import Extractor
from pytyped.macros.extractor import WithDefault


HoconValue = Union[None, bool, int, float, Decimal, str, List[Any], ConfigTree]


class HoconParseError(metaclass=ABCMeta):
    @abstractmethod
    def get_message(self) -> str:
        pass

    def to_string(self) -> str:
        return "Error when parsing HOCON: " + self.get_message()


@dataclass
class HoconParseErrorFinal(HoconParseError):
    message: str

    def get_message(self) -> str:
        return ": " + self.message


@dataclass
class HoconParseErrorInField(HoconParseError):
    field_name: str
    error: HoconParseError

    def get_message(self) -> str:
        return "." + self.field_name + self.error.get_message()


@dataclass
class HoconParseErrorInArray(HoconParseError):
    index: int
    error: HoconParseError

    def get_message(self) -> str:
        return "[" + str(self.index) + "]" + self.error.get_message()


class HoconParseException(Exception):
    errors: List[HoconParseError]

    def __init__(self, errors: List[HoconParseError]) -> None:
        self.errors = errors

    def __str__(self) -> str:
        return "Found %d errors while validating JSON: [\n  %s]" % (
            len(self.errors),
            ",\n  ".join([e.to_string() for e in self.errors]),
        )


T = TypeVar("T")
TOrError = Union[Boxed[T], List[HoconParseError]]


class HoconParser(Generic[T], metaclass=ABCMeta):
    @classmethod
    def parses_none(cls) -> bool:
        """
        Returns true if the parser is able to deal with `None` values.
        """
        return False

    @abstractmethod
    def parse(self, hocon: HoconValue) -> TOrError[T]:
        pass

    def from_hocon(self, hocon: HoconValue, root: Optional[str] = None) -> T:
        if root is not None:
            hocon = hocon[root]
        t_or_error = self.parse(hocon)
        if isinstance(t_or_error, Boxed):
            return t_or_error.t
        else:
            raise HoconParseException(t_or_error)

    def from_file(self, file_path: str, root: Optional[str] = None) -> T:
        return self.from_hocon(ConfigFactory.parse_file(file_path), root)

    def from_string(self, conf: str, root: Optional[str] = None) -> T:
        return self.from_hocon(ConfigFactory.parse_string(conf), root)


@dataclass
class HoconObjectParser(HoconParser[T]):
    field_parsers: Dict[str, HoconParser[Any]]
    field_defaults: Dict[str, Union[Boxed[Any], Callable[[], Any]]]
    constructor: Callable[[Dict[str, Any]], T]

    def parse(self, hocon: HoconValue) -> TOrError[T]:
        if not isinstance(hocon, ConfigTree):
            return [
                HoconParseErrorFinal(f"Expected a Hocon config tree but received something of type {type(hocon)}.")
            ]
        parsed_fields: Dict[str, Any] = {}
        parsing_errors: List[HoconParseError] = []
        for field_name, field_parser in self.field_parsers.items():
            field_hocon = hocon.get(field_name, default=None)
            if field_hocon is None:
                if field_parser.parses_none():
                    parsed_field_value = field_parser.parse(None)
                    if isinstance(parsed_field_value, Boxed):
                        parsed_fields[field_name] = parsed_field_value.t
                    else:
                        parsing_errors.extend(HoconParseErrorInField(field_name, err) for err in parsed_field_value)
                elif field_name in self.field_defaults:
                    def_or_fac = self.field_defaults[field_name]
                    parsed_fields[field_name] = def_or_fac.t if isinstance(def_or_fac, Boxed) else def_or_fac()
                else:
                    parsing_errors.append(
                        HoconParseErrorInField(field_name, HoconParseErrorFinal("Non-optional field was not found"))
                    )
            else:
                parsed_field = field_parser.parse(field_hocon)
                if isinstance(parsed_field, Boxed):
                    parsed_fields[field_name] = parsed_field.t
                else:
                    parsing_errors.extend([HoconParseErrorInField(field_name, err) for err in parsed_field])

        if len(parsing_errors) > 0:
            return parsing_errors
        else:
            return Boxed(self.constructor(parsed_fields))


@dataclass
class HoconTupleParser(HoconParser[Tuple[Any, ...]]):
    field_parsers: List[HoconParser[Any]]

    def parse(self, hocon: HoconValue) -> TOrError[Tuple[Any, ...]]:
        if not isinstance(hocon, list):
            return [HoconParseErrorFinal(f"Expected a Hocon array but received something of type {type(hocon)}.")]
        if len(hocon) != len(self.field_parsers):
            return [HoconParseErrorFinal(
                f"Expected a HOCON array of size {len(self.field_parsers)} but received one of size {len(hocon)}."
            )]

        parsed_fields: List[Any] = []
        parsing_errors: List[HoconParseError] = []
        for index, field_parser in enumerate(self.field_parsers):
            # The field_name is a key and its associated value is not None. So, it should be parsed.
            field_hocon = cast(HoconValue, hocon[index])
            parsed_field = field_parser.parse(field_hocon)
            if isinstance(parsed_field, Boxed):
                parsed_fields.append(parsed_field.t)
            else:
                parsing_errors.extend([HoconParseErrorInArray(index, err) for err in parsed_field])

        if len(parsing_errors) > 0:
            return parsing_errors
        else:
            return Boxed(tuple(parsed_fields))


@dataclass
class HoconTaggedParser(HoconParser[Any]):
    branch_parsers: Dict[str, HoconParser[Any]]
    tag_field_name: str = "tag"
    value_field_name: Optional[str] = None  # None means the value is in the same object file

    def parse(self, hocon: HoconValue) -> TOrError[T]:
        if not isinstance(hocon, ConfigTree):
            return [HoconParseErrorFinal("Expected a Hocon object but received something else.")]

        tag_value = hocon.get(self.tag_field_name)
        if tag_value is None:
            return [HoconParseErrorInField(
                field_name=self.tag_field_name,
                error=HoconParseErrorFinal(f"Required tag field {self.tag_field_name} not found.")
            )]
        if not isinstance(tag_value, str):
            return [HoconParseErrorInField(
                field_name=self.tag_field_name,
                error=HoconParseErrorFinal(f"Expected tag field {self.tag_field_name} to be a string but found type {type(tag_value)}.")
            )]

        parser = self.branch_parsers.get(tag_value)
        if parser is None:
            return [HoconParseErrorInField(
                field_name=self.tag_field_name,
                error=HoconParseErrorFinal(f"Unknown tag value {tag_value} (possible values are: {', '.join(self.branch_parsers.keys())}).")
            )]

        if self.value_field_name is None:
            return parser.parse(hocon)

        value_field = cast(HoconValue, hocon.get(self.value_field_name))
        return parser.parse(value_field)


@dataclass
class HoconOptionalParser(HoconParser[Optional[T]]):
    inner_parser: HoconParser[T]

    @classmethod
    def parses_none(cls) -> bool:
        return True

    def parse(self, hocon: HoconValue) -> TOrError[Optional[T]]:
        if hocon is None:
            return Boxed(None)
        return self.inner_parser.parse(hocon)


@dataclass
class HoconErrorAsDefaultParser(HoconParser[T]):
    inner_parser: HoconParser[T]
    default: T

    def parse(self, hocon: HoconValue) -> TOrError[T]:
        result = self.inner_parser.parse(hocon)
        if isinstance(result, Boxed):
            return result
        return Boxed(self.default)


@dataclass
class HoconPriorityParser(HoconParser[Any]):
    # Parsers in the order of priority. The head of the list has more priority.
    inner_parsers: List[HoconParser[Any]]

    def parse(self, hocon: HoconValue) -> TOrError[Any]:
        errors: List[HoconParseError] = []
        for inner_parser in self.inner_parsers:
            result = inner_parser.parse(hocon)
            if isinstance(result, Boxed):
                return result
            errors.extend(result)

        return errors


U = TypeVar("U")


@dataclass
class HoconMappedParser(HoconParser[T], Generic[T, U]):
    u_parser: HoconParser[U]
    u_to_t: Callable[[U], T]

    def parse(self, hocon: HoconValue) -> TOrError[T]:
        result = self.u_parser.parse(hocon)
        if isinstance(result, Boxed):
            transformer = cast(Callable[[U], T], self.u_to_t)
            return Boxed(transformer(result.t))
        return result


@dataclass
class HoconFlatMappedParser(HoconParser[T], Generic[T, U]):
    u_parser: HoconParser[U]
    u_to_t: Callable[[U], TOrError[T]]

    def parse(self, hocon: HoconValue) -> TOrError[T]:
        result = self.u_parser.parse(hocon)
        if isinstance(result, Boxed):
            transformer = cast(Callable[[U], TOrError[T]], self.u_to_t)
            return transformer(result.t)
        return result


@dataclass
class HoconListParser(HoconParser[List[T]]):
    element_parser: HoconParser[T]

    def parse(self, hocon: HoconValue) -> TOrError[List[T]]:
        if not isinstance(hocon, list):
            return [HoconParseErrorFinal(f"Expected a Hocon array but received something of type {type(hocon)}.")]
        parsed_elements: List[Any] = []
        parsing_errors: List[HoconParseError] = []
        for index, element_hocon in enumerate(hocon):
            element_hocon = cast(HoconValue, element_hocon)
            parsed_element = self.element_parser.parse(element_hocon)
            if isinstance(parsed_element, Boxed):
                parsed_elements.append(parsed_element.t)
            else:
                parsing_errors.extend([HoconParseErrorInArray(index, err) for err in parsed_element])

        if len(parsing_errors) > 0:
            return parsing_errors
        else:
            return Boxed(parsed_elements)


@dataclass
class HoconStringDictionaryParser(HoconParser[Dict[str, T]]):
    element_parser: HoconParser[T]

    def parse(self, hocon: HoconValue) -> TOrError[Dict[str, T]]:
        if not isinstance(hocon, ConfigTree):
            return [HoconParseErrorFinal(f"Expected a Hocon config tree but received something of type {type(hocon)}.")]
        parsed_elements: Dict[str, Any] = {}
        parsing_errors: List[HoconParseError] = []
        for key, value_hocon in hocon.items():
            if type(key) is not str:
                parsing_errors.append(HoconParseErrorFinal(f"Found non-string key {key}  with type: {type(key)}."))
            else:
                value_hocon = cast(HoconValue, value_hocon)
                parsed_value = self.element_parser.parse(value_hocon)
                if isinstance(parsed_value, Boxed):
                    parsed_elements[key] = parsed_value.t
                else:
                    parsing_errors.extend([HoconParseErrorInField(key, err) for err in parsed_value])

        if len(parsing_errors) > 0:
            return parsing_errors
        else:
            return Boxed(parsed_elements)


@dataclass
class HoconStringParser(HoconParser[str]):
    def parse(self, hocon: HoconValue) -> TOrError[str]:
        if not isinstance(hocon, str):
            return [HoconParseErrorFinal(f"Expected a string but received something of type {type(hocon)}.")]
        return Boxed(hocon)


@dataclass
class HoconNumberParser(HoconParser[Decimal]):
    def parse(self, hocon: HoconValue) -> TOrError[Decimal]:
        if isinstance(hocon, Decimal):
            return Boxed(hocon)
        elif isinstance(hocon, (float, int, str)):
            try:
                return Boxed(Decimal(hocon))
            except DecimalException:
                return [HoconParseErrorFinal(f"Value not convertible to decimal: '{hocon}'.")]

        return [HoconParseErrorFinal(f"Expected a number but received something of type {type(hocon)}.")]


@dataclass
class HoconBooleanParser(HoconParser[bool]):
    def parse(self, hocon: HoconValue) -> TOrError[bool]:
        if isinstance(hocon, bool):
            return Boxed(hocon)
        elif isinstance(hocon, int):
            if hocon == 1:
                return Boxed(True)
            if hocon == 0:
                return Boxed(False)
            return [HoconParseErrorFinal(f"Received an integer other than 0 or 1 for a Boolean type (value={hocon}).")]
        elif isinstance(hocon, str):
            value = hocon.lower()
            if value in ["y", "yes", "true"]:
                return Boxed(True)
            if value in ["n", "no", "false"]:
                return Boxed(False)
            return [HoconParseErrorFinal(f"Expected a Boolean value but received a string with value={hocon}.")]
        return [HoconParseErrorFinal(f"Expected a Boolean value but received a value of type {type(hocon)}.")]


hocon_string_parser = HoconStringParser()
hocon_number_parser = HoconNumberParser()


@dataclass
class HoconIntegerParser(HoconParser[int]):
    def parse(self, hocon: HoconValue) -> TOrError[int]:
        decimal_or_error = hocon_number_parser.parse(hocon)
        if isinstance(decimal_or_error, Boxed):
            d = decimal_or_error.t
            if int(d) == d:
                return Boxed(int(d))
            else:
                return [HoconParseErrorFinal(f"Expected an integral number but received number {d}.")]
        else:
            return decimal_or_error


@dataclass
class HoconDateParser(HoconParser[date]):
    def parse(self, hocon: HoconValue) -> TOrError[date]:
        string_or_error = hocon_string_parser.parse(hocon)
        if isinstance(string_or_error, Boxed):
            s = string_or_error.t
            try:
                return Boxed(dateutil_parser.isoparse(s).date())
            except ValueError:
                return [HoconParseErrorFinal(f"Expected a string representing a date but received '{s}'.")]
        else:
            return string_or_error


@dataclass
class HoconDatetimeParser(HoconParser[datetime]):
    def parse(self, hocon: HoconValue) -> TOrError[datetime]:
        string_or_error = hocon_string_parser.parse(hocon)
        if isinstance(string_or_error, Boxed):
            s = string_or_error.t
            try:
                return Boxed(dateutil_parser.isoparse(s))
            except ValueError:
                return [HoconParseErrorFinal(f"Expected a string representing a datetime but received '{s}'.")]
        else:
            return string_or_error


@dataclass
class HoconEnumParser(HoconParser[T]):
    enum_name: str
    enum_values: Dict[str, T]

    def parse(self, hocon: HoconValue) -> TOrError[T]:
        string_or_error = hocon_string_parser.parse(hocon)
        if isinstance(string_or_error, Boxed):
            s = string_or_error.t
            enum_value = self.enum_values.get(s)
            if enum_value is None:
                return [HoconParseErrorFinal(f"Unexpected value {s} while deserializing enum {self.enum_name}.")]
            else:
                return Boxed(enum_value)
        else:
            return string_or_error


@dataclass
class HoconNoneParser(HoconParser[None]):
    def parse(self, hocon: HoconValue) -> TOrError[None]:
        return Boxed(None)


@dataclass
class HoconAnyParser(HoconParser[Any]):
    """
    UNSAFE: Avoid using this class as much as possible.
    Returns the raw hocon for cases where the structure of Hocon is not known in advance.
    Does not do any validation and, so, errors are possible if the input is not valid JSON.
    """
    def parse(self, hocon: HoconValue) -> TOrError[Any]:
        return Boxed(hocon)


class AutoHoconParser(Extractor[HoconParser[Any]]):
    hocon_boolean_parser = HoconBooleanParser()
    hocon_integer_parser = HoconIntegerParser()
    hocon_date_parser = HoconDateParser()
    hocon_datetime_parser = HoconDatetimeParser()

    basic_hocon_parsers: Dict[type, Boxed[HoconParser[Any]]] = {
        bool: Boxed(hocon_boolean_parser),
        str: Boxed(hocon_string_parser),
        int: Boxed(hocon_integer_parser),
        Decimal: Boxed(hocon_number_parser),
        datetime: Boxed(hocon_datetime_parser),
        date: Boxed(hocon_date_parser),
        type(None): Boxed(cast(HoconParser[Any], HoconNoneParser))
    }

    def __init__(self, enable_any: bool = False) -> None:
        super().__init__()
        if enable_any:
            self.add_special(Any, HoconAnyParser())

    @property
    def basics(self) -> Dict[type, Boxed[HoconParser[Any]]]:
        return self.basic_hocon_parsers

    def named_product_extractor(self, t: type, fields: Dict[str, WithDefault[HoconParser[Any]]]) -> HoconParser[Any]:
        field_parsers: Dict[str, HoconParser[Any]] = {
            n: v.t for (n, v) in fields.items()
        }
        field_defaults: Dict[str, Union[Boxed[Any], Callable[[], Any]]] = {
            n: v.default for (n, v) in fields.items() if v.default is not None
        }

        return HoconObjectParser(
            field_parsers=field_parsers,
            field_defaults=field_defaults,
            constructor=lambda args: t(**args),
        )

    def unnamed_product_extractor(self, t: type, fields: List[HoconParser[Any]]) -> HoconParser[Tuple[Any, ...]]:
        return HoconTupleParser(fields)

    def named_sum_extractor(self, t: type, branches: Dict[str, Tuple[type, HoconParser[Any]]]) -> HoconParser[Any]:
        return HoconTaggedParser(
            branch_parsers={s: t for (s, (_, t)) in branches.items()},
            tag_field_name=t.__name__, value_field_name=None
        )

    def unnamed_sum_extractor(self, t: type, branches: List[Tuple[type, HoconParser[Any]]]) -> HoconParser[Any]:
        return HoconPriorityParser([d for (_, d) in branches])

    def optional_extractor(self, t: HoconParser[T]) -> HoconParser[Optional[T]]:
        return HoconOptionalParser(t)

    def list_extractor(self, t: HoconParser[T]) -> HoconParser[List[T]]:
        return HoconListParser(t)

    def dictionary_extractor(
        self,
        key: type,
        value: type,
        key_ext: HoconParser[Any],
        val_ext: HoconParser[Any]
    ) -> HoconParser[Dict[Any, Any]]:
        def to_enum_dict(d: Dict[str, Any]) -> TOrError[Dict[Any, Any]]:
            result: Dict[Any, Any] = {}
            errors: List[HoconParseError] = []
            for k, v in d.items():
                e_or_error = cast(TOrError[Enum], key_ext.parse(k))
                if isinstance(e_or_error, Boxed):
                    result[e_or_error.t] = v
                else:
                    errors.extend(e_or_error)

            if len(errors) > 0:
                return errors
            return Boxed(result)

        if key is str:
            return HoconStringDictionaryParser(val_ext)
        if issubclass(key, Enum):
            return HoconFlatMappedParser(HoconStringDictionaryParser(val_ext), to_enum_dict)
        raise NotImplementedError()

    def enum_extractor(self, enum_name: str, enum_values: List[Tuple[str, Any]]) -> HoconParser[Any]:
        return HoconEnumParser(enum_name, {n: v for (n, v) in enum_values})


@dataclass
class AutoHoconParsingConfig:
    enable_any: bool = False

    def build(self) -> AutoHoconParser:
        return AutoHoconParser(enable_any=self.enable_any)
