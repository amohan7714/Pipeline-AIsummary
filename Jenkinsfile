
pipeline {
    agent any

    environment {
        INCIDENT_API_URL    = 'http://54.173.49.94:8080/webhook/jenkins'
        WEBHOOK_SECRET       = '2fe931364f4a16f9bcdad4f287880af536a8862a97712fbd151c702a91591c9a'
    }

    stages {
        stage('Build') {
            steps {
                sh 'echo "pretend build step"'
            }
        }

        stage('Test - force failure') {
            steps {
                // remove this once you're done testing the webhook
                sh 'exit 1'
            }
        }
    }

    post {
        failure {
            sh """
              curl -sS -X POST "${INCIDENT_API_URL}" \\
                -H "Content-Type: application/json" \\
                -H "X-Webhook-Secret: ${WEBHOOK_SECRET}" \\
                -d '{
                  "job_name": "${JOB_NAME}",
                  "build_number": ${BUILD_NUMBER},
                  "build_url": "${BUILD_URL}",
                  "status": "FAILURE",
                  "branch": "${GIT_BRANCH ?: 'unknown'}"
                }'
            """
        }
    }
}