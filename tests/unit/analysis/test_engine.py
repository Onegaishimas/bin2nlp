"""
Unit tests for binary analysis engine.

Tests the main BinaryAnalysisEngine with comprehensive mocking of all processors,
error recovery, timeout handling, and result aggregation.
"""

import pytest
import tempfile
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any

from src.analysis.engine import (
    BinaryAnalysisEngine,
    EngineConfig,
    ProcessorConfig,
    AggregatedAnalysisResult,
    ProcessorResult,
    AnalysisPhase,
    BinaryAnalysisEngineException
)
from src.models.shared.enums import AnalysisDepth
from src.analysis.processors.format_detector import FormatDetectionResult
from src.analysis.processors.function_analyzer import FunctionAnalysisResult
from src.analysis.processors.security_scanner import SecurityAnalysisResult
from src.analysis.processors.string_extractor import StringExtractionResult
from src.models.shared.enums import FileFormat, Platform


class TestEngineConfig:
    """Test EngineConfig validation."""
    
    def test_config_defaults(self):
        """Test default configuration values."""
        config = EngineConfig()
        
        assert config.analysis_depth == AnalysisDepth.STANDARD
        assert config.focus_areas == set()
        assert config.max_analysis_time == 1200
        assert config.parallel_execution is True
        assert config.stop_on_critical_error is False
        
        # Check processor configs
        assert config.format_detection.required is True
        assert config.format_detection.priority == 1
        assert config.function_analysis.priority == 2
        assert config.security_scanning.priority == 3
        assert config.string_extraction.priority == 4
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = EngineConfig(
            analysis_depth=AnalysisDepth.DEEP,
            focus_areas={"malware", "crypto"},
            max_analysis_time=3600
        )
        assert config.analysis_depth == AnalysisDepth.DEEP
        assert "malware" in config.focus_areas
        assert config.max_analysis_time == 3600
        
        # Invalid focus areas
        with pytest.raises(ValueError, match="Invalid focus areas"):
            EngineConfig(focus_areas={"invalid_area"})


class TestProcessorConfig:
    """Test ProcessorConfig validation."""
    
    def test_processor_config_defaults(self):
        """Test default processor configuration."""
        config = ProcessorConfig()
        
        assert config.enabled is True
        assert config.timeout_seconds == 300
        assert config.priority == 1
        assert config.required is False
    
    def test_processor_config_validation(self):
        """Test processor configuration validation."""
        # Valid config
        config = ProcessorConfig(
            timeout_seconds=600,
            priority=5,
            required=True
        )
        assert config.timeout_seconds == 600
        assert config.priority == 5
        assert config.required is True
        
        # Test constraints
        with pytest.raises(ValueError):
            ProcessorConfig(timeout_seconds=10)  # Should be >= 30
        
        with pytest.raises(ValueError):
            ProcessorConfig(priority=0)  # Should be >= 1


