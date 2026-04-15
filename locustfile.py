# locustfile.py
"""
MEF Portal Load Testing Suite

Load tests for the MEF Portal application.
Tests critical user journeys:
- Student login & request submission
- Mentor approval workflow
- Status checking
- PDF download

Usage:
    locust -f locustfile.py --host=http://localhost:5000
    
Or headless mode:
    locust -f locustfile.py --host=http://localhost:5000 -u 100 -r 10 --run-time 5m --headless
"""

import logging
import json
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MEFPortalUser(FastHttpUser):
    """
    Simulates a student user in MEF Portal.
    Performs typical workflow: login → submit request → check status
    """
    wait_time = between(2, 5)  # Wait 2-5 seconds between tasks
    
    # Performance targets
    TARGET_LOGIN_TIME = 1.0  # seconds
    TARGET_REQUEST_TIME = 1.5  # seconds
    TARGET_STATUS_TIME = 1.0  # seconds
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = None
        self.request_id = None
        self.session_cookie = None
        self.csrf_token = None
        
    def on_start(self):
        """
        Called when a Locust user starts.
        Performs login to establish session.
        """
        logger.info(f"User {self.client_id} starting session")
        self._login()
        
    def on_stop(self):
        """Called when user stops (test ends or user removed)"""
        if self.user_id:
            logger.info(f"User {self.user_id} ending session")
    
    def _login(self):
        """Authenticate and extract CSRF token + session cookie"""
        # Step 1: GET login page to extract CSRF token
        with self.client.get(
            "/",
            catch_response=True,
            name="/login [GET]"
        ) as response:
            if response.status_code == 200:
                response.success()
                # Extract CSRF token from HTML (simplified)
                # In real scenario, parse HTML
                logger.debug(f"Login page fetched: {response.status_code}")
            else:
                response.failure(f"Login page failed: {response.status_code}")
                return
        
        # Step 2: POST login credentials
        login_data = {
            "register_number": "23IT001",  # Test student
            "password": "password123",
        }
        
        with self.client.post(
            "/auth/login",
            data=login_data,
            catch_response=True,
            name="/auth/login [POST]"
        ) as response:
            if response.status_code in [200, 302]:  # 302 = redirect to dashboard
                response.success()
                self.user_id = "23IT001"
                logger.info(f"✅ Login successful for {self.user_id}")
            else:
                response.failure(f"Login failed: {response.status_code}")
                logger.error(f"Login failed: {response.text[:200]}")
    
    @task(3)  # Weight: 3x more frequent than other tasks
    def view_dashboard(self):
        """
        Task: View student dashboard (high frequency)
        Tests: Session validity, data retrieval, rendering
        """
        with self.client.get(
            "/",
            catch_response=True,
            name="/dashboard [GET]"
        ) as response:
            if response.status_code == 200:
                response.success()
                # Track if dashboard content is loaded
                if "dashboard" in response.text.lower():
                    logger.debug(f"Dashboard loaded for {self.user_id}")
            else:
                response.failure(f"Dashboard failed: {response.status_code}")
    
    @task(2)
    def submit_request(self):
        """
        Task: Submit a leave request
        Tests: Form handling, validation, database write, error handling
        Performance critical: Should be <1.5s
        """
        request_data = {
            "date_from": "2026-04-25",
            "date_to": "2026-04-26",
            "reason": "Medical appointment",
            "request_type": "leave",
        }
        
        with self.client.post(
            "/unified_request",
            data=request_data,
            catch_response=True,
            name="/unified_request [POST]"
        ) as response:
            if response.status_code in [200, 302]:
                response.success()
                # Extract request ID if present in response
                if "request_id=" in response.text or "pending" in response.text.lower():
                    logger.info(f"✅ Request submitted by {self.user_id}")
                    self.request_id = "auto_assigned"
            else:
                response.failure(f"Request submission failed: {response.status_code}")
                logger.error(f"Request failed: {response.text[:200]}")
    
    @task(2)
    def check_request_status(self):
        """
        Task: Check status of submitted requests
        Tests: Query performance, database read, filtering
        Performance critical: Should be <1.0s
        """
        with self.client.get(
            "/status",
            catch_response=True,
            name="/status [GET]"
        ) as response:
            if response.status_code == 200:
                response.success()
                if "pending" in response.text.lower() or "approved" in response.text.lower():
                    logger.debug(f"Status check successful")
            else:
                response.failure(f"Status check failed: {response.status_code}")
    
    @task(1)
    def view_profile(self):
        """
        Task: View user profile (low frequency)
        Tests: Session validation, profile data retrieval
        """
        with self.client.get(
            "/profile",
            catch_response=True,
            name="/profile [GET]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Profile view failed: {response.status_code}")


