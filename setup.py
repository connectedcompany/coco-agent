from setuptools import find_packages, setup

config = {
    "version": "0.1.3",
    "name": "coco-agent",
    "description": "coco-agent",
    "author": "CoCo",
    #'url': 'unused',
    #'download_url': 'Where to download it.',
    #'author_email': 'My email.',
    "install_requires": [
        "click==7.1.2",
        "gitpython==3.1.11",
        "google-cloud-storage==1.33.0",
        "pybase62==0.4.3",
        "srsly>=1.0",
    ],
    "python_requires": ">=3.6",
    "packages": find_packages(),
    "scripts": ["coco-agent"],
}

setup(**config)
