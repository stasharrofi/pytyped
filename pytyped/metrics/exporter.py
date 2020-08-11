from abc import ABCMeta
from abc import abstractmethod
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from typing import Dict
from typing import Generic
from typing import List
from typing import NamedTuple
from typing import Optional
from typing import Tuple
from typing import TypeVar
from typing import Union
from typing import cast

from pytyped.macros.boxed import Boxed
from pytyped.macros.extractor import Extractor
from pytyped.macros.extractor import WithDefault
from pytyped.metrics.common import MetricsBranch
from pytyped.metrics.common import MetricsLeaf
from pytyped.metrics.common import MetricsNone
from pytyped.metrics.common import MetricsTags
from pytyped.metrics.common import MetricsTree

T = TypeVar("T")


class MetricsExporter(Generic[T], metaclass=ABCMeta):
    @abstractmethod
    def outer_tags(self, names: List[str], t: T) -> Dict[str, str]:
       pass

    @abstractmethod
    def export(self, names: List[str], t: T) -> MetricsTree:
        pass


@dataclass
class ValueExporter(MetricsExporter[Union[int, float, Decimal]]):
    def outer_tags(self, names: List[str], t: Union[int, float, Decimal]) -> Dict[str, str]:
        return {}

    def export(self, names: List[str], t: Union[int, float, Decimal]) -> MetricsTree:
        return MetricsLeaf(".".join(names), t)


@dataclass
class TagExporter(MetricsExporter[str]):
    def outer_tags(self, names: List[str], t: str) -> Dict[str, str]:
        return {".".join(names): t}

    def export(self, names: List[str], t: str) -> MetricsTree:
        return MetricsNone()


@dataclass
class BooleanExporter(MetricsExporter[bool]):
    def outer_tags(self, names: List[str], t: bool) -> Dict[str, str]:
        return {".".join(names): "yes" if t else "no"}

    def export(self, names: List[str], t: bool) -> MetricsTree:
        return MetricsNone()


class DateExporter(MetricsExporter[date]):
    _weekday_names: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def outer_tags(self, names: List[str], t: date) -> Dict[str, str]:
        name = ".".join(names)
        return {
            name + "_day": str(t.day),
            name + "_month": str(t.month),
            name + "_year": str(t.year),
            name + "_weekday": DateExporter._weekday_names[t.weekday()]
        }

    def export(self, names: List[str], t: T) -> MetricsTree:
        return MetricsNone()


class DateTimeExporter(MetricsExporter[datetime]):
    _date_exporter: DateExporter = DateExporter()

    def outer_tags(self, names: List[str], t: datetime) -> Dict[str, str]:
        tags = self._date_exporter.outer_tags(names, t.date())
        tags[".".join(names) + "_hour"] = str(t.hour)

        return tags

    def export(self, names: List[str], t: datetime) -> MetricsTree:
        return MetricsNone()


@dataclass
class NamedProductExporter(MetricsExporter[T]):
    field_exporters: Dict[str, MetricsExporter[Any]]

    def outer_tags(self, names: List[str], t: T) -> Dict[str, str]:
        return {}

    def export(self, names: List[str], t: T) -> MetricsTree:
        d: Dict[str, Any]
        if hasattr(t, "_asdict"):
            d = cast(NamedTuple, t)._asdict()
        else:
            d = t.__dict__

        tags: Dict[str, str] = {}
        for field_name, field_exporter in self.field_exporters.items():
            tags.update(field_exporter.outer_tags(names + [field_name], d[field_name]))

        result: MetricsTree = MetricsBranch([
            field_exporter.export(names + [field_name], d[field_name])
            for field_name, field_exporter in self.field_exporters.items()
        ])
        if len(tags) > 0:
            result = MetricsTags(tags, result)

        return result


@dataclass
class TupleExporter(MetricsExporter[Tuple[Any, ...]]):
    exporters: List[MetricsExporter[Any]]

    def outer_tags(self, names: List[str], t: Tuple[Any, ...]) -> Dict[str, str]:
        return {}

    def export(self, names: List[str], t: Tuple[Any, ...]) -> MetricsTree:
        return MetricsBranch([e.export(names, v) for v, e in zip(t, self.exporters)])


@dataclass
class ListExporter(MetricsExporter[List[T]]):
    inner_exporter: MetricsExporter[T]

    def outer_tags(self, names: List[str], t: List[T]) -> Dict[str, str]:
        return {}

    def export(self, names: List[str], t: List[T]) -> MetricsTree:
        return MetricsBranch([self.inner_exporter.export(names, v) for v in t])


