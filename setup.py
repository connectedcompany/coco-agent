from setuptools import find_packages, setup

config = {
    "version": "0.1.4",
    "name": "coco-agent",
    "description": "coco-agent",
    "author": "CoCo",
    "url": "https://github.com/connectedcompany/coco-agent",
    #'download_url': 'Where to download it.',
    #'author_email': 'My email.',
    "install_requires": [
        "click==7.1.2",
        "gitpython==3.1.17",
        "google-cloud-storage==1.33.0",
        "pybase62==0.4.3",
        "srsly==2.4.1",
    ],
    "python_requires": ">=3.6",
    "packages": find_packages(),
    "scripts": ["coco-agent"],
}

setup(**config)
