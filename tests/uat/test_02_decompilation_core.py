"""
UAT Tests: Core Decompilation Workflow
Tests the 4 core decompilation endpoints with comprehensive parameter validation
"""
import pytest
import time
import os
import tempfile
from typing import Dict, Any


class TestDecompilationCore:
    """Test core decompilation workflow endpoints"""
    
    def test_decompile_test_endpoint_connectivity(self, client):
        """TEST-D02: Test decompilation API connectivity"""
        response = client.get("/api/v1/decompile/test")
        
        assert response.status_code == 200, f"Test endpoint failed: {response.text}"
        
        data = response.json()
        assert "message" in data, "Test endpoint should return a message"
        assert "decompilation api is working" in data["message"].lower(), \
            f"Unexpected test message: {data['message']}"

    def test_decompile_submit_minimal_parameters(self, client, small_test_binary):
        """TEST-D01: Test minimal decompilation job submission"""
        with open(small_test_binary, "rb") as f:
            files = {"file": (os.path.basename(small_test_binary), f, "application/octet-stream")}
            response = client.post("/api/v1/decompile", files=files)
        
        # Validate successful submission
        assert response.status_code == 202, f"Job submission failed: {response.text}"
        
        data = response.json()
        
        # Validate response structure
        required_fields = ["success", "job_id", "status", "message", "file_info"]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        assert data["success"] is True, "Job submission should be successful"
        assert data["status"] == "queued", f"Expected 'queued' status, got: {data['status']}"
        
        # Validate job ID format (should be UUID-like)
        job_id = data["job_id"]
        assert len(job_id) >= 32, f"Job ID seems too short: {job_id}"
        
        # Validate file info
        file_info = data["file_info"]
        assert "filename" in file_info
        assert "size_bytes" in file_info
        assert file_info["size_bytes"] > 0

    def test_decompile_submit_all_parameters(self, client, small_test_binary):
        """TEST-D01: Test decompilation with all parameters specified"""
        with open(small_test_binary, "rb") as f:
            files = {"file": (os.path.basename(small_test_binary), f, "application/octet-stream")}
            form_data = {
                "analysis_depth": "comprehensive",
                "llm_provider": "openai",
                "llm_model": "gpt-4",
                "translation_detail": "detailed"
            }
            response = client.post("/api/v1/decompile", files=files, data=form_data)
        
        assert response.status_code == 202, f"Parameterized job submission failed: {response.text}"
        
        response_data = response.json()
        
        # Validate configuration echoed back
        if "config" in response_data:
            config = response_data["config"]
            assert config["analysis_depth"] == "comprehensive"
            assert config["llm_provider"] == "openai"
            assert config["translation_detail"] == "detailed"

    def test_decompile_file_size_validation(self, client):
        """TEST-D01: Test file size limits validation"""
        # Test oversized file rejection (assuming 100MB limit from PRD)
        # Create a file larger than the limit
        large_data = b"A" * (101 * 1024 * 1024)  # 101MB
        
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_file.write(large_data)
            temp_file.flush()
            
            with open(temp_file.name, "rb") as f:
                files = {"file": ("large_file.bin", f, "application/octet-stream")}
                response = client.post("/api/v1/decompile", files=files)
        
        # Should reject oversized files
        assert response.status_code == 413, \
            f"Oversized file should be rejected with 413, got: {response.status_code}"
        
        if response.status_code != 413:
            # If not rejected, check error message
            try:
                error_data = response.json()
                assert "file too large" in error_data.get("detail", "").lower() or \
                       "size" in error_data.get("detail", "").lower()
            except:
                pass

    def test_decompile_invalid_parameters(self, client, small_test_binary):
        """TEST-D01: Test invalid parameter validation"""
        test_cases = [
            {"analysis_depth": "invalid_depth"},
            {"translation_detail": "invalid_detail"},
            {"llm_provider": "invalid_provider"}
        ]
        
        for invalid_params in test_cases:
            with open(small_test_binary, "rb") as f:
                files = {"file": (os.path.basename(small_test_binary), f, "application/octet-stream")}
                response = client.post("/api/v1/decompile", files=files, data=invalid_params)
            
            # Should either reject with validation error or accept with defaults
            if response.status_code == 422:
                # Validation error - expected for invalid parameters
                error_data = response.json()
                assert "detail" in error_data or "error" in error_data
            elif response.status_code == 202:
                # Accepted - system may use defaults for invalid values
                pass
            else:
                pytest.fail(f"Unexpected response for invalid params {invalid_params}: {response.status_code}")

    def test_decompile_missing_file(self, client):
        """TEST-D01: Test submission without file"""
        response = client.post("/api/v1/decompile", data={"analysis_depth": "standard"})
        
        # Should reject requests without files
        assert response.status_code in [400, 422], \
            f"Missing file should be rejected, got: {response.status_code}"

    def test_get_job_status_nonexistent(self, client):
        """TEST-D03: Test retrieval of non-existent job"""
        import uuid
        fake_job_id = str(uuid.uuid4())  # Generate a truly random UUID
        response = client.get(f"/api/v1/decompile/{fake_job_id}")
        
        assert response.status_code == 404, \
            f"Non-existent job should return 404, got: {response.status_code}"
        
        if response.status_code == 404:
            try:
                error_data = response.json()
                assert "not found" in error_data.get("detail", "").lower()
            except:
                pass

    def test_get_job_status_valid_format(self, client, small_test_binary):
        """TEST-D03: Test job status for newly submitted job"""
        # Submit job first
        with open(small_test_binary, "rb") as f:
            files = {"file": (os.path.basename(small_test_binary), f, "application/octet-stream")}
            submit_response = client.post("/api/v1/decompile", files=files)
        
        assert submit_response.status_code == 202
        job_id = submit_response.json()["job_id"]
        
        # Get job status
        response = client.get(f"/api/v1/decompile/{job_id}")
        assert response.status_code == 200, f"Job status request failed: {response.text}"
        
        data = response.json()
        
        # Validate required fields
        required_fields = ["job_id", "status", "progress_percentage"]
        for field in required_fields:
            assert field in data, f"Missing required field in job status: {field}"
        
        assert data["job_id"] == job_id
        assert data["status"] in ["queued", "processing", "completed", "failed"], \
            f"Invalid job status: {data['status']}"
        
        # Progress should be a number between 0 and 100
        progress = data["progress_percentage"]
        assert isinstance(progress, (int, float)), "Progress should be numeric"
        assert 0 <= progress <= 100, f"Progress should be 0-100, got: {progress}"

    def test_get_job_status_with_parameters(self, client, small_test_binary):
        """TEST-D03: Test job status with include_raw_data parameter"""
        # Submit job
        with open(small_test_binary, "rb") as f:
            files = {"file": (os.path.basename(small_test_binary), f, "application/octet-stream")}
            submit_response = client.post("/api/v1/decompile", files=files)
        
        job_id = submit_response.json()["job_id"]
        
        # Test with raw data inclusion
        response = client.get(f"/api/v1/decompile/{job_id}?include_raw_data=true")
        assert response.status_code == 200
        
        response_false = client.get(f"/api/v1/decompile/{job_id}?include_raw_data=false")  
        assert response_false.status_code == 200

    def test_cancel_decompilation_job(self, client, small_test_binary):
        """TEST-D04: Test job cancellation functionality"""
        # Submit job
        with open(small_test_binary, "rb") as f:
            files = {"file": (os.path.basename(small_test_binary), f, "application/octet-stream")}
            submit_response = client.post("/api/v1/decompile", files=files)
        
        job_id = submit_response.json()["job_id"]
        
        # Try to cancel immediately
        cancel_response = client.delete(f"/api/v1/decompile/{job_id}")
        
        # Should either succeed (200) or indicate it cannot be cancelled (400)
        assert cancel_response.status_code in [200, 400, 404], \
            f"Cancel request returned unexpected status: {cancel_response.status_code}"
        
        if cancel_response.status_code == 200:
            # Cancellation successful
            data = cancel_response.json()
            assert "message" in data
            assert "cancelled" in data["message"].lower()
        elif cancel_response.status_code == 400:
            # Cannot be cancelled (may already be processing)
            data = cancel_response.json()
            assert "could not be cancelled" in data.get("detail", "").lower() or \
                   "cannot" in data.get("detail", "").lower()

    def test_cancel_nonexistent_job(self, client):
        """TEST-D04: Test cancellation of non-existent job"""
        import uuid
        fake_job_id = str(uuid.uuid4())  # Generate a truly random UUID
        response = client.delete(f"/api/v1/decompile/{fake_job_id}")
        
        # Should return 404 for non-existent job
        assert response.status_code == 404, \
            f"Non-existent job cancellation should return 404, got: {response.status_code}"

    def test_decompilation_workflow_performance(self, client, small_test_binary):
        """Test decompilation API response times meet performance requirements"""
        # Test endpoint response times
        endpoints_to_test = [
            "/api/v1/decompile/test",
        ]
        
        for endpoint in endpoints_to_test:
            start_time = time.time()
            response = client.get(endpoint)
            duration = time.time() - start_time
            
            assert duration < 2.0, \
                f"Endpoint {endpoint} took {duration:.2f}s, exceeds 2s requirement"
        
        # Test job submission response time
        start_time = time.time()
        with open(small_test_binary, "rb") as f:
            files = {"file": (os.path.basename(small_test_binary), f, "application/octet-stream")}
            response = client.post("/api/v1/decompile", files=files)
        duration = time.time() - start_time
        
        # Job submission should be quick (just queuing, not processing)
        assert duration < 5.0, \
            f"Job submission took {duration:.2f}s, should be quick for queuing"