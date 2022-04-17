# pytyped-json

`pytyped-json` is a Python package that enables automatic extraction of JSON decoders/encoders for given Python types.
`pytyped-json` is a piece of the `pytyped` collection of packages and follows its philosophy of using types to automate mundane and repetitive tasks.

### Installation

You can install `pytyped-json` from [PyPI](https://pypi.org/):

```
pip install pytyped-json
```

`pytyped-json` is checked on `Python 3.6+`.

### Why `pytyped-json`?

Based on the foundation of `pytyped-macros`, to our knowledge, `pytyped-json` is the only Python package that supports type-based JSON encoder/decoder extraction for **all typing combinators** including even recursive types that, up to this day, are not even fully supported by Python itself.
Additionally, `pytyped-json` is designed to be extensible.
That is, you can add your own specialized JSON decoders/encoders for either a simple type or even a generic type.

Currently, `pytyped-json` supports the following type driven JSON encoder/decoder extractions:
- JSON encoders/decoders for **basic types** such as `int`, `bool`, `date`, `datetime`, `str`, and `Decimal`.
- JSON encoders/decoders for **simple type combinators** such as `List[T]` and `Dict[A, B]`.
- JSON encoders/decoders for **named product types** such as `NamedTuple`s or `dataclass`es.
- JSON encoders/decoders for **anonymous product types** such as `Tuple[T1, T2, ...]`.
- JSON encoders/decoders for **anonymous union types** such as `Optional[T]`, `Union[T1, T2, ...]`, etc.
- JSON encoders/decoders for **named union types** such as class hierarchies (i.e., when a class `A` has several subclasses `A1`, ..., `An`).
- JSON encoders/decoders for **generic types** and type variables.
- JSON encoders/decoders for **custom functional types** such as `Set[T]`, `Secret[T]`, etc where a custom function is defined for generic types such as `Set` or `Secret` and that functional is applied to all instantiations of those generic type.
- JSON encoders/decoders for **recursive types** such as binary trees, etc.

### Using `pytyped-json` to extract JSON decoders/encoders

First, define your type.
For example, the following defines an account superclass that can either be a personal account or a business account.
Here, we define a personal account to have one owner and possibly a co-owner while a business account is defined by the company name as the owner and a list of persons that can represent the company.

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List
from typing import Optional

@dataclass
class Person:
    first_name: str
    last_name: str


@dataclass
class Account:
    created_at: datetime


@dataclass
class PersonalAccount(Account):
    owner: Person
    co_owner: Optional[Person]


@dataclass
class BusinessAccount(Account):
    owner: str
    representatives: List[Person]
```

Second, use an instance of `AutoJsonDecoder` and `AutoJsonEncoder` to extract JSON decoders and encoders as below:

```python
from pytyped.json.decoder import AutoJsonDecoder
from pytyped.json.decoder import JsonDecoder
from pytyped.json.encoder import AutoJsonEncoder
from pytyped.json.encoder import JsonEncoder

_auto_json_decoder = AutoJsonDecoder()
_auto_json_encoder = AutoJsonEncoder()

account_decoder: JsonDecoder[Account] = _auto_json_decoder.extract(Account)
account_encoder: JsonEncoder[Account] = _auto_json_encoder.extract(Account)
```

Third, define some instances of the `Account` class:

```python
personal_account = PersonalAccount(
    created_at = datetime.now(),
    owner = Person(first_name = "John", last_name = "Doe"),
    co_owner = None
)

business_account = BusinessAccount(
    created_at = datetime.now(),
    owner = "Doe Ltd.",
    representatives = [Person(first_name = "John", last_name = "Doe"), Person(first_name = "Jane", last_name = "Doe")]
) 
```

Finally, use `account_encoder` and `account_decoder` to convert data in your instances to/from JSON as below:

```python
>>> json = account_encoder.write(personal_account)
>>> json
{'created_at': '2020-08-24T20:00:18.205347', 'owner': {'first_name': 'John', 'last_name': 'Doe'}, 'co_owner': None, 'Account': 'PersonalAccount'}
>>> account_decoder.read(json)
PersonalAccount(created_at=datetime.datetime(2020, 8, 24, 20, 0, 18, 205347), owner=Person(first_name='John', last_name='Doe'), co_owner=None)


>>> json = account_encoder.write(business_account)
>>> json
{'created_at': '2020-08-24T20:00:40.057088', 'owner': 'Doe Ltd.', 'representatives': [{'first_name': 'John', 'last_name': 'Doe'}, {'first_name': 'Jane', 'last_name': 'Doe'}], 'Account': 'BusinessAccount'}
>>> account_decoder.read(json)
BusinessAccount(created_at=datetime.datetime(2020, 8, 24, 20, 0, 40, 57088), owner='Doe Ltd.', representatives=[Person(first_name='John', last_name='Doe'), Person(first_name='Jane', last_name='Doe')])
```

To illustrate the types of validation that JSON decoders enable for you, consider the following example invalid JSONs:

```python
>>> account_decoder.read({'created_at': '2020-08-24T20:00:40.057088', 'owner': 'Doe Ltd.', 'representatives': [{'first_name': 'John', 'last_name': 'Doe'}, {'first_name': 'Jane', 'last_name': 'Doe'}], 'Account': 'NewAccount'})
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "~/Repos/pytyped/pytyped/json/decoder.py", line 91, in read
    raise JsDecodeException(t_or_error)
pytyped.json.decoder.JsDecodeException: Found 1 errors while validating JSON: [
  Error when decoding JSON: /Account: Unknown tag value NewAccount (possible values are: PersonalAccount, BusinessAccount).]


>>> account_decoder.read({'created_at': '2020-08-24T20:00:40.057088', 'owner': 'Doe Ltd.', 'representatives': [{'first_name': 'John', 'last_name': 'Doe'}, {'first_name': 'Jane', 'last': 'Doe'}], 'Account': 'BusinessAccount'})
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/home/shahab/Repos/pytyped/pytyped/json/decoder.py", line 91, in read
    raise JsDecodeException(t_or_error)
pytyped.json.decoder.JsDecodeException: Found 1 errors while validating JSON: [
  Error when decoding JSON: /representatives[1]/last_name: Non-optional field was not found]
```

### Issues

Please report any issues to the [GitHub repository for this package](https://github.com/stasharrofi/pytyped).

### Contributors

- [Shahab Tasharrofi](mailto:shahab.tasharrofi@gmail.com)
- [Ilyess Bachiri](mailto:bachiri.ilyess@gmail.com)
