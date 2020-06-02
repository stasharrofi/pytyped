from abc import ABCMeta
from abc import abstractmethod
from dataclasses import Field
from dataclasses import MISSING
from enum import Enum
from dataclasses import dataclass
from typing import FrozenSet
from typing import cast
from typing import Any
from typing import Callable
from typing import Dict
from typing import Generic
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Tuple
from typing import Type
from typing import TypeVar
from typing import Union

from pytyped.macros.boxed import Boxed


@dataclass
class UnknownExtractorException(Exception):
    t: type

    def message(self) -> str:
        return "Automatic extraction not implemented for type %s" % str(self.t)


@dataclass
class ExtractorAssignmentException(Exception):
    assignments: Dict[str, type]
    t: str

    def message(self) -> str:
        return "Automatic extraction not implemented for type %s" % str(self.t)


T = TypeVar("T")
U = TypeVar("U")


@dataclass
class WithDefault(Generic[T]):
    t: T
    default: Optional[Boxed[Any]]

    def map(self, f: Callable[[T], U]) -> "WithDefault[U]":
        return WithDefault(f(self.t), self.default)


FieldType = WithDefault[type]


@dataclass
class UnionDescriptor:
    branches: List[type]  # List of non-None branches
    is_optional: bool  # True if `None` is one of the union branches


