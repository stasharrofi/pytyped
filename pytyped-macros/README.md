# pytyped-macros

`pytyped-macros` is a core piece of `pytyped` Python packages that allows analysis of a given Python type and its breakdown into primitive type combinators.
In this way, `pytyped-macros` facilitate `pytyped`'s main goal of type-driven development in Python.
`pytyped-macros` is designed to be an extensible base class upon which other type derivations are implemented. 
In order to see examples of how `pytyped-macros` can be used, look at `pytyped-json`, and `pytyped-metrics`.

### Installation

You can install `pytyped-macros` from [PyPI](https://pypi.org/):

```
pip install pytyped-macros
```

`pytyped-macros` is checked on `Python 3.6+`.

### Why `pytyped-macros`?

To our knowledge, `pytyped-macros` is the only Python package that supports type-based automation for all typing constructs including even recursive types that, up to this day, are not even fully supported by Python itself.
Additionally, `pytyped-macros` is designed to be extensible.
That is, you can create a sub-class of `pytyped-macros`'s `Extractor` class to automate type derivation for your own task.
To see examples of how this is done in practice, look at `pytyped-json` which uses `pytyped-macros` in order to automatically derive JSON decoders/encoders for a given Python type.

Currently, `pytyped-macros` supports the following type driven derivations:
- Derivations for **basic types** such as `int`, `bool`, `date`, `datetime`, `str`, and `Decimal`.
- Derivations for **simple usual combinators** such as `List[T]` and `Dict[A, B]`.
- Derivations for **named product types** such as `NamedTuple`s or `dataclass`es.
- Derivations for **anonymous product types** such as `Tuple[T1, T2, ...]`.
- Derivations for **anonymous union types** such as `Optional[T]`, `Union[T1, T2, ...]`, etc.
- Derivations for **named union types** such as class hierarchies (i.e., when a class `A` has several subclasses `A1`, ..., `An`).
- Derivations for **generic types** and type variables.
- Derivations for **custom functional types** such as `Set[T]`, `Secret[T]`, etc where a custom function is defined for generic types such as `Set` or `Secret` and that functional is applied to all instantiations of those generic type.
- Derivations for **recursive types** such as binary trees, etc.

### Defining New Type Automations

You can follow the examples of `pytyped-json` (for JSON decoders and JSON encoders), or `pytyped-metrics` for metric exporters to define new type-based automations.
You just need to extend `pytyped.macros.extractor.Extractor` and implement the abstrtact methods there.

### Issues

Please report any issues to the [GitHub repository for this package](https://github.com/stasharrofi/pytyped).

### Contributors

- [Shahab Tasharrofi](mailto:shahab.tasharrofi@gmail.com)
- [Ilyess Bachiri](mailto:bachiri.ilyess@gmail.com)
