from setuptools import setup, find_packages

setup(
    name="luna11",
    version="1.1.0",
    description="Luna1.1 — AI Creative Studio: text to image, video, voice, music and full productions from one command.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Luna1.1 Contributors",
    python_requires=">=3.9",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
        "edge-tts>=6.1.9",
    ],
    extras_require={
        "fal": ["fal-client>=0.10.0"],
        "replicate": ["replicate>=0.25.0"],
        "openai": ["openai>=1.30.0"],
        "local": [
            "torch>=2.3.0",
            "diffusers>=0.27.0",
            "transformers>=4.40.0",
            "accelerate>=0.30.0",
            "Pillow>=10.3.0",
            "scipy>=1.13.0",
        ],
        "captions": ["openai-whisper>=20231117"],
        "all": [
            "fal-client>=0.10.0",
            "replicate>=0.25.0",
            "openai>=1.30.0",
            "openai-whisper>=20231117",
        ],
    },
    entry_points={
        "console_scripts": [
            "luna11=main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
