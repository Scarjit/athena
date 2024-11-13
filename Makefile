
check_dependencies:
	@# Validate that uv is installed
	@which uv || curl -LsSf https://astral.sh/uv/install.sh | sh && echo "uv installed"

prepare_config:
	@#If there is no config.toml, copy the config.toml.sample
	@if [ ! -f "config.toml" ]; then cp config.toml.sample config.toml && echo "config.toml created"; else echo "config.toml already exists"; fi

prepare: check_dependencies prepare_config
	@# Create virtual environment (if not exists)
	@if [ ! -d ".venv" ]; then uv venv && echo "Virtual environment created"; else echo "Virtual environment already exists"; fi && \
	source .venv/bin/activate && \
	uv sync && \
	echo "Dependencies installed"

run: prepare
	@.venv/bin/python3 main.py
