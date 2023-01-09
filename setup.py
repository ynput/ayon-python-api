from setuptools import setup


setup(
    name="Ayon Python Api",
    version="0.1.0",
    description="",
    py_modules=["ayon_api"],
    package_dir={"": "ayon_api"},
    author="ynput.io",
    author_email="info@ynput.io",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/pypeclub/ayon-python-api",
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
    keywords=["ayon", "ynput", "OpenPype", "vfx"]
)