# Default target
.DEFAULT_GOAL := help

# Find and delete all __pycache__ directories in the project
.PHONY: clean
clean:
	@echo "Cleaning __pycache__ directories..."
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@find . -name "*.pyc" -delete
	@echo "Cleaned all __pycache__ directories and .pyc files"

# Run the game
.PHONY: run
run:
	@echo "Starting the game..."
	@python -m rts.rts_game

# Run unit tests if they exist
.PHONY: test
test:
	@echo "Running tests..."
	@pytest tests/

# Help command
.PHONY: help
help:
	@echo "Available commands:"
	@echo "  clean    - Delete all __pycache__ directories and .pyc files"
	@echo "  run      - Run the game"
	@echo "  test     - Run unit tests"
	@echo "  help     - Show this help message"