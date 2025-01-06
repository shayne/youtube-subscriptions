.PHONY: clean reset-db reset-videos reset-channels help

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
	@sqlite3 youtube.db < schema.sql
	@echo "Database reset complete"

reset-videos:
	@echo "Clearing videos table..."
	@sqlite3 youtube.db "DELETE FROM videos;"
	@echo "Videos table cleared"

reset-channels:
	@echo "Clearing channels table..."
	@sqlite3 youtube.db "DELETE FROM channels;"
	@echo "Channels table cleared" 