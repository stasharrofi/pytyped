# pytyped

`pytyped` is a collection of Python packages that strive to enable as much type-driven development as possible in Python.
That is, starting from the definition of your type in Python, we try to automate repetitive and mundane tasks for those types.

Currently, `pytyped` repository includes following Python packages:
- [pytyped-macros](https://pypi.org/project/pytyped-macros/) introduces an extensible introspective package that takes a type and applies a custom-defined type transformation to that type.
- [pytyped-json](https://pypi.org/project/pytyped-json/) introduces automatic extraction of JSON decoders and JSON encoders for a given type.
- [pytyped-hocon](https://pypi.org/project/pytyped-hocon/) introduces automatic parsing of [HOCON](https://github.com/lightbend/config/blob/main/HOCON.md) format for a given Python type.
- [pytyped-metrics](https://pypi.org/project/pytyped-metrics/) introduces automatic metric exporter extraction from Python types.
- [pytyped](https://pypi.org/project/pytyped/) is just a collection of all packages above and an easy way to install all of them together.
