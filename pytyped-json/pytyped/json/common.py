from decimal import Decimal
from typing import Any
from typing import Dict
from typing import List
from typing import Union

JsValue = Union[Dict[str, Any], List[Any], str, Decimal, float, int, bool, None]
