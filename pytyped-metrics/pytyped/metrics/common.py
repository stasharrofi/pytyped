import itertools
from abc import ABCMeta
from abc import abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union


@dataclass
class Metric:
    """
        A metric is a contextualized numerical value with contextualized meaning that it has a name,
        a lineage (i.e., a set of ancestors) and tags on each ancestor.
    """
    name: str
    value: Union[int, float, Decimal]
    tags: Dict[str, str]  # The first value in the list is considered to be the parent


class MetricsTree(metaclass=ABCMeta):
    @abstractmethod
    def to_metrics(self, tag_context: Dict[str, str]) -> List[Metric]:
        pass


@dataclass
class MetricsNone(MetricsTree):
    def to_metrics(self, tag_context: Dict[str, str]) -> List[Metric]:
        return []


@dataclass
class MetricsLeaf(MetricsTree):
    name: str
    value: Union[int, float, Decimal]

    def to_metrics(self, tag_context: Dict[str, str]) -> List[Metric]:
        return [Metric(self.name, self.value, tag_context)]


@dataclass
class MetricsTags(MetricsTree):
    tags: Dict[str, str]
    internal: MetricsTree

    def to_metrics(self, tag_context: Dict[str, str]) -> List[Metric]:
        tag_context = tag_context.copy()
        tag_context.update(self.tags)
        return self.internal.to_metrics(tag_context)


@dataclass
class MetricsBranch(MetricsTree):
    children: List[MetricsTree]

    def to_metrics(self, tag_context: Dict[str, str]) -> List[Metric]:
        return [m for child in self.children for m in child.to_metrics(tag_context)]
