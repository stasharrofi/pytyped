# pytyped

`pytyped` is a Python package whose goal is to enable as much type-driven development as possible in Python.
We believe in using types to automate mundane and repetitive tasks.
Currently, given a type, JSON decoders/encoders and metric extractors can be automatically extracted for that type.

### Installation

You can install `pytyped` from [PyPI](https://pypi.org/):

```
pip install pytyped
```

`pytyped` is checked on `Python 3.6+`.

### Using `pytyped` to extract JSON decoders/encoders

First, define your type. For example, in the following we want to define an account that can either be a personal
account or a business account with personal account having one owner and possibly a co-owner while a business account
has the company name as the owner and a list of persons that can represent the company.

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

### Using pytyped to extract metrics

Similar to extracting JSON decoders/encoders except that `pytyped.metrics.exporter.AutoMetricExporter` is used.
Further explanation is WIP.

### Defining New Type Automations

You can follow the examples of JSON decoders, JSON encoders, and metric exporters to define new type-based automations.
You just need to extend `pytyped.macros.extractor.Extractor` and implement the abstrtact methods there.
Further explanation is WIP.

### Issues

Please report any issues to the [GitHub repository for this package](https://github.com/stasharrofi/pytyped).

### Contributors

- [Shahab Tasharrofi](mailto:shahab.tasharrofi@gmail.com)
