pipeline {
    // Run on a Jenkins node with ArcGIS Pro installed.
    agent { label 'arcgis-pro' }

    parameters {
        choice(
            name: 'ENV',
            choices: ['DEV', 'UAT', 'PROD'],
            description: 'Target environment. Config files will be loaded from config-repo/<ENV>/'
        )
        string(
            name: 'CONFIG_REPO_URL',
            defaultValue: 'https://gitlab.company.com/gis/geotech-print-config.git',
            description: 'GitLab URL of the separate config repo'
        )
        string(
            name: 'CONFIG_REPO_BRANCH',
            defaultValue: 'main',
            description: 'Branch to checkout from the config repo'
        )
        string(
            name: 'CONFIG_REPO_CREDS_ID',
            defaultValue: 'gitlab-config-repo-creds',
            description: 'Jenkins credentials ID (Username/Password) for the config repo'
        )
        string(
            name: 'ARCGIS_PYTHON',
            defaultValue: 'C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe',
            description: 'ArcGIS Pro Python executable path. Use a cloned conda env path in production.'
        )
    }

    stages {

        stage('Checkout Config Repo') {
            steps {
                // Clone the config repo into a dedicated subdirectory.
                // Jenkins has already checked out the automation repo in WORKSPACE root.
                dir('config-repo') {
                    git(
                        url: params.CONFIG_REPO_URL,
                        branch: params.CONFIG_REPO_BRANCH,
                        credentialsId: params.CONFIG_REPO_CREDS_ID
                    )
                }
                echo "Config repo checked out -> config-repo/${params.ENV}/"
            }
        }

        stage('Setup') {
            steps {
                bat "\"${params.ARCGIS_PYTHON}\" -m pip install --upgrade pip"
                bat "\"${params.ARCGIS_PYTHON}\" -m pip install -r requirements.txt"
            }
        }

        stage('Lint') {
            steps {
                bat "\"${params.ARCGIS_PYTHON}\" -m ruff check src/ tests/"
            }
        }

        stage('Test') {
            steps {
                bat "\"${params.ARCGIS_PYTHON}\" -m pytest tests/ -v --junitxml=test-results.xml"
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'test-results.xml'
                }
            }
        }

        stage('Run') {
            steps {
                bat "\"${params.ARCGIS_PYTHON}\" -m src.runners.main_runner ^
                    --config config-repo/${params.ENV}/app_config.yaml ^
                    --logging config-repo/${params.ENV}/logging.yaml ^
                    --env ${params.ENV}"
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'logs/*.log', allowEmptyArchive: true
        }
        success {
            echo "Workflow completed successfully [ENV=${params.ENV}]."
        }
        failure {
            echo "Workflow failed [ENV=${params.ENV}]. Check archived logs."
        }
    }
}
