"""
Performance tests for LLM provider response times and throughput.

Measures and validates LLM provider performance characteristics including
response times, token processing rates, and reliability metrics.
"""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from statistics import mean, median, stdev
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import pytest

from src.llm.providers.factory import LLMProviderFactory
from src.llm.base import LLMProvider
from src.core.config import get_settings
from tests.fixtures.llm_responses import (
    get_mock_response, get_provider_performance, simulate_provider_latency,
    simulate_provider_reliability
)
from tests.fixtures.assembly_samples import get_functions_by_criteria


@dataclass
class PerformanceMetrics:
    """Container for performance measurement results."""
    provider: str
    model: str
    operation_type: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    
    # Timing metrics (milliseconds)
    response_times: List[float] = field(default_factory=list)
    mean_response_time: float = 0.0
    median_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    std_dev_response_time: float = 0.0
    
    # Throughput metrics
    tokens_processed: int = 0
    total_duration: float = 0.0  # seconds
    requests_per_second: float = 0.0
    tokens_per_second: float = 0.0
    
    # Reliability metrics
    success_rate: float = 0.0
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    
    # Cost metrics
    total_cost: float = 0.0
    cost_per_request: float = 0.0
    cost_per_token: float = 0.0
    
    # Quality metrics
    quality_scores: List[float] = field(default_factory=list)
    mean_quality: float = 0.0
    
    def calculate_derived_metrics(self):
        """Calculate derived metrics from raw data."""
        if self.response_times:
            self.mean_response_time = mean(self.response_times)
            self.median_response_time = median(self.response_times)
            self.response_times.sort()
            n = len(self.response_times)
            self.p95_response_time = self.response_times[int(n * 0.95)]
            self.p99_response_time = self.response_times[int(n * 0.99)]
            if len(self.response_times) > 1:
                self.std_dev_response_time = stdev(self.response_times)
        
        if self.total_requests > 0:
            self.success_rate = self.successful_requests / self.total_requests
            self.error_rate = self.failed_requests / self.total_requests
        
        if self.total_duration > 0:
            self.requests_per_second = self.successful_requests / self.total_duration
            self.tokens_per_second = self.tokens_processed / self.total_duration
        
        if self.successful_requests > 0:
            self.cost_per_request = self.total_cost / self.successful_requests
        
        if self.tokens_processed > 0:
            self.cost_per_token = self.total_cost / self.tokens_processed
        
        if self.quality_scores:
            self.mean_quality = mean(self.quality_scores)