@dataclass
class TaggedExporter(MetricsExporter[T]):
    branches: Dict[str, Tuple[type, MetricsExporter[Any]]]
    tag_tag: str

    def outer_tags(self, names: List[str], t: T) -> Dict[str, str]:
        return {}

    def export(self, names: List[str], t: T) -> MetricsTree:
        for branch_name, (branch_type, exporter) in self.branches.items():
            if isinstance(t, branch_type):
                exported_value: MetricsTree = exporter.export(names, t)
                return MetricsTags({".".join(names + [self.tag_tag]): branch_name}, exported_value)

        return MetricsNone()


@dataclass
class PriorityExporter(MetricsExporter[T]):
    branches: List[Tuple[type, MetricsExporter[Any]]]

    def outer_tags(self, names: List[str], t: T) -> Dict[str, str]:
        return {}

    def export(self, names: List[str], t: T) -> MetricsTree:
        for branch_type, exporter in self.branches:
            if isinstance(t, branch_type):
                return exporter.export(names, t)

        return MetricsNone()


@dataclass
class OptionalExporter(MetricsExporter[Optional[T]]):
    exporter: MetricsExporter[T]

    def outer_tags(self, names: List[str], t: Optional[T]) -> Dict[str, str]:
        return {".".join(names) + "_present": "no" if t is None else "yes"}

    def export(self, names: List[str], t: Optional[T]) -> MetricsTree:
        return MetricsNone() if t is None else self.exporter.export(names, t)


@dataclass
class StringDictionaryExporter(MetricsExporter[Dict[str, T]]):
    element_exporter: MetricsExporter[T]

    def outer_tags(self, names: List[str], t: Dict[str, T]) -> Dict[str, str]:
        return {}

    def export(self, names: List[str], d: Dict[str, T]) -> MetricsTree:
        name = ".".join(names)
        prev_names = names[:-1]
        return MetricsBranch([MetricsTags({name: k}, self.element_exporter.export(prev_names, v)) for k, v in d.items()])


@dataclass
class EnumExporter(MetricsExporter[Enum]):
    def outer_tags(self, names: List[str], t: Enum) -> Dict[str, str]:
        return {".".join(names): str(t.value)}

    def export(self, names: List[str], t: Enum) -> MetricsTree:
        return MetricsNone()


class AutoMetricExporter(Extractor[MetricsExporter[Any]]):
    _enum_exporter = EnumExporter()
    _basics: Dict[type, Boxed[MetricsExporter[Any]]] = {
        bool: Boxed(BooleanExporter()),
        int: Boxed(ValueExporter()),
        float: Boxed(ValueExporter()),
        Decimal: Boxed(ValueExporter()),
        str: Boxed(TagExporter()),
        date: Boxed(DateExporter()),
        datetime: Boxed(DateTimeExporter())
    }

    @property
    def basics(self) -> Dict[type, Boxed[MetricsExporter[Any]]]:
        return self._basics

    def named_product_extractor(
        self,
        t: type,
        fields: Dict[str, WithDefault[MetricsExporter[Any]]]
    ) -> MetricsExporter[Any]:
        return NamedProductExporter(field_exporters={f_name: f_exporter.t for f_name, f_exporter in fields.items()})

    def unnamed_product_extractor(self, t: type, fields: List[MetricsExporter[Any]]) -> MetricsExporter[Any]:
        return TupleExporter(fields)

    def named_sum_extractor(
        self,
        t: type,
        branches: Dict[str, Tuple[type, MetricsExporter[Any]]]
    ) -> MetricsExporter[Any]:
        return TaggedExporter(branches=branches, tag_tag=t.__name__)

    def unnamed_sum_extractor(self, t: type, branches: List[Tuple[type, MetricsExporter[Any]]]) -> MetricsExporter[Any]:
        return PriorityExporter(branches=branches)

    def optional_extractor(self, t: MetricsExporter[Any]) -> MetricsExporter[Any]:
        return OptionalExporter(t)

    def list_extractor(self, t: MetricsExporter[Any]) -> MetricsExporter[Any]:
        return ListExporter(t)

    def dictionary_extractor(
        self,
        key: type,
        value: type,
        key_ext: MetricsExporter[Any],
        val_ext: MetricsExporter[Any]
    ) -> MetricsExporter[Any]:
        if key is str:
            return StringDictionaryExporter(val_ext)
        raise NotImplementedError()

    def enum_extractor(self, enum_name: str, enum_values: List[Tuple[str, Any]]) -> MetricsExporter[Any]:
        return self._enum_exporter
