"""Setup for Ultradex Python SDK"""

from setuptools import setup, find_packages

with open("SDK_README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ultradex-sdk",
    version="1.0.0",
    author="Nate Walker",
    description="Python SDK for Ultradex AI-powered contact analysis API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.ravenhelm.dev/products/ultradex",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "httpx>=0.24.0",
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "ultradex=cli.ultradex_cli:cli",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
