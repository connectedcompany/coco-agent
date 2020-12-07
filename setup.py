try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


config = {
    "description": "coco-agent",
    "author": "CoCo",
    #'url': 'unused',
    #'download_url': 'Where to download it.',
    #'author_email': 'My email.',
    "version": "0.1",
    "install_requires": [
        "click==7.1.2",
        "gitpython==3.1.11",
        "google-cloud-storage==1.33.0",
        "pybase62==0.4.3",
        "srsly==2.3.2",
    ],
    "packages": ["coco_agent"],
    "scripts": [],
    "name": "coco-agent",
}

setup(**config)
