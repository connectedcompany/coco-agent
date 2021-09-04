from setuptools import find_packages, setup

config = {
    "version": "0.2.7",
    "name": "coco-agent",
    "description": "coco-agent",
    "author": "connectedcompany.io",
    "long_description": "README",
    "long_description_content_type": "text/markdown",
    "url": "https://github.com/connectedcompany/coco-agent",
    #'download_url': 'Where to download it.',
    #'author_email': 'My email.',
    "install_requires": [
        "click==7.1.2",
        "gitpython==3.1.17",
        "google-cloud-logging==2.6.0",
        "google-cloud-storage==1.42.0",
        "pybase62==0.4.3",
        "srsly==2.4.1",
        "urllib3>=1.26.6",
    ],
    "python_requires": ">=3.6",
    "packages": find_packages(),
    "scripts": ["coco-agent"],
}

setup(**config)
