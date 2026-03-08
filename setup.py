from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ace-content-getter",
    version="1.0.0",
    author="Your Name",
    description="Descarga un archivo m3u, reemplaza IPs y lo sirve mediante HTTP",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/ace_content_getter",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    install_requires=[
        "Flask==2.3.3",
        "requests==2.31.0",
        "Werkzeug==2.3.7",
    ],
)