class LLMPerformanceTester:
    """Framework for testing LLM provider performance."""
    
    def __init__(self):
        self.settings = get_settings()
        self.results = {}
    
    async def run_response_time_test(
        self,
        provider: str,
        operation_type: str = "function_translation",
        num_requests: int = 50,
        complexity: str = "medium",
        use_mock: bool = True
    ) -> PerformanceMetrics:
        """
        Test response time characteristics for a provider.
        
        Args:
            provider: LLM provider name
            operation_type: Type of operation to test
            num_requests: Number of requests to make
            complexity: Complexity level for test data
            use_mock: Whether to use mock responses (faster, no API costs)
            
        Returns:
            PerformanceMetrics with timing results
        """
        metrics = PerformanceMetrics(
            provider=provider,
            model=f"{provider}-default",
            operation_type=operation_type,
            total_requests=num_requests,
            successful_requests=0,
            failed_requests=0
        )
        
        start_time = time.time()
        
        for i in range(num_requests):
            request_start = time.time()
            
            try:
                if use_mock:
                    # Use mock response with simulated latency
                    mock_response = get_mock_response(
                        provider=provider,
                        operation_type=operation_type,
                        complexity=complexity
                    )
                    
                    # Simulate realistic delay
                    simulated_delay = simulate_provider_latency(provider, mock_response.tokens_used)
                    await asyncio.sleep(simulated_delay / 1000.0)
                    
                    # Simulate reliability
                    if not simulate_provider_reliability(provider):
                        raise Exception("Simulated provider failure")
                    
                    response_time = (time.time() - request_start) * 1000
                    metrics.response_times.append(response_time)
                    metrics.tokens_processed += mock_response.tokens_used
                    metrics.quality_scores.append(mock_response.quality_score)
                    metrics.successful_requests += 1
                    
                    # Calculate cost (mock)
                    profile = get_provider_performance(provider)
                    request_cost = (mock_response.tokens_used / 1000) * profile["cost_per_1k_tokens"]
                    metrics.total_cost += request_cost
                
                else:
                    # Real API call (implement based on provider)
                    response = await self._make_real_api_call(provider, operation_type, complexity)
                    response_time = (time.time() - request_start) * 1000
                    metrics.response_times.append(response_time)
                    metrics.successful_requests += 1
                    # Add other metrics from real response
                
            except Exception as e:
                metrics.failed_requests += 1
                response_time = (time.time() - request_start) * 1000
                metrics.response_times.append(response_time)
        
        metrics.total_duration = time.time() - start_time
        metrics.calculate_derived_metrics()
        
        return metrics
    
    async def run_throughput_test(
        self,
        provider: str,
        concurrent_requests: int = 10,
        total_requests: int = 100,
        use_mock: bool = True
    ) -> PerformanceMetrics:
        """
        Test throughput characteristics with concurrent requests.
        
        Args:
            provider: LLM provider name
            concurrent_requests: Number of concurrent requests
            total_requests: Total requests to make
            use_mock: Whether to use mock responses
            
        Returns:
            PerformanceMetrics with throughput results
        """
        metrics = PerformanceMetrics(
            provider=provider,
            model=f"{provider}-default",
            operation_type="throughput_test",
            total_requests=total_requests,
            successful_requests=0,
            failed_requests=0
        )
        
        semaphore = asyncio.Semaphore(concurrent_requests)
        start_time = time.time()
        
        async def single_request():
            async with semaphore:
                request_start = time.time()
                try:
                    if use_mock:
                        mock_response = get_mock_response(
                            provider=provider,
                            operation_type="function_translation",
                            complexity="medium"
                        )
                        
                        # Simulate delay
                        simulated_delay = simulate_provider_latency(provider, mock_response.tokens_used)
                        await asyncio.sleep(simulated_delay / 1000.0)
                        
                        if not simulate_provider_reliability(provider):
                            raise Exception("Simulated failure")
                        
                        response_time = (time.time() - request_start) * 1000
                        return {
                            "success": True,
                            "response_time": response_time,
                            "tokens": mock_response.tokens_used,
                            "quality": mock_response.quality_score
                        }
                    else:
                        # Real API call
                        response = await self._make_real_api_call(provider, "function_translation", "medium")
                        response_time = (time.time() - request_start) * 1000
                        return {
                            "success": True,
                            "response_time": response_time,
                            "tokens": response.get("tokens_used", 100),
                            "quality": 8.0
                        }
                        
                except Exception:
                    response_time = (time.time() - request_start) * 1000
                    return {
                        "success": False,
                        "response_time": response_time,
                        "tokens": 0,
                        "quality": 0.0
                    }
        
        # Execute all requests concurrently
        tasks = [single_request() for _ in range(total_requests)]
        results = await asyncio.gather(*tasks)
        
        # Process results
        for result in results:
            metrics.response_times.append(result["response_time"])
            if result["success"]:
                metrics.successful_requests += 1
                metrics.tokens_processed += result["tokens"]
                metrics.quality_scores.append(result["quality"])
            else:
                metrics.failed_requests += 1
        
        metrics.total_duration = time.time() - start_time
        metrics.calculate_derived_metrics()
        
        return metrics
    
    async def run_stress_test(
        self,
        provider: str,
        duration_seconds: int = 60,
        max_concurrent: int = 50,
        use_mock: bool = True
    ) -> PerformanceMetrics:
        """
        Run stress test with increasing load over time.
        
        Args:
            provider: LLM provider name
            duration_seconds: Test duration
            max_concurrent: Maximum concurrent requests
            use_mock: Whether to use mock responses
            
        Returns:
            PerformanceMetrics with stress test results
        """
        metrics = PerformanceMetrics(
            provider=provider,
            model=f"{provider}-default",
            operation_type="stress_test",
            total_requests=0,
            successful_requests=0,
            failed_requests=0
        )
        
        start_time = time.time()
        end_time = start_time + duration_seconds
        
        # Gradually increase load
        current_concurrent = 1
        ramp_up_interval = duration_seconds / max_concurrent
        next_ramp_time = start_time + ramp_up_interval
        
        active_requests = set()
        
        async def single_request(request_id: int):
            request_start = time.time()
            try:
                if use_mock:
                    mock_response = get_mock_response(
                        provider=provider,
                        operation_type="function_translation",
                        complexity="medium"
                    )
                    
                    delay = simulate_provider_latency(provider, mock_response.tokens_used)
                    await asyncio.sleep(delay / 1000.0)
                    
                    if not simulate_provider_reliability(provider):
                        raise Exception("Simulated failure")
                    
                    return {
                        "success": True,
                        "response_time": (time.time() - request_start) * 1000,
                        "tokens": mock_response.tokens_used
                    }
                else:
                    # Real API call
                    await self._make_real_api_call(provider, "function_translation", "medium")
                    return {
                        "success": True,
                        "response_time": (time.time() - request_start) * 1000,
                        "tokens": 100
                    }
                    
            except Exception:
                return {
                    "success": False,
                    "response_time": (time.time() - request_start) * 1000,
                    "tokens": 0
                }
            finally:
                active_requests.discard(request_id)
        
        request_counter = 0
        
        while time.time() < end_time:
            current_time = time.time()
            
            # Ramp up concurrent requests
            if current_time >= next_ramp_time and current_concurrent < max_concurrent:
                current_concurrent += 1
                next_ramp_time += ramp_up_interval
            
            # Launch new requests to maintain concurrent level
            while len(active_requests) < current_concurrent and time.time() < end_time:
                request_id = request_counter
                request_counter += 1
                
                task = asyncio.create_task(single_request(request_id))
                active_requests.add(request_id)
                
                # Process completed requests
                if request_counter % 10 == 0:  # Check periodically
                    await asyncio.sleep(0.01)  # Small delay to allow processing
            
            await asyncio.sleep(0.1)  # Brief pause between iterations
        
        # Wait for remaining requests
        while active_requests:
            await asyncio.sleep(0.1)
        
        metrics.total_requests = request_counter
        metrics.total_duration = time.time() - start_time
        metrics.calculate_derived_metrics()
        
        return metrics
    
    async def _make_real_api_call(self, provider: str, operation_type: str, complexity: str) -> Dict[str, Any]:
        """Make a real API call to the LLM provider (placeholder implementation)."""
        # This would implement actual API calls to providers
        # For now, simulate with realistic delay
        await asyncio.sleep(0.5)  # Simulate network delay
        return {
            "content": f"Mock {operation_type} response from {provider}",
            "tokens_used": 100,
            "quality_score": 8.0
        }
    
    def generate_performance_report(self, metrics_list: List[PerformanceMetrics]) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.
        
        Args:
            metrics_list: List of performance metrics from different tests
            
        Returns:
            Detailed performance report
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {},
            "providers": {},
            "comparisons": {},
            "recommendations": []
        }
        
        # Group metrics by provider
        by_provider = {}
        for metrics in metrics_list:
            if metrics.provider not in by_provider:
                by_provider[metrics.provider] = []
            by_provider[metrics.provider].append(metrics)
        
        # Analyze each provider
        for provider, provider_metrics in by_provider.items():
            provider_summary = {
                "response_times": {
                    "mean": mean([m.mean_response_time for m in provider_metrics if m.mean_response_time > 0]),
                    "median": mean([m.median_response_time for m in provider_metrics if m.median_response_time > 0]),
                    "p95": mean([m.p95_response_time for m in provider_metrics if m.p95_response_time > 0])
                },
                "throughput": {
                    "requests_per_second": mean([m.requests_per_second for m in provider_metrics if m.requests_per_second > 0]),
                    "tokens_per_second": mean([m.tokens_per_second for m in provider_metrics if m.tokens_per_second > 0])
                },
                "reliability": {
                    "success_rate": mean([m.success_rate for m in provider_metrics]),
                    "error_rate": mean([m.error_rate for m in provider_metrics])
                },
                "cost": {
                    "cost_per_request": mean([m.cost_per_request for m in provider_metrics if m.cost_per_request > 0]),
                    "cost_per_token": mean([m.cost_per_token for m in provider_metrics if m.cost_per_token > 0])
                },
                "quality": {
                    "mean_quality": mean([m.mean_quality for m in provider_metrics if m.mean_quality > 0])
                }
            }
            
            report["providers"][provider] = provider_summary
        
        # Generate comparisons
        if len(by_provider) > 1:
            providers = list(by_provider.keys())
            
            # Speed comparison
            speed_ranking = sorted(providers, 
                key=lambda p: report["providers"][p]["response_times"]["mean"])
            report["comparisons"]["speed_ranking"] = speed_ranking
            
            # Cost comparison
            cost_ranking = sorted(providers,
                key=lambda p: report["providers"][p]["cost"]["cost_per_token"])
            report["comparisons"]["cost_ranking"] = cost_ranking
            
            # Quality comparison
            quality_ranking = sorted(providers,
                key=lambda p: report["providers"][p]["quality"]["mean_quality"], reverse=True)
            report["comparisons"]["quality_ranking"] = quality_ranking
        
        # Generate recommendations
        if "openai" in by_provider:
            openai_metrics = report["providers"]["openai"]
            if openai_metrics["response_times"]["mean"] > 2000:
                report["recommendations"].append("OpenAI response times are high - consider optimizing prompts or using faster models")
        
        if "anthropic" in by_provider:
            anthropic_metrics = report["providers"]["anthropic"]
            if anthropic_metrics["quality"]["mean_quality"] > 9.0:
                report["recommendations"].append("Anthropic shows excellent quality - recommend for complex translations")
        
        report["summary"] = {
            "total_providers_tested": len(by_provider),
            "total_tests_run": len(metrics_list),
            "fastest_provider": report["comparisons"].get("speed_ranking", [None])[0],
            "most_cost_effective": report["comparisons"].get("cost_ranking", [None])[0],
            "highest_quality": report["comparisons"].get("quality_ranking", [None])[0]
        }
        
        return report


