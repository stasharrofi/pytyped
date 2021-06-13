import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

package_list = setuptools.find_packages(exclude=["tests"])

setuptools.setup(
    name="pytyped",
    version="0.1.0",
    author="Shahab Tasharrofi",
    author_email="shahab.tasharrofi@gmail.com",
    description="Type-Driven Development for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/stasharrofi/pytyped",
    install_requires=["python-dateutil>=2.8.1"],
    packages=package_list,
    package_data={package_name: ['py.typed'] for package_name in package_list},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    zip_safe=False,
)