class Extractor(Generic[T], metaclass=ABCMeta):
    # Memoized values for types that have already been extracted.
    # Since types can be generic, their relative context are included.
    # So, the mapping for a generic type G[X] would be (G, {X --> A}) --> T[G[A]].
    memoized: Dict[Tuple[type, FrozenSet[Tuple[str, type]]], Boxed[T]]

    # Current context: A mapping from type variable names to their types.
    # Should only be non-empty when a type-extraction is in progress.
    # Not thread-safe.
    _context: Dict[str, type]

    def __init__(self):
        self.memoized = {}
        self._context = {}

    @property
    @abstractmethod
    def basics(self) -> Dict[type, Boxed[T]]:
        # Mapping from X -> T[X] for basic types (usually str, int, bool, float, etc)
        pass

    @abstractmethod
    def product_extractor(self, t: type, fields: Dict[str, WithDefault[T]]) -> T:
        # Given N = {f1: X1, f2: X2, ..., fn: Xn}, T[X1], T[X2], ..., and T[Xn], generates T[N]
        pass

    @abstractmethod
    def sum_extractor(self, t: type, branches: Dict[type, T]) -> T:
        # Given T[X], generates T[Optional[X]]
        pass

    @abstractmethod
    def optional_extractor(self, t: T) -> T:
        # Given T[X], generates T[Optional[X]]
        pass

    @abstractmethod
    def list_extractor(self, t: T) -> T:
        # Given T[X], generates T[List[X]]
        pass

    @abstractmethod
    def enum_extractor(self, enum_name: str, enum_values: List[Tuple[str, Any]]) -> T:
        # Given enum_name: str, and enum_values: Dict[str, E], generates T[E]
        pass

    @staticmethod
    def extract_if_union_type(t: type) -> Optional[UnionDescriptor]:
        """
        :param t: Type that needs to be checked for being optional.
        :return: Returns Boxed(x) if t is Optional[x] and returns None otherwise.
        """
        if not hasattr(t, "__origin__"):
            return None
        if t.__origin__ is not Union:  # type: ignore
            return None
        t = cast(Union, t)
        args: Tuple[type, ...] = cast(Tuple[type, ...], t.__args__)  # type: ignore

        is_optional: bool = False
        branches: List[type] = []
        for inner_type in args:
            if inner_type is type(None):  # noqa: E721
                is_optional = True
            else:
                branches.append(inner_type)

        return UnionDescriptor(branches, is_optional)

    @staticmethod
    def extract_if_named_tuple_type(t: type) -> Optional[Dict[str, FieldType]]:
        """
        :param t: Type that needs to be checked for being a named tuple.
        :return:
           If `t` is a NamedTuple, returns a mapping from `t`'s field names to their types and default values.
           Otherwise, returns None.
        """
        if not hasattr(t, "_field_types"):
            return None

        t = cast(Type[NamedTuple], t)
        fields: Dict[str, FieldType] = {}
        for (f_name, f_type) in t._field_types.items():
            f_default: Optional[Boxed[Any]] = None
            if f_name in t._field_defaults:
                f_default = Boxed(t._field_defaults[f_name])
            fields[f_name] = FieldType(f_type, f_default)
        return fields

    @staticmethod
    def extract_if_dataclass_type(t: type) -> Optional[Dict[str, FieldType]]:
        """
        :param t: Type that needs to be checked for being a dataclass.
        :return:
           If `t` is a dataclass, returns a mapping from `t`'s field names to their types and default values.
           Otherwise, returns None.
        """
        if not hasattr(t, "__dataclass_fields__"):
            return None

        dataclass_fields = cast(Dict[str, Field], t.__dataclass_fields__)  # type: ignore
        fields: Dict[str, FieldType] = {}
        for (field_name, field_definition) in dataclass_fields.items():
            field_default: Optional[Boxed[Any]] = None
            if field_definition.default is not MISSING:
                field_default = Boxed(field_definition.default)
            fields[field_name] = FieldType(field_definition.type, field_default)
        return fields

    @staticmethod
    def extract_if_list_type(t: type) -> Optional[Boxed[type]]:
        """
        :param t: type that needs to be checked for being a list.
        :return: Returns `Boxed(X)` if `t` is the type `List[X]` and returns None otherwise.
        """
        if not hasattr(t, "__origin__"):
            return None
        if t.__origin__ not in [list, List]:  # type: ignore
            return None
        t = cast(Type[List[Any]], t)
        return Boxed(t.__args__[0])  # type: ignore

    @staticmethod
    def apply_assignments(t: type, old_context: Dict[str, type]) -> Dict[str, type]:
        if not hasattr(t, "__origin__"):
            return old_context
        if not hasattr(t, "__args__"):
            return old_context

        origin: type = cast(type, t.__origin__)  # type: ignore
        if not hasattr(origin, "__parameters__"):
            return old_context
        if origin.__parameters__ is None:  # type: ignore
            return old_context

        parameter_names: List[str] = []
        for parameter in origin.__parameters__:  # type: ignore
            parameter_names.append(parameter.__name__)

        new_context: Dict[str, type] = old_context.copy()
        for (parameter_name, arg) in zip(parameter_names, t.__args__):  # type: ignore
            if isinstance(arg, TypeVar):  # type: ignore
                arg_name: str = arg.__name__
                if arg_name not in old_context:
                    raise ExtractorAssignmentException(old_context, arg_name)
                new_context[parameter_name] = old_context[arg_name]
            else:
                new_context[parameter_name] = arg

        return new_context

    @staticmethod
    def or_else(t: Optional[T], f: Callable[[], Optional[T]]) -> Optional[T]:
        if t is None:
            return f()
        return t

    def assignments(self, t: type) -> FrozenSet[Tuple[str, type]]:
        if not hasattr(t, "__parameters__"):
            return frozenset([])

        assignments: Dict[str, type] = {}
        for parameter in t.__parameters__:  # type:ignore
            parameter_name: str = cast(str, parameter.__name__)
            if parameter_name not in self._context:
                raise ExtractorAssignmentException(self._context.copy(), parameter_name)
            assignments[parameter_name] = self._context[parameter_name]

        return frozenset(assignments.items())

    def add_special(self, typ: type, value: T) -> None:
        self.memoized[(typ, self.assignments(typ))] = Boxed(value)

    def _extract_basic_type(self, t: type) -> Optional[Boxed[T]]:
        return self.basics.get(t)

    def _extract_product_type(self, product_type: type) -> Optional[Boxed[T]]:
        maybe_fields = Extractor.extract_if_named_tuple_type(product_type)
        maybe_fields = Extractor.or_else(maybe_fields, lambda: Extractor.extract_if_dataclass_type(product_type))
        if maybe_fields is None:
            return None

        fields: Dict[str, WithDefault[T]] = {
            n: v.map(self._make) for (n, v) in maybe_fields.items()
        }
        return Boxed(self.product_extractor(product_type, fields))

    def _extract_union_type(self, sum_type: type) -> Optional[Boxed[T]]:
        maybe_union_type = Extractor.extract_if_union_type(sum_type)
        if maybe_union_type is None:
            return None

        extracted_branches: Dict[type, T] = {t: self._make(t) for t in maybe_union_type.branches}
        extracted_union: T
        if len(extracted_branches) == 1:
            extracted_branch: List[Tuple[type, T]] = list(extracted_branches.items())
            extracted_union = extracted_branch[0][1]
        else:
            extracted_union = self.sum_extractor(sum_type, extracted_branches)
        if maybe_union_type.is_optional:
            extracted_union = self.optional_extractor(extracted_union)
        return Boxed(extracted_union)

    def _extract_list_type(self, list_type: type) -> Optional[Boxed[T]]:
        maybe_list_type = Extractor.extract_if_list_type(list_type)
        if maybe_list_type is None:
            return None
        return Boxed(self.list_extractor(self._make(maybe_list_type.t)))

    def _extract_enum_type(self, enum_type: type) -> Optional[Boxed[T]]:
        try:
            if not issubclass(enum_type, Enum):
                return None
        except Exception:
            return None

        value_dict = cast(Dict[str, Any], enum_type._value2member_map_)
        value_list = cast(List[Tuple[str, Any]], list(value_dict.items()))
        return Boxed(self.enum_extractor(str(enum_type), value_list))

    def _make(self, t: type) -> T:
        if isinstance(t, TypeVar):  # type: ignore
            t_name: str = cast(str, t.__name__)  # type: ignore
            if t_name not in self._context:
                raise ExtractorAssignmentException(self._context.copy(), t_name)
            t = self._context[t_name]

        result: Optional[Boxed[T]] = self.memoized.get((t, self.assignments(t)))

        old_context = self._context
        self._context = Extractor.apply_assignments(t, self._context)

        result = Extractor.or_else(result, lambda: self._extract_basic_type(t))
        result = Extractor.or_else(result, lambda: self._extract_union_type(t))
        result = Extractor.or_else(result, lambda: self._extract_list_type(t))
        result = Extractor.or_else(result, lambda: self._extract_product_type(t))
        result = Extractor.or_else(result, lambda: self._extract_enum_type(t))

        if result is None:
            raise UnknownExtractorException(t)

        self._context = old_context
        t_assignments = self.assignments(t)
        if (t, t_assignments) not in self.memoized:
            self.memoized[(t, t_assignments)] = result
        return result.t

    def extract(self, in_typ: type) -> T:
        """
        :param in_typ: The type for which meta-programming needs to be initiated (i.e., generate T[in_typ])
        :return: The auto generated value T[in_typ]
        """
        self._context = {}
        result: T = self._make(t=in_typ)
        assert len(self._context) == 0, "Non-empty context at the top level."

        return result