# Test fixtures and utilities

@pytest.fixture
def performance_tester():
    """Fixture providing LLMPerformanceTester instance."""
    return LLMPerformanceTester()


@pytest.fixture
def mock_providers():
    """Fixture providing mock provider configurations."""
    return ["openai", "anthropic", "gemini", "ollama"]


# Performance test cases

@pytest.mark.performance
async def test_response_time_all_providers(performance_tester, mock_providers):
    """Test response times across all providers."""
    results = []
    
    for provider in mock_providers:
        metrics = await performance_tester.run_response_time_test(
            provider=provider,
            num_requests=20,
            use_mock=True
        )
        results.append(metrics)
        
        # Assertions for response time requirements
        assert metrics.mean_response_time < 3000, f"{provider} response time too high: {metrics.mean_response_time}ms"
        assert metrics.success_rate > 0.9, f"{provider} success rate too low: {metrics.success_rate}"
    
    return results


@pytest.mark.performance 
async def test_throughput_comparison(performance_tester, mock_providers):
    """Test throughput characteristics across providers."""
    results = []
    
    for provider in mock_providers:
        metrics = await performance_tester.run_throughput_test(
            provider=provider,
            concurrent_requests=5,
            total_requests=50,
            use_mock=True
        )
        results.append(metrics)
        
        # Assertions for throughput requirements
        assert metrics.requests_per_second > 0.5, f"{provider} throughput too low: {metrics.requests_per_second} req/sec"
        assert metrics.tokens_per_second > 10, f"{provider} token processing too slow: {metrics.tokens_per_second} tok/sec"
    
    return results


