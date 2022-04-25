# pytyped-hocon

`pytyped-hocon` is a Python package that enables automatic extraction of HOCON parsers for given Python types.
`pytyped-hocon` is built on top of [pyhocon](https://pypi.org/project/pyhocon/) and [pytyped-macros](https://pypi.org/project/pytyped-macros/) to automatically parse HOCON config files into native Python types.
`pytyped-hocon` is a piece of the `pytyped` collection of packages and follows its philosophy of using types to automate mundane and repetitive tasks.

### Installation

You can install `pytyped-hocon` from [PyPI](https://pypi.org/):

```
pip install pytyped-hocon
```

`pytyped-hocon` is checked on `Python 3.6+`.

### Why `pytyped-hocon`?

Based on the foundation of `pytyped-macros`, to our knowledge, `pytyped-hocon` is the only Python package that supports type-based HOCON parser extraction for **all typing combinators** including even recursive types that, up to this day, are not even fully supported by Python itself.
Additionally, `pytyped-hocon` is designed to be extensible.
That is, you can add your own specialized HOCON parsers for either a simple type or even a generic type.

Currently, `pytyped-hocon` supports the following type driven HOCON parser extractions:
- HOCON parsers for **basic types** such as `int`, `bool`, `date`, `datetime`, `str`, and `Decimal`.
- HOCON parsers for **simple type combinators** such as `List[T]` and `Dict[A, B]`.
- HOCON parsers for **named product types** such as `NamedTuple`s or `dataclass`es.
- HOCON parsers for **anonymous product types** such as `Tuple[T1, T2, ...]`.
- HOCON parsers for **anonymous union types** such as `Optional[T]`, `Union[T1, T2, ...]`, etc.
- HOCON parsers for **named union types** such as class hierarchies (i.e., when a class `A` has several subclasses `A1`, ..., `An`).
- HOCON parsers for **generic types** and type variables.
- HOCON parsers for **custom functional types** such as `Set[T]`, `Secret[T]`, etc where a custom function is defined for generic types such as `Set` or `Secret` and that functional is applied to all instantiations of those generic type.
- HOCON parsers for **recursive types** such as binary trees, etc.

### Using `pytyped-hocon` to extract HOCON decoders

First, define your type.
For example, the following defines the configuration of a simple new archiver program that connects to a news server, gets today's news and stores it in a database.

```python
from dataclasses import dataclass
from typing import Generic, Optional, TypeVar


T = TypeVar("T")


@dataclass
class Secret(Generic[T]):
    value: T

    def __str__(self) -> str:
        return "<redacted-secret>"

    def __repr__(self) -> str:
        return "<redacted-secret>"


@dataclass
class ServerConfig:
    host: str
    port: Optional[int]  # If None, use port 80
    api_key: Secret[str]
    path: Optional[str]


@dataclass
class DbConfig:
    host: str
    user_name: str
    password: Secret[str]
    port: int = 5432  # Default Postgres port


@dataclass
class ArchiverConfig:
    news_server: ServerConfig
    db: DbConfig
```

Second, use an instance of `AutoHoconParser` to extract a HOCON parser as below:

```python
from pytyped.hocon.parser import AutoHoconParser, HoconMappedParser, HoconParser

_auto_hocon_parser = AutoHoconParser()

_auto_hocon_parser.add_custom_functional_type(Secret, lambda t_parser: HoconMappedParser(t_parser, lambda s: Secret(s)))
config_parser: HoconParser[ArchiverConfig] = _auto_hocon_parser.extract(ArchiverConfig)
```

Third, define a file such as `archiver.conf` which contains your program configuration:

```HOCON
archiver: {
    news_server: {
        host: yahoo.com
        api_key: ${YAHOO_API_KEY}
        path: "/news"
    }
    db: {
        host: localhost
        user_name: news
        password: ${DB_PASSWORD}
    }
}
```

Finally, use `config_parser` to parse your config file into your config object:

```python
>>> import os
>>> os.environ["YAHOO_API_KEY"] = "secret-api-key"
>>> os.environ["DB_PASSWORD"] = "ABCD"
>>> conf = config_parser.from_file("archiver.conf", root="archiver")
>>> conf
ArchiverConfig(
    news_server=ServerConfig(
        host='yahoo.com',
        port=None,
        api_key=<redacted-secret>,
        path='/news'
    ),
    db=DbConfig(
        host='localhost',
        user_name='news',
        password=<redacted-secret>,
        port=5432
    )
)
>>> conf.news_server.api_key.value
'secret-api-key'
>>> conf.db.password.value
'ABCD'
```

### Issues

Please report any issues to the [GitHub repository for this package](https://github.com/stasharrofi/pytyped).

### Contributors

- [Shahab Tasharrofi](mailto:shahab.tasharrofi@gmail.com)
