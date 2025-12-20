.PHONY: clean reset-db reset-videos reset-channels help

XDG_STATE_HOME ?= $(HOME)/.local/state
DB_PATH ?= $(XDG_STATE_HOME)/ytsubs/youtube.db

help:
	@echo "Available commands:"
	@echo "  make clean          - Remove Python cache files"
	@echo "  make reset-db       - Reset database to empty tables"
	@echo "  make reset-videos   - Clear only the videos table"
	@echo "  make reset-channels - Clear only the channels table"

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

reset-db:
	@echo "Resetting database..."
	@mkdir -p $(dir $(DB_PATH))
	@sqlite3 $(DB_PATH) < src/ytsubs/schema.sql
	@echo "Database reset complete"

reset-videos:
	@echo "Clearing videos table..."
	@sqlite3 $(DB_PATH) "DELETE FROM videos;"
	@echo "Videos table cleared"

reset-channels:
	@echo "Clearing channels table..."
	@sqlite3 $(DB_PATH) "DELETE FROM channels;"
	@echo "Channels table cleared"
