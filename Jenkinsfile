pipeline {
    // Run on a Jenkins node with ArcGIS Pro installed.
    agent { label 'arcgis-pro' }

    parameters {
        choice(
            name: 'ENV',
            choices: ['DEV', 'UAT', 'PROD'],
            description: 'Target environment'
        )
        string(
            name: 'ARCGIS_PYTHON',
            defaultValue: 'C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe',
            description: 'ArcGIS Pro Python executable path. Use a cloned conda env path in production.'
        )
        string(
            name: 'CONFIG_PATH',
            defaultValue: 'config/app_config.yaml',
            description: 'Path to app config YAML'
        )
        string(
            name: 'LOGGING_PATH',
            defaultValue: 'config/logging.prod.yaml',
            description: 'Path to logging config YAML'
        )
    }

    stages {
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
                bat "\"${params.ARCGIS_PYTHON}\" -m src.runners.main_runner --config ${params.CONFIG_PATH} --logging ${params.LOGGING_PATH} --env ${params.ENV}"
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'logs/*.log', allowEmptyArchive: true
        }
        success {
            echo 'Workflow completed successfully.'
        }
        failure {
            echo 'Workflow failed. Check archived logs for details.'
        }
    }
}
