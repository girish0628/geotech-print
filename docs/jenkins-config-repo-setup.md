# Jenkins + Separate Config Repo Setup Guide

## Why a Separate Config Repo?

The automation code (`geotech-print`) is environment-agnostic. All environment-specific
values — GDB paths, FME webhook URLs, log levels — live in a dedicated config repo
(`geotech-print-config`). This gives you:

- Access control: lock PROD config to a smaller group without restricting the code repo
- Auditability: config changes have their own git history independent of code changes
- No accidental config commit into the code repo

---

## Repo Structure

### Automation Repo (this repo — `geotech-print`)

```
geotech-print/
├── src/
├── tests/
├── config/           ← local defaults only, used for local dev
│   ├── app_config.yaml
│   └── logging.yaml
├── Jenkinsfile       ← clones config repo at runtime
└── docs/
    └── config-repo-template/   ← copy these into your config repo
        ├── DEV/
        ├── UAT/
        └── PROD/
```

### Config Repo (`geotech-print-config`) — separate GitLab repo

```
geotech-print-config/
├── DEV/
│   ├── app_config.yaml
│   └── logging.yaml
├── UAT/
│   ├── app_config.yaml
│   └── logging.yaml
└── PROD/
    ├── app_config.yaml
    └── logging.yaml
```

---

## Step 1 — Create the Config Repo in GitLab

1. In GitLab, create a new project: `geotech-print-config`
2. Copy the template files from `docs/config-repo-template/` into it:
   ```
   DEV/app_config.yaml
   DEV/logging.yaml
   UAT/app_config.yaml
   UAT/logging.yaml
   PROD/app_config.yaml
   PROD/logging.yaml
   ```
3. Fill in real values for each environment (GDB paths, FME URLs, etc.)
4. Push to `main`

---

## Step 2 — Create Jenkins Credentials for the Config Repo

The config repo is private, so Jenkins needs credentials to clone it.

1. Go to: **Jenkins > Manage Jenkins > Credentials > System > Global credentials**
2. Click **Add Credentials**
3. Fill in:
   | Field | Value |
   |---|---|
   | Kind | Username with password |
   | Scope | Global |
   | Username | Your GitLab username or service account |
   | Password | GitLab Personal Access Token (scope: `read_repository`) |
   | ID | `gitlab-config-repo-creds` |
   | Description | GitLab config repo read access |
4. Click **OK**

> The credential ID `gitlab-config-repo-creds` matches the default in the `Jenkinsfile`.
> If you use a different ID, update the `CONFIG_REPO_CREDS_ID` parameter when running the job.

---

## Step 3 — Configure the Jenkins Job

The `Jenkinsfile` in the automation repo handles everything. Jenkins will:

1. Check out the automation repo (standard SCM checkout)
2. Clone the config repo into `config-repo/` within the workspace
3. Pass `config-repo/<ENV>/app_config.yaml` and `config-repo/<ENV>/logging.yaml` to the runner

### Jenkins Job Parameters (set at run time or in job defaults)

| Parameter | Default | Description |
|---|---|---|
| `ENV` | `DEV` | Target environment (`DEV` / `UAT` / `PROD`) |
| `CONFIG_REPO_URL` | `https://gitlab.company.com/gis/geotech-print-config.git` | URL of the config repo |
| `CONFIG_REPO_BRANCH` | `main` | Config repo branch to clone |
| `CONFIG_REPO_CREDS_ID` | `gitlab-config-repo-creds` | Jenkins credential ID |
| `ARCGIS_PYTHON` | ArcGIS Pro default path | Path to Python executable |

---

## Step 4 — Jenkins Workspace Layout at Runtime

After the pipeline runs, the Jenkins workspace looks like this:

```
WORKSPACE/
├── src/                         ← from automation repo
├── tests/                       ← from automation repo
├── requirements.txt             ← from automation repo
├── Jenkinsfile                  ← from automation repo
├── config/                      ← from automation repo (ignored at runtime)
├── config-repo/                 ← cloned from geotech-print-config
│   ├── DEV/
│   │   ├── app_config.yaml
│   │   └── logging.yaml
│   ├── UAT/
│   └── PROD/
└── logs/
    └── app.log
```

The runner is called with:
```
python -m src.runners.main_runner \
    --config config-repo/DEV/app_config.yaml \
    --logging config-repo/DEV/logging.yaml \
    --env DEV
```

---

## Local Development

For local runs, keep using `config/app_config.yaml` (already in the automation repo).
This file is for local dev only and is **not** used by Jenkins.

```bash
conda activate geotech-print-env
python -m src.runners.main_runner \
    --config config/app_config.yaml \
    --logging config/logging.yaml \
    --env DEV
```

Or, clone the config repo locally and point to it:

```bash
git clone https://gitlab.company.com/gis/geotech-print-config.git ../geotech-print-config

python -m src.runners.main_runner \
    --config ../geotech-print-config/DEV/app_config.yaml \
    --logging ../geotech-print-config/DEV/logging.yaml \
    --env DEV
```

---

## Troubleshooting

### `git clone` fails in the Checkout Config Repo stage

- Verify the credential ID exists in Jenkins and has `read_repository` scope
- Check the `CONFIG_REPO_URL` is correct (HTTPS, not SSH, unless Jenkins has SSH keys)
- Ensure the `arcgis-pro` Jenkins agent node can reach the GitLab server

### Config file not found at runtime

- Confirm the config repo was cloned successfully (check stage output)
- Verify the folder structure in the config repo matches `DEV/`, `UAT/`, `PROD/`
- The `ENV` parameter must exactly match the folder name (uppercase)

### Wrong config loaded

- Each `ENV` folder should have both `app_config.yaml` and `logging.yaml`
- Confirm you are running with the correct `ENV` parameter
