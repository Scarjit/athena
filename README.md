# Athena

A simple OpenAI based voice assistant.

## Installation

This project uses [uv](https://github.com/astral-sh/uv) as a dependency manager.
But you can probably use any other dependency manager.

```bash
# Clone the repository
git clone https://github.com/Scarjit/athena.git

# Copy the config.toml.sample to config.toml
cp config.toml.sample config.toml

# Create virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate

# Install the dependencies (using uv)
uv sync

# Run the project
.venv/bin/python main.py
```