from setuptools import find_packages, setup

with open("README.md", "r") as f:
    long_description = f.read()
import io
import re

# source: https://stackoverflow.com/a/39671214/1933315
__version__ = re.search(
    r'__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
    io.open("coco_agent/__init__.py", encoding="utf_8_sig").read(),
).group(1)

config = {
    "version": __version__,
    "name": "coco-agent",
    "description": "coco-agent",
    "author": "connectedcompany.io",
    "long_description": long_description,
    "long_description_content_type": "text/markdown",
    "url": "https://github.com/connectedcompany/coco-agent",
    #'download_url': 'Where to download it.',
    #'author_email': 'My email.',
    "install_requires": [
        "click>=7.1.2,<8",
        "gitpython==3.1.27",
        "google-cloud-logging==2.6.0",
        "google-cloud-storage==2.1.0",
        "pybase62==0.4.3",
        "python-dateutil>=2.8.2",
        "srsly>=2.4.1",
        "urllib3>=1.26.6",
    ],
    "python_requires": ">=3.7",
    "packages": find_packages(),
    "scripts": ["coco-agent"],
}

setup(**config)
