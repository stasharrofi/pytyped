import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

package_list = []

setuptools.setup(
    name="pytyped",
    version="2.0.0",
    author="Shahab Tasharrofi",
    author_email="shahab.tasharrofi@gmail.com",
    description="Type-Driven Development for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/stasharrofi/pytyped/tree/master/pytyped",
    install_requires=["pytyped-json>=2.0.0", "pytyped-metrics>=2.0.0", "pytyped-hocon>=1.0.0"],
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
