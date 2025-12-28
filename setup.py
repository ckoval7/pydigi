"""
PyDigi - Pure Python implementation of digital modem algorithms from fldigi
"""

from setuptools import setup, find_packages

# Read dependencies from pyproject.toml, but provide fallback for older tools
setup(
    packages=find_packages(exclude=["tests", "tests.*", "examples", "docs"]),
    include_package_data=True,
)
