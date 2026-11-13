"""Uso: uv run python -m app.jobs.ingest --source ted --days 1

La ejecución diaria es `ingest_daily`. Este módulo se queda para un relanzado manual.
"""

from app.jobs.ingest_daily import main

if __name__ == "__main__":
    main()
