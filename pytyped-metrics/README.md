# pytyped-metrics

`pytyped-metrics` is a Python package that automatically extracts `statsd`-style metrics for a given Python type.
`pytyped-metrics` is a part of `pytyped` collection and follows its philosophy of using types to automate mundane and repetitive tasks.
Currently, given a type `T`, `pytyped-metrics` automatically extracts a class `MetricsExporter[T]` which takes a value `t: T` and returns a list of metrics to be published to a `statsd`-style metrics collector.

### Installation

You can install `pytyped-metrics` from [PyPI](https://pypi.org/):

```
pip install pytyped-metrics
```

`pytyped-metrics` is checked on `Python 3.6+`.

### Why `pytyped-metrics`?

Metrics are valuable pieces of information in any real-world software and, to our knowledge, `pytyped-metrics` is the only Python package that automatic exporting of metrics based on reasonably-defined types.
Additionally, `pytyped-metrics` is designed to be extensible.
That is, you can define custom metrics exporters for specific types or custom functional types.

Many `statsd`-style metric collectors such as `statsd`, `influxdb`, `prometheus`, and `datadog` define a metric as a numeric value which can have a collection of tags with each tag having a name and a value.
For example, the load of different cores of a CPU can be defined by a metric called `system.cpu.load` and a tag `core_no=x` which defines the load on which core is being reported.

Currently, `pytyped-metrics` supports the following type driven extractions of metric exporters:
- Metric exporting for **basic numeric types** such as `int`, `float`, and `Decimal` (which define a singular metric).
- Metric exporting for **basic non-numeric types** such as `bool`, `date`, `datetime`, and `str` (which define meaningful tags on other metrics)
- Metric exporting for **simple type combinators** such as `List[T]` and `Dict[A, B]`.
- Metric exporting for **named product types** such as `NamedTuple`s or `dataclass`es.
- Metric exporting for **anonymous product types** such as `Tuple[T1, T2, ...]`.
- Metric exporting for **anonymous union types** such as `Optional[T]`, `Union[T1, T2, ...]`, etc.
- Metric exporting for **named union types** such as class hierarchies (i.e., when a class `A` has several subclasses `A1`, ..., `An`).
- Metric exporting for **generic types** and type variables.
- Metric exporting for **custom functional types** such as `Set[T]`, `Secret[T]`, etc where a custom function is defined for generic types such as `Set` or `Secret` and that functional is applied to all instantiations of those generic type.
- Metric exporting for **recursive types** such as binary trees, etc.

### Using `pytyped-metrics` to extract metric exporters

First, define your type. For example, in the following we want to define an account that can either be a personal account or a business account.
Each account (personal or business) has a beneficiary owner and a personal account has one currency and possibly multiple banking products (checking, saving, etc) but the business account can have both multiple currencies and multiple banking products per currency.

```python
from decimal import Decimal
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


@dataclass
class BankingProductType(Enum):
    Checking = "Checking"
    Saving = "Saving"
    Credit = "Credit card"
    LoC = "Line of Credit"


@dataclass
class BankingProduct:
    type: BankingProductType
    balance: Decimal


@dataclass
class Account:
    owner: str


@dataclass
class PersonalAccount(Account):
    currency: str
    products: List[BankingProduct]


@dataclass
class BusinessAccount(Account):
    currencies: Dict[str, List[BankingProduct]]
```

Second, use an instance of `AutoMetricExporter` to extract a metric exporter for type `Account`:

```python
from pytyped.metrics.exporter import AutoMetricExporter, MetricsExporter

_auto_metric_exporter = AutoMetricExporter()
account_metric_exporter: MetricsExporter[Account] = _auto_metric_exporter.extract(Account)
```

Third, define some instances of the `Account` class:

```python
personal_account = PersonalAccount(
    owner = "John Doe",
    currency = "USD",
    products = [
        BankingProduct(type=BankingProductType.Checking, balance=Decimal(1000)),
        BankingProduct(type=BankingProductType.Credit, balance=Decimal(200))
    ]
)

business_account = BusinessAccount(
    owner = "Doe Ltd.",
    currencies = {
        "USD": [
            BankingProduct(type=BankingProductType.Checking, balance=Decimal(100000)),
            BankingProduct(type=BankingProductType.LoC, balance=Decimal(20000))
        ],
        "EUR": [
            BankingProduct(type=BankingProductType.Checking, balance=Decimal(50000)),
        ],
    }
) 
```

Finally, use `account_metric_exporter` to convert data in your instances to a list of metrics:

```python
>>> account_metric_exporter.export(["account"], personal_account).to_metrics({})
[
    Metric(
        name='account.products.balance',
        value=Decimal('1000'),
        tags={
            'account.Account': 'PersonalAccount',
            'account.owner': 'John Doe',
            'account.currency': 'USD'
        }
    ),
    Metric(
        name='account.products.balance',
        value=Decimal('200'),
        tags={
            'account.Account': 'PersonalAccount',
            'account.owner': 'John Doe',
            'account.currency': 'USD'
        }
    )
]
>>> account_metric_exporter.export(["account"], business_account).to_metrics({})
[
    Metric(
        name='account.balance',
        value=Decimal('100000'),
        tags={
            'account.Account': 'BusinessAccount',
            'account.owner': 'Doe Ltd.',
            'account.currencies': 'USD'
        }
    ),
    Metric(
        name='account.balance',
        value=Decimal('20000'),
        tags={
            'account.Account': 'BusinessAccount',
            'account.owner': 'Doe Ltd.',
            'account.currencies': 'USD'
        }
    ),
    Metric(
        name='account.balance',
        value=Decimal('50000'),
        tags={
            'account.Account': 'BusinessAccount',
            'account.owner': 'Doe Ltd.',
            'account.currencies': 'EUR'
        }
    )
]
```

### Issues

Please report any issues to the [GitHub repository for this package](https://github.com/stasharrofi/pytyped).

### Contributors

- [Shahab Tasharrofi](mailto:shahab.tasharrofi@gmail.com)
