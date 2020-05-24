import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pytyped-stasharrofi", # Replace with your own username
    version="0.0.1",
    package_data={"pytyped": ["py.typed"]},
    packages=["pytyped"],
    author="Shahab Tasharrofi",
    author_email="shahab.tasharrofi@gmail.com",
    description="Typing utilities for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/stasharrofi/pytyped",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GPLv3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
