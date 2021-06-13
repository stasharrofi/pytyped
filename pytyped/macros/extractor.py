from abc import ABCMeta
from abc import abstractmethod
from dataclasses import Field
from dataclasses import MISSING, dataclass, is_dataclass
from enum import Enum
from inspect import isclass
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
from pytyped.macros.pyjack import replace_all_refs


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
    default: Union[None, Boxed[Any], Callable[[], Any]]

    def map(self, f: Callable[[T], U]) -> "WithDefault[U]":
        return WithDefault(f(self.t), self.default)


FieldType = WithDefault[type]


@dataclass
class UnnamedUnionDescriptor:
    branches: List[type]  # List of non-None branches
    is_optional: bool  # True if `None` is one of the union branches


@dataclass
class NamedUnionDescriptor:
    branches: Dict[str, type]  # Mapping of names to branches


@dataclass
class RecursiveTypeApplication:
    ref_count: int
    typ: type
    assignments: FrozenSet[Tuple[str, type]]

class Extractor(Generic[T], metaclass=ABCMeta):
    # Memoized values for types that have already been extracted.
    # Since types can be generic, their relative context are included.
    # So, the mapping for a generic type G[X] would be (G, {X --> A}) --> T[G[A]].
    memoized: Dict[Tuple[type, FrozenSet[Tuple[str, type]]], Boxed[T]]

    # Current context: A mapping from type variable names to their types.
    # Should only be non-empty when a type-extraction is in progress.
    # Not thread-safe.
    _context: Dict[str, type]

    def __init__(self) -> None:
        self.memoized = {}
        self._context = {}

    @property
    @abstractmethod
    def basics(self) -> Dict[type, Boxed[T]]:
        # Mapping from X -> T[X] for basic types (usually str, int, bool, float, etc)
        pass

    @abstractmethod
    def named_product_extractor(self, t: type, fields: Dict[str, WithDefault[T]]) -> T:
        # Given N = {f1: X1, f2: X2, ..., fn: Xn}, T[X1], T[X2], ..., and T[Xn], generates T[N]
        pass

    @abstractmethod
    def unnamed_product_extractor(self, t: type, fields: List[T]) -> T:
        # Given N = {f1: X1, f2: X2, ..., fn: Xn}, T[X1], T[X2], ..., and T[Xn], generates T[N]
        pass

    @abstractmethod
    def named_sum_extractor(self, t: type, branches: Dict[str, Tuple[type, T]]) -> T:
        # Given T[X], generates T[Optional[X]]
        pass

    @abstractmethod
    def unnamed_sum_extractor(self, t: type, branches: List[Tuple[type, T]]) -> T:
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
    def dictionary_extractor(self, key: type, value: type, key_ext: T, val_ext: T) -> T:
        # Given T[X], generates T[List[X]]
        pass

    @abstractmethod
    def enum_extractor(self, enum_name: str, enum_values: List[Tuple[str, Any]]) -> T:
        # Given enum_name: str, and enum_values: Dict[str, E], generates T[E]
        pass

    @staticmethod
    def extract_if_union_type(t: type) -> Optional[UnnamedUnionDescriptor]:
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

        return UnnamedUnionDescriptor(branches, is_optional)

    @staticmethod
    def extract_if_has_sub_classes(t: type) -> Optional[NamedUnionDescriptor]:
        """
        :param t: Type that needs to be checked for being optional.
        :return: Returns Boxed(x) if t is Optional[x] and returns None otherwise.
        """
        if not (isclass(t) or (hasattr(t, "__origin__") and hasattr(t.__origin__, "__args__") and isclass(t.__origin__))):
            return None

        branch_list: List[type]
        if hasattr(t, "__subclasses__"):
            branch_list = t.__subclasses__()
        elif hasattr(t, "__origin__") and hasattr(t.__origin__, "__subclasses__"):
            branch_list = t.__origin__.__subclasses__()
        else:
            return None
        if len(branch_list) <= 0:
            return None

        branches: Dict[str, type] = {}
        for branch in branch_list:
            if not hasattr(branch, "__name__"):
                return None
            branches[branch.__name__] = branch

        return NamedUnionDescriptor(branches)

    @staticmethod
    def extract_if_tuple_type(t: type) -> Optional[List[type]]:
        """
        :param t: Type that needs to be checked for being a named tuple.
        :return:
           If `t` is a Tuple, returns a list of `t`'s field types.
           Otherwise, returns None.
        """
        if not hasattr(t, "__origin__"):
            return None
        if t.__origin__ not in [Tuple, tuple]:  # type: ignore
            return None
        if not hasattr(t, "__args__"):
            return None

        args: Tuple[type, ...] = cast(Tuple[type, ...], t.__args__)  # type: ignore
        inner_types: List[type] = [t for t in args]
        return inner_types

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
        dataclass_fields: Dict[str, Field]
        if is_dataclass(t):
            dataclass_fields = cast(Dict[str, Field], t.__dataclass_fields__)  # type: ignore
        elif hasattr(t, "__origin__") and hasattr(t.__origin__, "__args__") and is_dataclass(t.__origin__):
            dataclass_fields = cast(Dict[str, Field], t.__origin__.__dataclass_fields__)  # type: ignore
        else:
            return None

        fields: Dict[str, FieldType] = {}
        for (field_name, field_definition) in dataclass_fields.items():
            field_default: Union[None, Boxed[Any], Callable[[], Any]] = None
            if field_definition.default is not MISSING:
                field_default = Boxed(field_definition.default)
            elif field_definition.default_factory is not MISSING:  # type: ignore
                field_default = field_definition.default_factory  # type: ignore
            fields[field_name] = FieldType(field_definition.type, field_default)
        return fields

    @staticmethod
    def extract_if_list_type(t: type) -> Union[None, str, Boxed[type]]:
        """
        :param t: type that needs to be checked for being a list.
        :return: Returns `Boxed("X")` if `t` is the type `List[X]` with X being the type variable name used by `List`.
        """
        if not hasattr(t, "__origin__"):
            return None
        origin = cast(type, t.__origin__)  # type: ignore
        if origin is List:
            return origin.__parameters__[0].__name__  # type: ignore
        if origin is list:
            return Boxed(t.__args__[0])  # type: ignore
        return None

    @staticmethod
    def extract_if_dictionary_type(t: type) -> Union[None, Tuple[str, str], Boxed[Tuple[type, type]]]:
        """
        :param t: type that needs to be checked for being a dictionary.
        :return: Returns `Boxed(("X", "Y"))` if `t` is the type `Dict[X, Y]` and X and Y are type variable names
                 for key and value types respectively.
        """
        if not hasattr(t, "__origin__"):
            return None
        origin = cast(type, t.__origin__)  # type: ignore
        if origin is Dict:
            return origin.__parameters__[0].__name__, origin.__parameters__[1].__name__  # type: ignore
        if origin is dict:
            return Boxed((t.__args__[0], t.__args__[1]))  # type: ignore
        return None

    @staticmethod
    def or_else(t: Optional[T], f: Callable[[], Optional[T]]) -> Optional[T]:
        if t is None:
            return f()
        return t

    def assignments(self, t: type) -> Tuple[type, FrozenSet[Tuple[str, type]], Dict[str, type]]:
        new_context = self._context.copy()
        if hasattr(t, "__origin__") and hasattr(t.__origin__, "__parameters__") and hasattr(t, "__args__"):
            t_origin = t.__origin__
            assert len(t.__args__) == len(t_origin.__parameters__)
            for parameter, arg in zip(t_origin.__parameters__, t.__args__):  # type:ignore
                parameter_name: str = cast(str, parameter.__name__)
                if isinstance(arg, TypeVar):  # type: ignore
                    arg_name: str = arg.__name__
                    if arg_name not in self._context:
                        raise ExtractorAssignmentException(self._context, arg_name)
                    new_context[parameter_name] = self._context[arg_name]
                else:
                    if not hasattr(arg, "__parameters__") or len(arg.__parameters__) <= 0:
                        new_context[parameter_name] = arg
                    else:
                        concretized_params_list: List[type] = []
                        for p in arg.__parameters__:
                            p_name = p.__name__
                            p_type = self._context.get(p_name)
                            if p_type is None:
                                raise ExtractorAssignmentException(self._context, p_name)
                            concretized_params_list.append(p_type)
                        concretized_params_tuple = tuple(t for t in concretized_params_list)
                        new_context[parameter_name] = arg[concretized_params_tuple]
        elif not hasattr(t, "__origin__"):
            t_origin = t
        else:
            return t, frozenset(), self._context

        assignments: Dict[str, type] = {}
        if hasattr(t_origin, "__parameters__"):
            for parameter in t_origin.__parameters__:  # type:ignore
                parameter_name: str = cast(str, parameter.__name__)
                parameter_type = new_context.get(parameter_name)
                if parameter_type is None:
                    raise ExtractorAssignmentException(new_context, parameter_name)
                assignments[parameter_name] = parameter_type

        if len(assignments) <= 0:
            return t_origin, frozenset(), self._context

        return t_origin, frozenset(assignments.items()), new_context
 
    def add_special(self, typ: type, value: T) -> None:
        t_origin, t_assignment, _ = self.assignments(typ)
        self.memoized[(t_origin, t_assignment)] = Boxed(value)

    def _var_to_type(self, var_name: str) -> type:
        if var_name not in self._context:
            raise ExtractorAssignmentException(self._context.copy(), var_name)
        list_inner_type = self._context[var_name]
        return list_inner_type

    def _extract_basic_type(self, t: type) -> Optional[Boxed[T]]:
        return self.basics.get(t)

    def _extract_unnamed_product_type(self, product_type: type) -> Optional[Boxed[T]]:
        maybe_fields = Extractor.extract_if_tuple_type(product_type)
        if maybe_fields is None:
            return None

        fields: List[T] = [self._make(t) for t in maybe_fields]
        return Boxed(self.unnamed_product_extractor(product_type, fields))

    def _extract_named_product_type(self, product_type: type) -> Optional[Boxed[T]]:
        maybe_fields = Extractor.extract_if_named_tuple_type(product_type)
        maybe_fields = Extractor.or_else(maybe_fields, lambda: Extractor.extract_if_dataclass_type(product_type))
        if maybe_fields is None:
            return None

        fields: Dict[str, WithDefault[T]] = {
            n: v.map(self._make) for (n, v) in maybe_fields.items()
        }
        return Boxed(self.named_product_extractor(product_type, fields))

    def _extract_unnamed_sum_type(self, sum_type: type) -> Optional[Boxed[T]]:
        maybe_unnamed_sum_type = Extractor.extract_if_union_type(sum_type)
        if maybe_unnamed_sum_type is None:
            return None

        extracted_branches: List[Tuple[type, T]] = [(t, self._make(t)) for t in maybe_unnamed_sum_type.branches]
        extracted_union: T
        if len(extracted_branches) == 1:
            extracted_union = extracted_branches[0][1]
        else:
            extracted_union = self.unnamed_sum_extractor(sum_type, extracted_branches)
        if maybe_unnamed_sum_type.is_optional:
            extracted_union = self.optional_extractor(extracted_union)
        return Boxed(extracted_union)

    def _extract_named_sum_type(self, sum_type: type) -> Optional[Boxed[T]]:
        maybe_named_sum_type = Extractor.extract_if_has_sub_classes(sum_type)
        if maybe_named_sum_type is None:
            return None

        extracted_branches: Dict[str, Tuple[type, T]] = {
            s: (t, self._make(t)) for (s, t) in maybe_named_sum_type.branches.items()
        }
        return Boxed(self.named_sum_extractor(sum_type, extracted_branches))

    def _extract_list_type(self, list_type: type) -> Optional[Boxed[T]]:
        maybe_list_var_name = Extractor.extract_if_list_type(list_type)
        if maybe_list_var_name is None:
            return None

        list_inner_type: type
        if isinstance(maybe_list_var_name, str):
            list_inner_type = self._var_to_type(maybe_list_var_name)
        else:
            list_inner_type = maybe_list_var_name.t

        return Boxed(self.list_extractor(self._make(list_inner_type)))

    def _extract_dictionary_type(self, dict_type: type) -> Optional[Boxed[T]]:
        maybe_dict_vars = Extractor.extract_if_dictionary_type(dict_type)
        if maybe_dict_vars is None:
            return None

        key_type: type
        value_type: type
        if isinstance(maybe_dict_vars, Boxed):
            key_type, value_type = maybe_dict_vars.t
        else:
            (key_var_name, value_var_name) = maybe_dict_vars
            key_type = self._var_to_type(key_var_name)
            value_type = self._var_to_type(value_var_name)

        key_extractor = self._make(key_type)
        value_extractor = self._make(value_type)
        return Boxed(self.dictionary_extractor(key_type, value_type, key_extractor, value_extractor))

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
            t = self._var_to_type(t.__name__)

        t_origin, t_assignments, new_context = self.assignments(t)
        key = (t_origin, t_assignments)
        if key in self.memoized:
            result = self.memoized[key].t
            if isinstance(result, RecursiveTypeApplication):
                result.ref_count = result.ref_count + 1
            return result

        recursion_placeholder = RecursiveTypeApplication(0, t_origin, t_assignments)
        self.memoized[key] = Boxed(recursion_placeholder)

        old_context = self._context
        self._context = new_context

        result: Optional[Boxed[T]] = None
        result = Extractor.or_else(result, lambda: self._extract_basic_type(t_origin))
        result = Extractor.or_else(result, lambda: self._extract_unnamed_sum_type(t_origin))
        result = Extractor.or_else(result, lambda: self._extract_named_sum_type(t_origin))
        result = Extractor.or_else(result, lambda: self._extract_list_type(t_origin))
        result = Extractor.or_else(result, lambda: self._extract_dictionary_type(t_origin))
        result = Extractor.or_else(result, lambda: self._extract_unnamed_product_type(t_origin))
        result = Extractor.or_else(result, lambda: self._extract_named_product_type(t_origin))
        result = Extractor.or_else(result, lambda: self._extract_enum_type(t_origin))

        if result is None:
            raise UnknownExtractorException(t_origin)

        if recursion_placeholder.ref_count > 0:
            replace_all_refs(recursion_placeholder, result.t)
        self._context = old_context
        self.memoized[key] = result
        return result.t

    def extract(self, in_typ: type) -> T:
        """
        :param in_typ: The type for which meta-programming needs to be initiated (i.e., generate T[in_typ])
        :param assumptions: A mapping from type variable names to their assumed generated types. This is useful when
            extracting the type of a generic class without knowing the type of its variables.
        :return: The auto generated value T[in_typ]
        """
        self._context = {}
        result: T = self._make(t=in_typ)
        assert len(self._context) == 0, "Non-empty context at the top level."

        return result
