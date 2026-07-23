"""Build metadata for the official Ultradex Python SDK."""

from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ultradex-sdk",
    version="1.1.0",
    author="Nate Walker",
    license="MIT",
    description="Python SDK for Ultradex AI-powered contact analysis API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nwalker85/ultradex",
    packages=["ultradex_sdk"],
    package_dir={"ultradex_sdk": "sdk"},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.11",
    install_requires=[
        "httpx>=0.24.0",
        "ravenhelm-contracts==0.2.0",
    ],
    include_package_data=True,
    zip_safe=False,
)
