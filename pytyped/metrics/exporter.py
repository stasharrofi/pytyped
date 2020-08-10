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
from pytyped.metrics.common import MetricsLeaf
from pytyped.metrics.common import MetricsNamedCollection
from pytyped.metrics.common import MetricsTag
from pytyped.metrics.common import MetricsTree
from pytyped.metrics.common import MetricsUnnamedCollection

T = TypeVar("T")


class MetricsExporter(Generic[T], metaclass=ABCMeta):
    @abstractmethod
    def export(self, t: T) -> MetricsTree:
        pass


@dataclass
class ValueExporter(MetricsExporter[Union[int, float, Decimal]]):
    def export(self, t: Union[int, float, Decimal]) -> MetricsTree:
        return MetricsLeaf(t)


@dataclass
class TagExporter(MetricsExporter[str]):
    def export(self, t: str) -> MetricsTree:
        return MetricsTag(None, t)


@dataclass
class BooleanExporter(MetricsExporter[bool]):
    def export(self, t: bool) -> MetricsTree:
        return MetricsTag(None, "yes" if t else "no")


class DateExporter(MetricsExporter[date]):
    _weekday_names: List[str] = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def export(self, t: date) -> MetricsTree:
        return MetricsUnnamedCollection([
            MetricsTag("_day", str(t.day)),
            MetricsTag("_month", str(t.month)),
            MetricsTag("_year", str(t.year)),
            MetricsTag("_weekday", DateExporter._weekday_names[t.weekday()]),
        ])


class DateTimeExporter(MetricsExporter[datetime]):
    _date_exporter: DateExporter = DateExporter()

    def export(self, t: datetime) -> MetricsTree:
        tags = DateTimeExporter._date_exporter.export(t.date())
        assert isinstance(tags, MetricsUnnamedCollection)

        tags.children.append(MetricsTag("_hour", str(t.hour)))

        return tags


@dataclass
class NamedProductExporter(MetricsExporter[T]):
    field_exporters: Dict[str, MetricsExporter[Any]]

    def export(self, t: T) -> MetricsTree:
        d: Dict[str, Any]
        if hasattr(t, "_asdict"):
            d = cast(NamedTuple, t)._asdict()
        else:
            d = t.__dict__

        return MetricsNamedCollection({
            field_name: field_exporter.export(d[field_name])
            for field_name, field_exporter in self.field_exporters.items()
        })


@dataclass
class TupleExporter(MetricsExporter[Tuple[Any, ...]]):
    exporters: List[MetricsExporter[Any]]

    def export(self, t: Tuple[Any, ...]) -> MetricsTree:
        return MetricsUnnamedCollection([e.export(v) for v, e in zip(t, self.exporters)])


@dataclass
class ListExporter(MetricsExporter[List[T]]):
    inner_exporter: MetricsExporter[T]

    def export(self, t: List[T]) -> MetricsTree:
        return MetricsUnnamedCollection([self.inner_exporter.export(v) for v in t])


@dataclass
class TaggedExporter(MetricsExporter[T]):
    branches: Dict[str, Tuple[type, MetricsExporter[Any]]]
    tag_postfix: Optional[str] = None

    def export(self, t: T) -> MetricsTree:
        for branch_name, (branch_type, exporter) in self.branches.items():
            if isinstance(t, branch_type):
                exported_value: MetricsTree = exporter.export(t)
                return MetricsUnnamedCollection([
                    MetricsTag(self.tag_postfix, branch_name),
                    exported_value
                ])

        return MetricsUnnamedCollection([])


@dataclass
class PriorityExporter(MetricsExporter[T]):
    branches: List[Tuple[type, MetricsExporter[Any]]]

    def export(self, t: T) -> MetricsTree:
        for branch_type, exporter in self.branches:
            if isinstance(t, branch_type):
                return exporter.export(t)

        return MetricsUnnamedCollection([])


@dataclass
class OptionalExporter(MetricsExporter[Optional[T]]):
    exporter: MetricsExporter[T]

    def export(self, t: Optional[T]) -> MetricsTree:
        if t is None:
            return MetricsTag("_present", "no")

        return MetricsUnnamedCollection([
            MetricsTag("_present", "yes"),
            self.exporter.export(t)
        ])


@dataclass
class StringDictionaryExporter(MetricsExporter[Dict[str, T]]):
    element_exporter: MetricsExporter[T]

    def export(self, d: Dict[str, T]) -> MetricsTree:
        return MetricsNamedCollection({k: self.element_exporter.export(v) for k, v in d.items()})


@dataclass
class EnumExporter(MetricsExporter[Enum]):
    def export(self, t: Enum) -> MetricsTree:
        return MetricsTag(None, str(t.value))


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
        return TaggedExporter(branches=branches, tag_postfix="_" + t.__name__)

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