class TestBinaryAnalysisEngine:
    """Test BinaryAnalysisEngine functionality."""
    
    @pytest.fixture
    def engine_config(self):
        """Create test engine configuration."""
        return EngineConfig(
            analysis_depth=AnalysisDepth.STANDARD,
            parallel_execution=True
        )
    
    @pytest.fixture
    def engine(self, engine_config):
        """Create BinaryAnalysisEngine instance."""
        return BinaryAnalysisEngine(engine_config)
    
    @pytest.fixture
    def test_file_path(self):
        """Create temporary test file."""
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp_file:
            tmp_file.write(b'MZ' + b'\x00' * 1000)  # Mock PE content
            tmp_file.flush()
            yield tmp_file.name
        
        try:
            os.unlink(tmp_file.name)
        except FileNotFoundError:
            pass
    
    @pytest.fixture
    def mock_format_result(self):
        """Mock format detection result."""
        return FormatDetectionResult(
            primary_format=FileFormat.PE,
            confidence=0.95,
            magika_type="exe",
            magika_confidence=0.98,
            header_analysis={"dos_header": True, "nt_header": True},
            platform=Platform.WINDOWS,
            warnings=[]
        )
    
    @pytest.fixture
    def mock_function_result(self):
        """Mock function analysis result."""
        return Mock(spec=FunctionAnalysisResult)
    
    @pytest.fixture
    def mock_security_result(self):
        """Mock security analysis result."""
        return Mock(spec=SecurityAnalysisResult)
    
    @pytest.fixture
    def mock_string_result(self):
        """Mock string extraction result."""
        return Mock(spec=StringExtractionResult)
    
    def test_engine_initialization(self, engine):
        """Test engine initialization."""
        assert engine.config is not None
        assert engine.settings is not None
        assert engine.format_detector is not None
        assert engine.function_analyzer is not None
        assert engine.security_scanner is not None
        assert engine.string_extractor is not None
        assert engine.recovery_manager is not None
    
    @pytest.mark.asyncio
    async def test_analyze_binary_success(
        self, 
        engine, 
        test_file_path,
        mock_format_result,
        mock_function_result,
        mock_security_result,
        mock_string_result
    ):
        """Test successful binary analysis."""
        # Mock all processors
        with patch.object(engine.format_detector, 'detect_format', return_value=mock_format_result), \
             patch.object(engine.function_analyzer, 'analyze_functions', return_value=mock_function_result), \
             patch.object(engine.security_scanner, 'scan_binary', return_value=mock_security_result), \
             patch.object(engine.string_extractor, 'extract_strings', return_value=mock_string_result), \
             patch.object(engine, '_calculate_file_hash', return_value="abcd1234" * 8):
            
            result = await engine.analyze_binary(test_file_path)
            
            assert isinstance(result, AggregatedAnalysisResult)
            assert result.analysis_success is True
            assert result.file_path == test_file_path
            assert len(result.file_hash) == 64  # SHA-256
            assert result.total_analysis_time_ms > 0
            assert len(result.processor_results) > 0
            
            # Check that all results are included
            assert result.format_info is mock_format_result
            assert result.function_analysis is mock_function_result
            assert result.security_findings is mock_security_result
            assert result.string_analysis is mock_string_result
    
    @pytest.mark.asyncio
    async def test_analyze_binary_file_not_found(self, engine):
        """Test analysis with non-existent file."""
        with pytest.raises(BinaryAnalysisEngineException, match="File not found"):
            await engine.analyze_binary("/nonexistent/file.exe")
    
    @pytest.mark.asyncio
    async def test_analyze_binary_processor_failure(self, engine, test_file_path):
        """Test analysis with processor failures."""
        # Mock format detector to succeed but function analyzer to fail
        mock_format_result = Mock()
        
        with patch.object(engine.format_detector, 'detect_format', return_value=mock_format_result), \
             patch.object(engine.function_analyzer, 'analyze_functions', side_effect=Exception("Function analysis failed")), \
             patch.object(engine.security_scanner, 'scan_binary', return_value=Mock()), \
             patch.object(engine.string_extractor, 'extract_strings', return_value=Mock()), \
             patch.object(engine, '_calculate_file_hash', return_value="abcd1234" * 8):
            
            result = await engine.analyze_binary(test_file_path)
            
            # Should still complete with partial results
            assert isinstance(result, AggregatedAnalysisResult)
            assert result.format_info is mock_format_result
            
            # Check error tracking
            assert len(result.errors_encountered) > 0
            assert any("Function analysis failed" in error for error in result.errors_encountered)
    
    @pytest.mark.asyncio
    async def test_parallel_execution(self, engine, test_file_path):
        """Test parallel processor execution."""
        engine.config.parallel_execution = True
        
        # Mock processors with delays to test parallelism
        async def delayed_function_analysis(*args, **kwargs):
            await asyncio.sleep(0.1)
            return Mock()
        
        async def delayed_security_scan(*args, **kwargs):
            await asyncio.sleep(0.1)
            return Mock()
        
        async def delayed_string_extraction(*args, **kwargs):
            await asyncio.sleep(0.1)
            return Mock()
        
        with patch.object(engine.format_detector, 'detect_format', return_value=Mock()), \
             patch.object(engine.function_analyzer, 'analyze_functions', side_effect=delayed_function_analysis), \
             patch.object(engine.security_scanner, 'scan_binary', side_effect=delayed_security_scan), \
             patch.object(engine.string_extractor, 'extract_strings', side_effect=delayed_string_extraction), \
             patch.object(engine, '_calculate_file_hash', return_value="abcd1234" * 8):
            
            import time
            start_time = time.time()
            result = await engine.analyze_binary(test_file_path)
            end_time = time.time()
            
            # Parallel execution should be faster than sequential
            # (3 * 0.1s delays should take ~0.1s in parallel vs ~0.3s sequential)
            assert (end_time - start_time) < 0.25
            assert result.analysis_success
    
    @pytest.mark.asyncio
    async def test_sequential_execution(self, engine, test_file_path):
        """Test sequential processor execution."""
        engine.config.parallel_execution = False
        
        execution_order = []
        
        async def track_function_analysis(*args, **kwargs):
            execution_order.append("function")
            return Mock()
        
        async def track_security_scan(*args, **kwargs):
            execution_order.append("security")
            return Mock()
        
        async def track_string_extraction(*args, **kwargs):
            execution_order.append("strings")
            return Mock()
        
        with patch.object(engine.format_detector, 'detect_format', return_value=Mock()), \
             patch.object(engine.function_analyzer, 'analyze_functions', side_effect=track_function_analysis), \
             patch.object(engine.security_scanner, 'scan_binary', side_effect=track_security_scan), \
             patch.object(engine.string_extractor, 'extract_strings', side_effect=track_string_extraction), \
             patch.object(engine, '_calculate_file_hash', return_value="abcd1234" * 8):
            
            result = await engine.analyze_binary(test_file_path)
            
            # Should execute in order
            assert len(execution_order) == 3
            assert "function" in execution_order
            assert "security" in execution_order
            assert "strings" in execution_order
            assert result.analysis_success
    
    @pytest.mark.asyncio
    async def test_format_detection_required_failure(self, engine, test_file_path):
        """Test behavior when required format detection fails."""
        engine.config.format_detection.required = True
        
        with patch.object(engine.format_detector, 'detect_format', side_effect=Exception("Format detection failed")), \
             patch.object(engine, '_calculate_file_hash', return_value="abcd1234" * 8):
            
            result = await engine.analyze_binary(test_file_path)
            
            # Should fail analysis due to required processor failure
            assert len(result.errors_encountered) > 0
            # Other processors should not run if format detection is required and fails
            assert result.function_analysis is None
    
    @pytest.mark.asyncio
    async def test_error_recovery_integration(self, engine, test_file_path):
        """Test error recovery system integration."""
        # Mock a processor to fail initially then succeed
        call_count = 0
        
        async def failing_then_succeeding(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First attempt failed")
            return Mock()
        
        with patch.object(engine.format_detector, 'detect_format', return_value=Mock()), \
             patch.object(engine.function_analyzer, 'analyze_functions', side_effect=failing_then_succeeding), \
             patch.object(engine.security_scanner, 'scan_binary', return_value=Mock()), \
             patch.object(engine.string_extractor, 'extract_strings', return_value=Mock()), \
             patch.object(engine, '_calculate_file_hash', return_value="abcd1234" * 8):
            
            result = await engine.analyze_binary(test_file_path)
            
            # Should have recovery information
            assert len(result.recovery_actions_taken) >= 0
            assert result.error_recovery_summary is not None
            # Should succeed due to retry
            assert result.analysis_success
    
    def test_create_function_config(self, engine):
        """Test function analysis configuration creation."""
        # Test different analysis depths
        engine.config.analysis_depth = AnalysisDepth.QUICK
        quick_config = engine._create_function_config()
        assert hasattr(quick_config, 'analyze_calls')
        assert quick_config.analyze_calls is False
        
        engine.config.analysis_depth = AnalysisDepth.DEEP
        deep_config = engine._create_function_config()
        assert deep_config.analyze_calls is True
        assert deep_config.extract_signatures is True
        
        engine.config.analysis_depth = AnalysisDepth.STANDARD
        standard_config = engine._create_function_config()
        assert standard_config is not None
    
    def test_create_security_config(self, engine):
        """Test security scanning configuration creation."""
        # Test with focus areas
        engine.config.focus_areas = {"malware", "crypto"}
        config = engine._create_security_config()
        
        assert hasattr(config, 'scan_network_operations')
        assert config.scan_network_operations is True  # malware focus
        assert config.scan_cryptographic_operations is True  # crypto focus
    
    def test_create_string_config(self, engine):
        """Test string extraction configuration creation."""
        # Test different analysis depths
        engine.config.analysis_depth = AnalysisDepth.QUICK
        quick_config = engine._create_string_config()
        assert quick_config.min_length == 6
        assert quick_config.max_strings == 200
        assert quick_config.significance_threshold == 0.5
        
        engine.config.analysis_depth = AnalysisDepth.DEEP
        deep_config = engine._create_string_config()
        assert deep_config.min_length == 3
        assert deep_config.max_strings == 2000
        assert deep_config.significance_threshold == 0.2
    
    def test_assess_risk_level(self, engine):
        """Test risk level assessment."""
        # Create mock result with varying risk factors
        result = AggregatedAnalysisResult(
            file_path="/test/path",
            file_hash="a" * 64,
            analysis_config=engine.config,
            total_analysis_time_ms=1000,
            start_timestamp="2023-01-01 00:00:00",
            end_timestamp="2023-01-01 00:01:00",
            analysis_success=True,
            overall_confidence=0.8
        )
        
        # Mock security findings
        mock_security = Mock()
        mock_security.total_findings = 5
        result.security_findings = mock_security
        
        # Mock string analysis
        mock_strings = Mock()
        mock_strings.categories_found = {"credential": 2, "crypto_key": 1}
        result.string_analysis = mock_strings
        
        risk_level = engine._assess_risk_level(result)
        assert risk_level in ["minimal", "low", "medium", "high"]
    
    def test_extract_key_findings(self, engine):
        """Test key findings extraction."""
        result = AggregatedAnalysisResult(
            file_path="/test/path",
            file_hash="a" * 64,
            analysis_config=engine.config,
            total_analysis_time_ms=1000,
            start_timestamp="2023-01-01 00:00:00",
            end_timestamp="2023-01-01 00:01:00",
            analysis_success=True,
            overall_confidence=0.8
        )
        
        # Mock format info
        result.format_info = Mock()
        result.format_info.detected_format = "PE"
        result.format_info.platform = "Windows"
        
        # Mock function analysis
        result.function_analysis = Mock()
        result.function_analysis.functions_found = 25
        
        # Mock security findings
        result.security_findings = Mock()
        result.security_findings.total_findings = 3
        
        findings = engine._extract_key_findings(result)
        
        assert len(findings) > 0
        assert any("PE" in finding for finding in findings)
        assert any("25 functions" in finding for finding in findings)
    
    def test_generate_recommendations(self, engine):
        """Test security recommendations generation."""
        result = AggregatedAnalysisResult(
            file_path="/test/path",
            file_hash="a" * 64,
            analysis_config=engine.config,
            total_analysis_time_ms=1000,
            start_timestamp="2023-01-01 00:00:00",
            end_timestamp="2023-01-01 00:01:00",
            analysis_success=True,
            overall_confidence=0.8
        )
        result.risk_level = "high"
        
        # Mock security findings
        result.security_findings = Mock()
        result.security_findings.total_findings = 10
        
        # Mock string analysis with credentials
        result.string_analysis = Mock()
        result.string_analysis.categories_found = {"credential": 3, "crypto_key": 1}
        
        recommendations = engine._generate_recommendations(result)
        
        assert len(recommendations) > 0
        assert any("credential" in rec.lower() for rec in recommendations)
        assert any("review" in rec.lower() or "analyze" in rec.lower() for rec in recommendations)
    
    def test_get_supported_formats(self, engine):
        """Test supported formats retrieval."""
        formats = engine.get_supported_formats()
        
        assert len(formats) > 0
        assert "PE" in formats or "pe" in formats
        assert "ELF" in formats or "elf" in formats
    
    def test_get_analysis_capabilities(self, engine):
        """Test analysis capabilities retrieval."""
        capabilities = engine.get_analysis_capabilities()
        
        assert "processors" in capabilities
        assert "analysis_depths" in capabilities
        assert "supported_formats" in capabilities
        assert "focus_areas" in capabilities
        
        # Check processors
        processors = capabilities["processors"]
        assert len(processors) >= 4
        processor_names = [p["name"] for p in processors]
        assert "format_detector" in processor_names
        assert "function_analyzer" in processor_names
        assert "security_scanner" in processor_names
        assert "string_extractor" in processor_names


class TestBinaryAnalysisEngineEdgeCases:
    """Test edge cases and error scenarios."""
    
    @pytest.fixture
    def engine(self):
        """Create BinaryAnalysisEngine with default config."""
        return BinaryAnalysisEngine()
    
    @pytest.mark.asyncio
    async def test_concurrent_analyses(self, engine):
        """Test concurrent binary analyses."""
        # Create multiple test files
        test_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(suffix=f'_test_{i}.exe', delete=False) as tmp_file:
                tmp_file.write(b'MZ' + bytes([i]) * 100)
                tmp_file.flush()
                test_files.append(tmp_file.name)
        
        try:
            # Mock all processors to return different results
            with patch.object(engine.format_detector, 'detect_format', return_value=Mock()), \
                 patch.object(engine.function_analyzer, 'analyze_functions', return_value=Mock()), \
                 patch.object(engine.security_scanner, 'scan_binary', return_value=Mock()), \
                 patch.object(engine.string_extractor, 'extract_strings', return_value=Mock()), \
                 patch.object(engine, '_calculate_file_hash', return_value="abcd1234" * 8):
                
                # Run concurrent analyses
                tasks = [engine.analyze_binary(file_path) for file_path in test_files]
                results = await asyncio.gather(*tasks)
                
                assert len(results) == 3
                for result in results:
                    assert isinstance(result, AggregatedAnalysisResult)
                    assert result.analysis_success
                
        finally:
            # Cleanup test files
            for file_path in test_files:
                try:
                    os.unlink(file_path)
                except FileNotFoundError:
                    pass
    
    @pytest.mark.asyncio
    async def test_processor_timeout_handling(self, engine):
        """Test processor timeout handling."""
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp_file:
            tmp_file.write(b'test')
            tmp_file.flush()
            
            try:
                # Mock a processor to timeout
                async def timeout_processor(*args, **kwargs):
                    await asyncio.sleep(10)  # Long delay
                    return Mock()
                
                # Set short timeout
                engine.config.function_analysis.timeout_seconds = 1
                
                with patch.object(engine.format_detector, 'detect_format', return_value=Mock()), \
                     patch.object(engine.function_analyzer, 'analyze_functions', side_effect=timeout_processor), \
                     patch.object(engine.security_scanner, 'scan_binary', return_value=Mock()), \
                     patch.object(engine.string_extractor, 'extract_strings', return_value=Mock()), \
                     patch.object(engine, '_calculate_file_hash', return_value="abcd1234" * 8):
                    
                    result = await engine.analyze_binary(tmp_file.name)
                    
                    # Should complete despite timeout
                    assert isinstance(result, AggregatedAnalysisResult)
                    # Should have error information
                    assert len(result.errors_encountered) >= 0
                    
            finally:
                os.unlink(tmp_file.name)
    
    @pytest.mark.asyncio
    async def test_memory_intensive_analysis(self, engine):
        """Test handling of memory-intensive analysis scenarios."""
        with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmp_file:
            tmp_file.write(b'MZ' + b'A' * 10000)  # Larger test file
            tmp_file.flush()
            
            try:
                # Mock processors to return large datasets
                large_format_result = Mock()
                large_function_result = Mock()
                large_security_result = Mock()
                large_string_result = Mock()
                
                with patch.object(engine.format_detector, 'detect_format', return_value=large_format_result), \
                     patch.object(engine.function_analyzer, 'analyze_functions', return_value=large_function_result), \
                     patch.object(engine.security_scanner, 'scan_binary', return_value=large_security_result), \
                     patch.object(engine.string_extractor, 'extract_strings', return_value=large_string_result), \
                     patch.object(engine, '_calculate_file_hash', return_value="abcd1234" * 8):
                    
                    result = await engine.analyze_binary(tmp_file.name)
                    
                    # Should handle large datasets appropriately
                    assert isinstance(result, AggregatedAnalysisResult)
                    assert result.total_analysis_time_ms > 0
                    
            finally:
                os.unlink(tmp_file.name)