@pytest.mark.performance
@pytest.mark.slow
async def test_stress_test_single_provider(performance_tester):
    """Run stress test on a single provider."""
    provider = "openai"  # Most stable for stress testing
    
    metrics = await performance_tester.run_stress_test(
        provider=provider,
        duration_seconds=30,  # Shorter for testing
        max_concurrent=20,
        use_mock=True
    )
    
    # Stress test assertions
    assert metrics.success_rate > 0.8, f"Stress test success rate too low: {metrics.success_rate}"
    assert metrics.total_requests > 50, f"Too few requests processed: {metrics.total_requests}"
    
    return metrics


@pytest.mark.performance
async def test_generate_performance_report(performance_tester, mock_providers):
    """Test performance report generation."""
    all_metrics = []
    
    # Run various tests
    for provider in mock_providers[:2]:  # Test with 2 providers
        response_metrics = await performance_tester.run_response_time_test(
            provider=provider,
            num_requests=10,
            use_mock=True
        )
        all_metrics.append(response_metrics)
        
        throughput_metrics = await performance_tester.run_throughput_test(
            provider=provider,
            concurrent_requests=3,
            total_requests=20,
            use_mock=True
        )
        all_metrics.append(throughput_metrics)
    
    # Generate report
    report = performance_tester.generate_performance_report(all_metrics)
    
    # Validate report structure
    assert "timestamp" in report
    assert "summary" in report
    assert "providers" in report
    assert "comparisons" in report
    assert "recommendations" in report
    
    assert len(report["providers"]) == 2
    assert "speed_ranking" in report["comparisons"]
    assert "cost_ranking" in report["comparisons"]
    
    return report


if __name__ == "__main__":
    # Example usage
    async def main():
        tester = LLMPerformanceTester()
        
        print("Running performance tests...")
        
        # Test each provider
        providers = ["openai", "anthropic", "gemini", "ollama"]
        all_metrics = []
        
        for provider in providers:
            print(f"Testing {provider}...")
            
            # Response time test
            response_metrics = await tester.run_response_time_test(
                provider=provider,
                num_requests=20,
                use_mock=True
            )
            all_metrics.append(response_metrics)
            print(f"  Mean response time: {response_metrics.mean_response_time:.1f}ms")
            print(f"  Success rate: {response_metrics.success_rate:.2f}")
            
            # Throughput test
            throughput_metrics = await tester.run_throughput_test(
                provider=provider,
                concurrent_requests=5,
                total_requests=30,
                use_mock=True
            )
            all_metrics.append(throughput_metrics)
            print(f"  Throughput: {throughput_metrics.requests_per_second:.1f} req/sec")
        
        # Generate report
        report = tester.generate_performance_report(all_metrics)
        print("\nPerformance Report:")
        print(f"Fastest provider: {report['summary']['fastest_provider']}")
        print(f"Most cost-effective: {report['summary']['most_cost_effective']}")
        print(f"Highest quality: {report['summary']['highest_quality']}")
    
    asyncio.run(main())