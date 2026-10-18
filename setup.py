from setuptools import setup, find_packages

setup(
    name="temporal-fusion",
    version="1.0.0",
    description="Physiologically Constrained Temporal Fusion for Multimodal EEG-fNIRS Brain-Computer Interfaces",
    author="Antigravity BCI Research Collaborative",
    packages=find_packages(include=["temporal_fusion", "temporal_fusion.*"]),
    python_requires=">=3.9",
    install_requires=[
        "torch>=2.0.0",
        "numpy>=1.24.0",
        "scipy>=1.11.0",
    ],
)
