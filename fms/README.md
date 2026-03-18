# fms

Python GIS automation project using ArcPy, FME Flow, and Jenkins CI/CD.

## Python Environment Setup (Required for ArcPy)

ArcPy is **only available inside the ArcGIS Pro Python environment**.
A plain `python -m venv` will NOT have access to ArcPy.

### Recommended: Clone the ArcGIS Pro conda environment

**Step 1 — Open ArcGIS Pro Python Command Prompt**
Start Menu > ArcGIS > Python Command Prompt

**Step 2 — Clone the default environment**
Never modify the base `arcgispro-py3` environment directly.
```
conda create --name fms-env --clone arcgispro-py3
conda activate fms-env
```

**Step 3 — Install project dependencies**
```
pip install -r requirements.dev.txt
```

**Step 4 — Verify ArcPy is available**
```
python -c "import arcpy; print^(arcpy.GetInstallInfo^(^)['Version']^)"
```

**Step 5 — Install pre-commit hooks**
```
pre-commit install
```

### Jenkins: Point to the cloned conda env

Use the cloned environment's Python executable in Jenkins:
- User installs: `C:\Users\{username}\AppData\Local\ESRI\conda\envs\fms-env\python.exe`
- Service account: `C:\ProgramData\ESRI\conda\envs\fms-env\python.exe`

Configure this path in the Jenkins job parameter `ARCGIS_PYTHON`.

## Project Structure

```
fms/
|-- src/
|   |-- core/              # Config loading, logging, custom exceptions
|   |-- services/          # Business logic (one file per external system)
|   |   |-- arcpy_service.py      # ArcPy geodatabase operations
|   |   `-- fme_webhook_service.py # FME Flow webhook calls
|   |-- runners/           # Entry points called by Jenkins / CLI
|   |   `-- main_runner.py
|   `-- utils/             # Shared helpers (add as needed)
|-- config/
|   |-- app_config.yaml    # All runtime values (edit before running)
|   |-- logging.yaml       # Dev logging (console + file, DEBUG)
|   `-- logging.prod.yaml  # Prod logging (console + file, INFO)
|-- tests/
|   |-- test_core/
|   `-- test_services/
|-- logs/                  # Log output (git-ignored)
|-- Jenkinsfile
`-- README.md
```

## Run Locally

```
conda activate fms-env
python -m src.runners.main_runner --config config/app_config.yaml --logging config/logging.yaml --env DEV
```

## Run Tests

```
pytest tests/ -v
```

## Run Linting

```
ruff check src/ tests/
```

## Configuration

Edit `config/app_config.yaml` before running. All paths and URLs must be real values.
No hardcoded values are allowed in `.py` files.

## Adding a New Service

1. Add a custom exception in `src/core/exceptions.py`
2. Create `src/services/my_new_service.py` following the ArcPyService pattern
3. Add a config section in `config/app_config.yaml`
4. Wire the service into `src/runners/main_runner.py`
5. Write tests in `tests/test_services/test_my_new_service.py`

See `docs/HOW_TO_CREATE_NEW_PROJECT.md` for detailed step-by-step instructions.
