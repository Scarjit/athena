
check_dependencies:
	@# Validate that uv is installed
	@which uv || curl -LsSf https://astral.sh/uv/install.sh | sh && echo "uv installed"

prepare_config:
	@#If there is no config.toml, copy the config.toml.sample
	@if [ ! -f "config.toml" ]; then cp config.toml.sample config.toml && echo "config.toml created"; else echo "config.toml already exists"; fi

check_ppn:
	@#At least one .ppn file must be inside the ppn folder
	@if [ ! -d "ppn" ]; then mkdir ppn && echo "ppn folder created"; else echo "ppn folder already exists"; fi && \
	if [ ! -n "$(shell ls ppn/*.ppn 2>/dev/null)" ]; then echo "No .ppn files found in ppn folder"; exit 1; else echo "At least one .ppn file found in ppn folder"; fi

prepare: check_dependencies prepare_config check_ppn
	@# Create virtual environment (if not exists)
	@if [ ! -d ".venv" ]; then uv venv && echo "Virtual environment created"; else echo "Virtual environment already exists"; fi && \
	source .venv/bin/activate && \
	uv sync && \
	echo "Dependencies installed"

run: prepare
	@.venv/bin/python3 main.py
