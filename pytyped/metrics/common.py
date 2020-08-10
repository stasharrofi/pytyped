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
class MetricContext:
    name: str
    properties: Dict[str, str]


@dataclass
class Metric:
    """
        A metric is a contextualized numerical value with contextualized meaning that it has a name,
        a lineage (i.e., a set of ancestors) and tags on each ancestor.
    """
    name: str
    value: Union[int, float, Decimal]
    lineage: List[MetricContext]  # The first value in the list is considered to be the parent


class MetricsTree(metaclass=ABCMeta):
    pass


class MetricsTreeFinal(MetricsTree, metaclass=ABCMeta):
    pass


@dataclass
class MetricsTag(MetricsTreeFinal):
    postfix: Optional[str]
    value: str

    def full_name(self, name: str) -> str:
        return name + ("" if self.postfix is None else self.postfix)


@dataclass
class MetricsLeaf(MetricsTreeFinal):
    value: Union[int, float, Decimal]


class MetricsTreeInternal(MetricsTree, metaclass=ABCMeta):
    @abstractmethod
    def to_metrics(self, name: str) -> List[Metric]:
        pass


@dataclass
class MetricsUnnamedCollection(MetricsTreeInternal):
    children: List[MetricsTree]

    def to_tags(self, name: str) -> Dict[str, str]:
        return {tag.full_name(name): tag.value for tag in self.children if isinstance(tag, MetricsTag)}

    def to_metrics(self, name: str) -> List[Metric]:
        leaf_metrics: List[Metric] = [
            Metric(name=name, value=child.value, lineage=[])
            for child in self.children
            if isinstance(child, MetricsLeaf)
        ]

        children_metrics: List[Metric] = list(itertools.chain.from_iterable([
            child.to_metrics(name) for child in self.children if isinstance(child, MetricsTreeInternal)
        ]))

        return leaf_metrics + children_metrics


@dataclass
class MetricsNamedCollection(MetricsTreeInternal):
    children: Dict[str, MetricsTree]

    def to_metrics(self, name: str) -> List[Metric]:
        props: Dict[str, str] = {}
        for l_name, l in self.children.items():
            if isinstance(l, MetricsUnnamedCollection):
                props.update(l.to_tags(l_name))
        props.update({
            tag.full_name(tag_name): tag.value for tag_name, tag in self.children.items() if isinstance(tag, MetricsTag)
        })

        context = MetricContext(name=name, properties=props)

        leaf_metrics: List[Metric] = [
            Metric(name=child_name, value=child.value, lineage=[context])
            for child_name, child in self.children.items()
            if isinstance(child, MetricsLeaf)
        ]

        children_metrics: List[Metric] = list(itertools.chain.from_iterable([
            child.to_metrics(child_name)
            for child_name, child in self.children.items()
            if isinstance(child, MetricsTreeInternal)
        ]))
        for m in children_metrics:
            m.lineage.append(context)

        return leaf_metrics + children_metrics