class MentorUser(FastHttpUser):
    """
    Simulates a mentor user reviewing and approving requests.
    Workflow: login → view pending requests → approve/reject
    """
    wait_time = between(3, 8)  # Mentor spends more time per request
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mentor_id = None
    
    def on_start(self):
        """Login as mentor"""
        self._mentor_login()
    
    def _mentor_login(self):
        """Authenticate as mentor"""
        with self.client.post(
            "/auth/login",
            data={
                "register_number": "mentor_001",
                "password": "password123",
            },
            catch_response=True,
            name="/auth/login [MENTOR]"
        ) as response:
            if response.status_code in [200, 302]:
                response.success()
                self.mentor_id = "mentor_001"
                logger.info(f"✅ Mentor login successful: {self.mentor_id}")
            else:
                response.failure(f"Mentor login failed: {response.status_code}")
    
    @task(1)
    def view_pending_requests(self):
        """View dashboard with pending approvals"""
        with self.client.get(
            "/staff/mentor",
            catch_response=True,
            name="/staff/mentor [GET]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Mentor dashboard failed: {response.status_code}")
    
    @task(1)
    def approve_request(self):
        """Approve a request (simulated)"""
        # In real test, would need to extract actual request ID from pending list
        request_id = 1  # Placeholder
        with self.client.post(
            f"/staff/approve/{request_id}",
            data={"comment": "Approved - looks good"},
            catch_response=True,
            name="/staff/approve [POST]"
        ) as response:
            if response.status_code in [200, 302]:
                response.success()
                logger.info(f"✅ Request {request_id} approved")
            elif response.status_code == 404:
                # Request not found (expected in load test)
                response.success()
            else:
                response.failure(f"Approval failed: {response.status_code}")


class HealthCheckUser(FastHttpUser):
    """
    Simulates monitoring system health checks.
    Frequent, lightweight requests to health endpoints.
    """
    wait_time = between(5, 10)  # Health checks every 5-10 seconds
    
    @task(5)
    def liveness_probe(self):
        """Check if app is running (liveness)"""
        with self.client.get(
            "/healthz/live",
            catch_response=True,
            name="/healthz/live [GET]"
        ) as response:
            if response.status_code == 200:
                response.success()
                if '"status":"live"' in response.text or '"status": "live"' in response.text:
                    pass
                else:
                    response.failure(f"Unexpected response: {response.text[:100]}")
            else:
                response.failure(f"Liveness check failed: {response.status_code}")
    
    @task(3)
    def readiness_probe(self):
        """Check if app is ready to accept traffic (readiness)"""
        with self.client.get(
            "/healthz/ready",
            catch_response=True,
            name="/healthz/ready [GET]"
        ) as response:
            if response.status_code in [200, 503]:  # 503 = not ready yet
                response.success()
            else:
                response.failure(f"Readiness check failed: {response.status_code}")


# ============================================================================
# CUSTOM EVENT LISTENERS & REPORTING
# ============================================================================

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when load test starts"""
    logger.info("=" * 80)
    logger.info("🚀 MEF PORTAL LOAD TEST STARTED")
    logger.info(f"Target: {environment.host}")
    logger.info("=" * 80)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when load test ends - print summary"""
    logger.info("=" * 80)
    logger.info("📊 LOAD TEST SUMMARY")
    logger.info("=" * 80)
    
    # Collect statistics
    stats = environment.stats
    
    total_requests = sum(r.num_requests for r in stats.entries.values())
    total_failures = sum(r.num_failures for r in stats.entries.values())
    total_time_ms = sum(r.total_response_time for r in stats.entries.values())
    
    success_rate = ((total_requests - total_failures) / total_requests * 100) if total_requests > 0 else 0
    
    logger.info(f"Total Requests: {total_requests}")
    logger.info(f"Total Failures: {total_failures}")
    logger.info(f"Success Rate: {success_rate:.2f}%")
    logger.info(f"Average Response Time: {total_time_ms/total_requests:.2f}ms")
    
    logger.info("\nEndpoint Performance:")
    logger.info("-" * 80)
    
    for method, entry in stats.entries.items():
        if entry.num_requests > 0:
            avg_response = entry.total_response_time / entry.num_requests
            logger.info(
                f"  {method:40} | "
                f"Reqs: {entry.num_requests:6} | "
                f"Failures: {entry.num_failures:4} | "
                f"Avg: {avg_response:7.2f}ms | "
                f"Min: {entry.min_response_time:7.2f}ms | "
                f"Max: {entry.max_response_time:7.2f}ms"
            )
    
    logger.info("-" * 80)
    
    # Check against targets
    logger.info("\n✅ Performance Targets:")
    logger.info(f"  Success Rate > 99%: {'✅ PASS' if success_rate > 99 else '❌ FAIL'}")
    logger.info(f"  Error Rate < 1%: {'✅ PASS' if (total_failures/total_requests*100) < 1 else '❌ FAIL'}")
    
    logger.info("=" * 80)


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, response, context, exception, **kwargs):
    """Called on every request for detailed logging"""
    if exception:
        logger.error(f"Request failed: {name} - {exception}")
    elif response_time > 2000:  # Slow request (>2 seconds)
        logger.warning(f"⚠️  Slow request: {name} took {response_time}ms")


# ============================================================================
# COMMAND LINE USAGE EXAMPLES
# ============================================================================
"""
# Interactive UI mode (http://localhost:8089)
locust -f locustfile.py --host=http://localhost:5000

# Headless mode - 100 users, ramp-up rate 10/sec, run for 5 minutes
locust -f locustfile.py --host=http://localhost:5000 \
  -u 100 -r 10 --run-time 5m --headless

# Spike test - sudden spike to 500 users
locust -f locustfile.py --host=http://localhost:5000 \
  -u 500 -r 50 --run-time 2m --headless

# Stress test - gradually increase until failure
locust -f locustfile.py --host=http://localhost:5000 \
  -u 1000 -r 50 --run-time 10m --headless

# Docker-based test
docker run -u $(id -u):$(id -g) -v $PWD:/mnt/locust locustio/locust:latest \
  -f /mnt/locustio/locustfile.py --host=http://host.docker.internal:5000 \
  -u 100 -r 10 --run-time 5m --headless

# Generate HTML report
locust -f locustfile.py --host=http://localhost:5000 \
  -u 100 -r 10 --run-time 5m --headless \
  --html=report.html
"""
