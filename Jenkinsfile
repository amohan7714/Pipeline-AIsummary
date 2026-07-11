pipeline {
    agent any

    environment {
        INCIDENT_API_URL    = 'http://54.173.49.94:8080/webhook/jenkins'
        WEBHOOK_SECRET       = '2fe931364f4a16f9bcdad4f287880af536a8862a97712fbd151c702a91591c9a'
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source from main branch...'
                sh 'echo "commit abc1234 checked out"'
            }
        }

        stage('Install dependencies') {
            steps {
                echo 'Installing dependencies...'
                sh '''
                    echo "Collecting fastapi==0.115.6"
                    echo "Collecting sqlalchemy==2.0.36"
                    echo "Collecting requests==2.31.0"
                    echo "Successfully installed fastapi-0.115.6 sqlalchemy-2.0.36 requests-2.31.0"
                '''
            }
        }

        stage('Run test suite') {
            steps {
                echo 'Running pytest...'
                sh '''
                    cat <<'EOF'
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-8.3.3, pluggy-1.5.0
rootdir: /workspace/backend-api-tests
collected 42 items

tests/test_health.py ..                                                  [  4%]
tests/test_auth.py ......                                                [ 19%]
tests/test_orders.py .......F..                                          [ 40%]
tests/test_payments.py ..........                                        [ 64%]
tests/test_users.py ............                                         [100%]

=================================== FAILURES ====================================
_________________________ test_create_order_with_discount ________________________

    def test_create_order_with_discount():
        order = create_order(user_id=42, items=[item_a, item_b], discount_code="SAVE10")
>       assert order.total == Decimal("89.99")
E       AssertionError: assert Decimal('99.99') == Decimal('89.99')
E        +  where Decimal('99.99') = Order(id=1042, total=Decimal('99.99')).total

tests/test_orders.py:87: AssertionError

---------------------------- Captured log call -----------------------------
ERROR    app.services.discount:discount.py:34 DiscountService: coupon "SAVE10"
lookup returned None -- discount_rules table has no active row for this code
in the current environment (staging DB may be out of sync with prod seed data)

=========================== short test summary info ============================
FAILED tests/test_orders.py::test_create_order_with_discount - AssertionError: assert Decimal('99.99') == Decimal('89.99')
================== 1 failed, 41 passed in 4.83s ==================
EOF
                '''
                sh 'exit 1'  // fail the stage so Jenkins marks the build FAILURE
            }
        }
    }

    post {
        failure {
            echo 'Build failed — notifying incident API...'
            sh """
              curl -sS -X POST "${INCIDENT_API_URL}" \\
                -H "Content-Type: application/json" \\
                -H "X-Webhook-Secret: ${WEBHOOK_SECRET}" \\
                -d '{
                  "job_name": "${JOB_NAME}",
                  "build_number": ${BUILD_NUMBER},
                  "build_url": "${BUILD_URL}",
                  "status": "FAILURE",
                  "branch": "${GIT_BRANCH ?: 'main'}"
                }'
            """
        }
        success {
            echo 'Build succeeded — no incident created.'
        }
    }
}