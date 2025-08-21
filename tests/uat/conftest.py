"""
UAT Test Configuration and Fixtures
"""
import pytest
import requests
import time
import os
import json
from typing import Dict, Any, Optional

# Test configuration
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_TIMEOUT = 30

class APIClient:
    """Centralized API client for UAT tests"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.timeout = API_TIMEOUT
    
    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Make API request with proper error handling"""
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, **kwargs)
            return response
        except requests.RequestException as e:
            pytest.fail(f"Request failed: {method} {url} - {str(e)}")
    
    def get(self, path: str, **kwargs) -> requests.Response:
        return self.request("GET", path, **kwargs)
    
    def post(self, path: str, **kwargs) -> requests.Response:
        return self.request("POST", path, **kwargs)
    
    def delete(self, path: str, **kwargs) -> requests.Response:
        return self.request("DELETE", path, **kwargs)

@pytest.fixture(scope="session")
def client():
    """API client fixture"""
    return APIClient()

@pytest.fixture(scope="session")
def admin_api_key(client):
    """Create admin API key for testing"""
    response = client.post("/api/v1/admin/dev/create-api-key?user_id=uat_admin")
    if response.status_code != 200:
        pytest.skip("Cannot create admin API key - server may not be in dev mode")
    
    return response.json()["api_key"]

@pytest.fixture(scope="session")
def admin_headers(admin_api_key):
    """Admin authorization headers"""
    return {"Authorization": f"Bearer {admin_api_key}"}

@pytest.fixture(scope="session") 
def standard_api_key(client):
    """Create standard API key for testing"""
    response = client.post("/api/v1/admin/dev/create-api-key?user_id=uat_user")
    if response.status_code != 200:
        pytest.skip("Cannot create standard API key")
    
    return response.json()["api_key"]

@pytest.fixture(scope="session")
def standard_headers(standard_api_key):
    """Standard user authorization headers"""
    return {"Authorization": f"Bearer {standard_api_key}"}

@pytest.fixture
def test_binary_ssh_keygen():
    """SSH keygen binary file path"""
    # Try to find ssh-keygen on system
    import shutil
    ssh_keygen_path = shutil.which("ssh-keygen")
    if ssh_keygen_path and os.path.exists(ssh_keygen_path):
        return ssh_keygen_path
    
    # Check if we have it in test data
    binary_path = "tests/uat/data/test_binaries/ssh-keygen"
    if os.path.exists(binary_path):
        return binary_path
    
    pytest.skip("SSH keygen binary not found for testing")

@pytest.fixture
def small_test_binary():
    """Create a small test binary"""
    import tempfile
    # Create a minimal ELF header for testing
    elf_header = bytes([
        0x7f, 0x45, 0x4c, 0x46,  # ELF magic
        0x02, 0x01, 0x01, 0x00,  # 64-bit, little-endian, version 1
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # padding
        0x02, 0x00,  # executable type
        0x3e, 0x00,  # x86-64
    ])
    # Pad to make it a bit larger
    test_data = elf_header + b'\x00' * 1000
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.elf')
    temp_file.write(test_data)
    temp_file.close()
    
    yield temp_file.name
    
    # Cleanup
    os.unlink(temp_file.name)

def wait_for_job_completion(client: APIClient, job_id: str, timeout: int = 300) -> Dict[str, Any]:
    """Wait for decompilation job to complete"""
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        response = client.get(f"/api/v1/decompile/{job_id}")
        assert response.status_code == 200
        
        data = response.json()
        status = data["status"]
        
        if status in ["completed", "failed", "cancelled"]:
            return data
        
        time.sleep(2)  # Poll every 2 seconds
    
    pytest.fail(f"Job {job_id} did not complete within {timeout} seconds")

def submit_test_job(client: APIClient, binary_path: str, **params) -> str:
    """Submit a test decompilation job and return job ID"""
    with open(binary_path, "rb") as f:
        files = {"file": (os.path.basename(binary_path), f, "application/octet-stream")}
        
        response = client.post("/api/v1/decompile", files=files, data=params)
    
    assert response.status_code == 202, f"Job submission failed: {response.text}"
    
    job_data = response.json()
    return job_data["job_id"]

# Test data validation
@pytest.fixture(autouse=True)
def verify_server_running(client):
    """Verify API server is running before each test"""
    try:
        response = client.get("/api/v1/health/live")
        if response.status_code != 200:
            pytest.skip("API server is not running or not ready")
    except:
        pytest.skip("Cannot connect to API server")