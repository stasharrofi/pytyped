import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pytyped",
    version="0.0.4",
    author="Shahab Tasharrofi",
    author_email="shahab.tasharrofi@gmail.com",
    description="Type-Driven Development for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/stasharrofi/pytyped",
    packages=['pytyped', 'pytyped.macros', 'pytyped.json', 'pytyped.metrics'],
    package_data= {
        'pytyped': ['py.typed'],
        'pytyped.macros': ['py.typed'],
        'pytyped.json': ['py.typed'],
        'pytyped.metrics': ['py.typed']
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    zip_safe=False,
)
