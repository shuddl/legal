
# CLAUDE.md

This file provides specific guidance for AI collaborators (like Claude) working on the **Perera Construction Lead Generation Agent** repository. Please adhere to these guidelines to ensure consistency, maintainability, and adherence to best practices.

## Project Structure Overview

This project follows a standard Python structure using a `src` layout:

- `src/perera_lead_scraper/`: Main application package code resides here.
  - `main.py`: Primary entry point for the application orchestration.
  - `__main__.py`: Allows running the package as a script (`python -m perera_lead_scraper`).
  - `config.py`: Loads and validates configuration from environment variables and/or files.
  - `data_models.py`: Contains Pydantic models (`Lead`, `DataSource`, Enums).
  - `storage.py`: Handles database interactions (SQLAlchemy ORM).
  - `source_manager.py`: Manages `DataSource` registry.
  - `hubspot_integration.py`: Handles HubSpot client logic.
  - Sub-packages for different functionalities (e.g., `parsers`, `scrapers`, `pipelines`, `enrichment`, `nlp`).
- `config/`: Static configuration files (e.g., `sources.json`, `keywords.json`, `selectors.json`, `logging.json`).
- `data/`: Local data storage (e.g., SQLite DB file, cache files). Add to `.gitignore` if sensitive/large.
- `scripts/`: Utility scripts (e.g., testing, deployment, data migration).
- `tests/`: Contains all `pytest` tests mirroring the `src` structure.
- `.env.example`: Template for environment variables.
- `requirements.txt`: Primary application dependencies.
- `requirements-dev.txt`: Development-specific dependencies (pytest, linters, etc.).
- `pyproject.toml`: Build system configuration, tool configurations (Black, Ruff, MyPy, Pytest).
- `README.md`: Project overview and setup instructions.
- `Dockerfile`, `docker-compose.yml`: Containerization setup (Phase 7).
- `ARCHITECTURE.md`, `DEPLOYMENT.md`, etc.: Documentation files.

## Setup & Running

1. **Clone:** `git clone ...`
2. **Create Virtual Environment:** `python -m venv venv`
3. **Activate:** `source venv/bin/activate` (Linux/macOS) or `.\venv\Scripts\activate` (Windows)
4. **Install Dependencies:** `pip install -r requirements.txt -r requirements-dev.txt`
5. **Install Package:** `pip install -e .` (Installs the `perera_lead_scraper` package in editable mode)
6. **Configure Environment:** Copy `.env.example` to `.env` and fill in necessary values (API keys, DB paths, etc.).
7. **Run Application:** `python -m perera_lead_scraper` (uses `src/perera_lead_scraper/__main__.py`) or potentially `python src/perera_lead_scraper/main.py` depending on entry point design.
8. **Run Specific Scripts:** `python scripts/your_script_name.py`

## Development Workflow & Commands

- **Linting:** `ruff check .` (or configured alias)
- **Formatting:** `black .` (or configured alias)
- **Type Checking:** `mypy src/perera_lead_scraper tests` (or configured alias)
- **Run All Tests:** `pytest tests/`
- **Run Specific Test File/Function:** `pytest tests/path/to/test_file.py::TestClassName::test_method_name`
- **Run Tests with Coverage:** `pytest --cov=src/perera_lead_scraper --cov-report term-missing tests/` (Aim for >80% coverage)
- **Update Dependencies:** Add new dependencies to `requirements.txt` or `requirements-dev.txt`. Regenerate lock files if used.

## Code Style & Conventions

Adhere strictly to the following:

- **Python Version**: 3.9+ compatible code.
- **Formatting**: **Black** for automated formatting (run before committing).
- **Linting**: **Ruff** (preferred over Flake8) for linting and style checks (configured in `pyproject.toml`). Address all linter warnings/errors.
- **Type Hints**: **Mandatory** for all function signatures (parameters and return types) and class attributes where feasible. Checked with **MyPy**.
- **Imports**: Group standard library, third-party, then `src/perera_lead_scraper` imports. Sort alphabetically within groups (handled by Ruff/Black). Use absolute imports relative to `src`.
- **Docstrings**: **Mandatory** for all modules, public classes, and functions (Google style preferred). Explain purpose, arguments, return values, and any raised exceptions.
- **Naming**: `CapWords` for classes, `snake_case` for functions, methods, variables, and modules/packages.
- **Configuration**: Use `src/perera_lead_scraper/config.py` module to load settings from `.env` (via `python-dotenv`) and potentially config files. **No hardcoded keys, paths, or sensitive values.**
- **Logging**: Use the configured **structured logger** (e.g., JSON format via `utils.logger` or configured in `config.py`). Use appropriate levels (DEBUG, INFO, WARNING, ERROR). **Do NOT use `print()` statements for logging/debugging.**
- **Error Handling**: Use specific `try...except` blocks. Catch specific exceptions, not bare `except:`. Log errors with context. Use custom exceptions where appropriate. Implement retry logic (`tenacity` library preferred) for network/API calls.
- **Modularity**: Keep functions and classes focused on a single responsibility. Break down complex logic.
- **Data Models**: Use **Pydantic** (`src/perera_lead_scraper/data_models.py`) for defining and validating data structures (`Lead`, `DataSource`, API responses, etc.).
- **Storage**: Use **SQLAlchemy ORM** via `src/perera_lead_scraper/storage.py`. Use session context managers for transactions. Consider Alembic for migrations.
- **Security**:
  - Retrieve ALL secrets (API keys, passwords) from environment variables (`.env`) via the `config.py` module.
  - Use credential referencing in configurations (`sources.json`) rather than storing secrets directly.
  - Sanitize external inputs.
  - Be mindful of logging sensitive information.
- **Testing**: Write **`pytest`** unit tests for new logic and integration tests for component interactions. Use fixtures and mocking effectively.

## Version Control (Git)

- Work on feature branches (`feature/`, `bugfix/`, `chore/`).
- Write clear, concise, and imperative commit messages (e.g., "Feat: Implement RSS feed parser caching"). Reference issue numbers if applicable.
- Keep commits focused and atomic.
- Rebase branches onto the main branch before merging (if required by team workflow).
- Use Pull Requests for code review (if applicable).

## Important Reminders
- **Focus:** Address the specific requirements of the current prompt/task. 
- **Ask Questions:** If requirements are unclear, ask for clarification before proceeding.
```

