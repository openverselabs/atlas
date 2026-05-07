from setuptools import setup, find_packages

setup(
    name="atlas",
    version="0.1.4",
    packages=find_packages(),
    install_requires=[
        "python-dotenv",
        "google-genai",  # New Google GenAI SDK
        "colorama",
        "prompt_toolkit",
        "openai",
        "anthropic",
        "groq",
        "mistralai",
    ],
    extras_require={
        "dev": ["pytest", "black", "flake8"],
    },
    entry_points={
        "console_scripts": [
            "atlas = atlas.main:main",
        ],
    },
)
