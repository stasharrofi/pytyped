import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

package_list = setuptools.find_namespace_packages(include=["pytyped.*"])

setuptools.setup(
    name="pytyped-hocon",
    version="1.0.0",
    author="Shahab Tasharrofi",
    author_email="shahab.tasharrofi@gmail.com",
    description="Type-Driven Development for Python: Automatic Extraction of HOCON Parsers for Python Types",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/stasharrofi/pytyped/tree/master/pytyped-hocon",
    install_requires=["pyhocon>=0.3.59", "python-dateutil>=2.8.1", "pytyped-macros>=2.0.0"],
    packages=package_list,
    package_data={package_name: ['py.typed'] for package_name in package_list},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    zip_safe=False,
)
