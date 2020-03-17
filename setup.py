import re
from setuptools import setup


_versionRE = re.compile(r'__version__\s*=\s*\"([^\"]+)\"')
# read the version number for the settings file
with open('lib/feaPyFoFum/__init__.py', "r") as settings:
    code = settings.read()
    found = _versionRE.search(code)
    assert found is not None, "glyphConstruction __version__ not found"
    __version__ = found.group(1)

setup(
    name='feaPyFoFum',
    version=__version__,
    description="A library for making .fea dynamic",
    url="https://github.com/typesupply/feaPyFoFum",
    packages=["feaPyFoFum"],
    package_dir={"": "Lib"}
)
