from setuptools import setup


setup(
    name="OpenPype Python Api",
    version="0.1.0",
    description="",
    py_modules=["openpype_api"],
    package_dir={"": "openpype_api"},
    author="OpenPype Team",
    author_email="info@openpype.io",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/pypeclub/openpype4-python-api",
    include_package_data=True,
    # https://pypi.org/classifiers/
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 3",
    ],
    install_requires=[
        "python = ^3.7",
        "requests = ^2.28.1",
        "six = ^1.15",
    ],
    keywords=["OpenPype", "pype.club", "vfx"]
)