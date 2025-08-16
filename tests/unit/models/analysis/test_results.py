"""
Unit tests for analysis result models.

Tests the AnalysisResult, SecurityFindings, FunctionInfo, and related
functionality for representing binary analysis results.
"""

import pytest
from datetime import datetime, timezone
from uuid import UUID, uuid4
from typing import List, Dict, Any

from src.models.shared.enums import JobStatus, AnalysisDepth, FileFormat, Platform
from src.models.analysis.results import (
    AnalysisResult, SecurityFindings, FunctionInfo, ImportInfo, 
    StringExtraction
)


class TestFunctionInfo:
    """Test cases for FunctionInfo model."""
    
    def test_basic_instantiation(self):
        """Test basic function info creation."""
        func_info = FunctionInfo(
            name="main",
            address="0x401000",
            size=256
        )
        
        assert func_info.name == "main"
        assert func_info.address == "0x401000"
        assert func_info.size == 256
        assert func_info.calls_to == []
        assert func_info.calls_from == []
        assert func_info.is_exported is False
        assert func_info.is_imported is False
    
    def test_with_call_relationships(self):
        """Test function with call relationships."""
        func_info = FunctionInfo(
            name="main",
            address="0x401000", 
            size=256,
            calls_to=["helper", "utility"],
            calls_from=["_start"]
        )
        
        assert len(func_info.calls_to) == 2
        assert len(func_info.calls_from) == 1
        assert "helper" in func_info.calls_to
        assert "_start" in func_info.calls_from
    
    def test_function_type_detection(self):
        """Test function type detection."""
        # Exported function
        exported_func = FunctionInfo(
            name="DllMain",
            address="0x401000",
            size=128,
            is_exported=True
        )
        assert exported_func.is_exported
        assert not exported_func.is_imported
        assert exported_func.get_function_type() == "exported"
        
        # Imported function
        imported_func = FunctionInfo(
            name="MessageBoxA",
            address="0x405000",
            size=0,
            is_imported=True
        )
        assert imported_func.is_imported
        assert not imported_func.is_exported
        assert imported_func.get_function_type() == "imported"
        
        # Internal function
        internal_func = FunctionInfo(
            name="helper",
            address="0x401100",
            size=64
        )
        assert not internal_func.is_exported
        assert not internal_func.is_imported
        assert internal_func.get_function_type() == "internal"
    
    def test_call_graph_metrics(self):
        """Test call graph analysis metrics."""
        func_info = FunctionInfo(
            name="main",
            address="0x401000",
            size=256,
            calls_to=["helper", "utility", "cleanup"],
            calls_from=["_start"]
        )
        
        assert func_info.get_outbound_call_count() == 3
        assert func_info.get_inbound_call_count() == 1
        assert func_info.is_leaf_function() is False  # Has outbound calls
        assert func_info.is_entry_point() is False  # Has inbound calls
    
    def test_complexity_estimation(self):
        """Test function complexity estimation."""
        # Simple function
        simple_func = FunctionInfo(
            name="getter",
            address="0x401000",
            size=32,
            calls_to=[]
        )
        complexity = simple_func.estimate_complexity()
        assert complexity == "low"
        
        # Complex function
        complex_func = FunctionInfo(
            name="main",
            address="0x401000",
            size=2048,
            calls_to=["f1", "f2", "f3", "f4", "f5", "f6"]
        )
        complexity = complex_func.estimate_complexity()
        assert complexity in ["medium", "high"]


class TestImportInfo:
    """Test cases for ImportInfo model."""
    
    def test_basic_instantiation(self):
        """Test basic import info creation."""
        import_info = ImportInfo(
            library="kernel32.dll",
            function="CreateFileA",
            address="0x405000"
        )
        
        assert import_info.library == "kernel32.dll"
        assert import_info.function == "CreateFileA"
        assert import_info.address == "0x405000"
        assert import_info.ordinal is None
        assert import_info.is_delayed is False
    
    def test_with_ordinal(self):
        """Test import with ordinal number."""
        import_info = ImportInfo(
            library="user32.dll",
            function="MessageBoxA",
            address="0x405010",
            ordinal=123
        )
        
        assert import_info.ordinal == 123
        assert import_info.has_ordinal()
    
    def test_delayed_import(self):
        """Test delayed import handling."""
        import_info = ImportInfo(
            library="shell32.dll",
            function="ShellExecuteA",
            address="0x405020",
            is_delayed=True
        )
        
        assert import_info.is_delayed is True
    
    def test_security_classification(self):
        """Test security-related import classification."""
        # File operation
        file_import = ImportInfo(
            library="kernel32.dll",
            function="CreateFileA",
            address="0x405000"
        )
        assert file_import.get_security_category() == "file_operations"
        
        # Network operation
        network_import = ImportInfo(
            library="ws2_32.dll",
            function="WSAStartup",
            address="0x405010"
        )
        assert network_import.get_security_category() == "network_operations"
        
        # Process operation
        process_import = ImportInfo(
            library="kernel32.dll",
            function="CreateProcessA",
            address="0x405020"
        )
        assert process_import.get_security_category() == "process_operations"
    
    def test_risk_assessment(self):
        """Test import risk level assessment."""
        # High risk import
        high_risk = ImportInfo(
            library="kernel32.dll",
            function="VirtualAlloc",
            address="0x405000"
        )
        assert high_risk.get_risk_level() in ["medium", "high"]
        
        # Low risk import
        low_risk = ImportInfo(
            library="user32.dll",
            function="MessageBoxA",
            address="0x405010"
        )
        assert low_risk.get_risk_level() in ["low", "medium"]


class TestStringExtraction:
    """Test cases for StringExtraction model."""
    
    def test_basic_instantiation(self):
        """Test basic string info creation."""
        string_info = StringExtraction(
            content="Hello World",
            address="0x403000",
            encoding="ascii"
        )
        
        assert string_info.content == "Hello World"
        assert string_info.address == "0x403000"
        assert string_info.encoding == "ascii"
        assert string_info.length == len("Hello World")
        assert string_info.context is None
    
    def test_with_context(self):
        """Test string with context information."""
        string_info = StringExtraction(
            content="Error: File not found",
            address="0x403010",
            encoding="ascii",
            context="error_message"
        )
        
        assert string_info.context == "error_message"
        assert string_info.is_error_message()
    
    def test_string_classification(self):
        """Test string content classification."""
        # URL string
        url_string = StringExtraction(
            content="http://example.com",
            address="0x403000",
            encoding="ascii"
        )
        assert url_string.get_string_type() == "url"
        assert url_string.is_url()
        
        # File path string
        path_string = StringExtraction(
            content="C:\\Windows\\System32\\file.exe",
            address="0x403010",
            encoding="ascii"
        )
        assert path_string.get_string_type() == "file_path"
        assert path_string.is_file_path()
        
        # Registry key string
        registry_string = StringExtraction(
            content="HKEY_LOCAL_MACHINE\\Software\\Test",
            address="0x403020",
            encoding="ascii"
        )
        assert registry_string.get_string_type() == "registry_key"
        assert registry_string.is_registry_key()
    
    def test_security_significance(self):
        """Test security significance assessment."""
        # Suspicious string
        suspicious_string = StringExtraction(
            content="powershell.exe -ExecutionPolicy Bypass",
            address="0x403000",
            encoding="ascii"
        )
        assert suspicious_string.get_security_significance() in ["medium", "high"]
        
        # Innocuous string
        normal_string = StringExtraction(
            content="Hello World",
            address="0x403010",
            encoding="ascii"
        )
        assert normal_string.get_security_significance() == "low"
    
    def test_encoding_validation(self):
        """Test string encoding validation."""
        # Valid ASCII
        ascii_string = StringExtraction(
            content="Hello",
            address="0x403000",
            encoding="ascii"
        )
        assert ascii_string.is_valid_encoding()
        
        # Unicode string
        unicode_string = StringExtraction(
            content="Hello 世界",
            address="0x403010",
            encoding="utf-16"
        )
        assert unicode_string.is_valid_encoding()


class TestSecurityFindings:
    """Test cases for SecurityFindings model."""
    
    def test_basic_instantiation(self):
        """Test basic security findings creation."""
        findings = SecurityFindings(
            risk_score=7.5,
            network_behaviors=["HTTP requests", "DNS queries"],
            file_operations=["File creation", "File deletion"],
            suspicious_patterns=["Code injection"],
            cryptographic_usage=[]
        )
        
        assert findings.risk_score == 7.5
        assert len(findings.network_behaviors) == 2
        assert len(findings.file_operations) == 2
        assert len(findings.suspicious_patterns) == 1
        assert len(findings.cryptographic_usage) == 0
    
    def test_risk_level_classification(self):
        """Test risk level classification."""
        # Low risk
        low_risk = SecurityFindings(risk_score=2.0)
        assert low_risk.get_risk_level() == "low"
        
        # Medium risk
        medium_risk = SecurityFindings(risk_score=5.0)
        assert medium_risk.get_risk_level() == "medium"
        
        # High risk
        high_risk = SecurityFindings(risk_score=8.5)
        assert high_risk.get_risk_level() == "high"
    
    def test_finding_aggregation(self):
        """Test security finding aggregation."""
        findings = SecurityFindings(
            risk_score=6.0,
            network_behaviors=["HTTP", "TCP socket"],
            file_operations=["File write", "Registry modify"],
            suspicious_patterns=["API hooking", "Process injection"],
            cryptographic_usage=["AES encryption"]
        )
        
        total_findings = findings.get_total_finding_count()
        assert total_findings == 6  # 2+2+2+1-1
        
        by_category = findings.get_findings_by_category()
        assert by_category["network"] == 2
        assert by_category["file_system"] == 2
        assert by_category["suspicious"] == 2
        assert by_category["cryptographic"] == 1
    
    def test_severity_assessment(self):
        """Test individual finding severity assessment."""
        findings = SecurityFindings(
            risk_score=7.0,
            suspicious_patterns=["Code injection", "API hooking", "Process hollowing"]
        )
        
        severity_breakdown = findings.get_severity_breakdown()
        assert "high" in severity_breakdown
        assert "medium" in severity_breakdown
        assert severity_breakdown["total"] == 3
    
    def test_mitigation_recommendations(self):
        """Test mitigation recommendations."""
        findings = SecurityFindings(
            risk_score=8.0,
            network_behaviors=["Outbound connections"],
            suspicious_patterns=["Code injection"]
        )
        
        recommendations = findings.get_mitigation_recommendations()
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        assert any("network" in rec.lower() for rec in recommendations)


class TestAnalysisStatistics:
    """Test cases for AnalysisStatistics model."""
    
    def test_basic_instantiation(self):
        """Test basic statistics creation."""
        stats = AnalysisStatistics(
            total_functions=150,
            total_imports=25,
            total_strings=300,
            analysis_duration_seconds=120.5,
            confidence_score=0.92
        )
        
        assert stats.total_functions == 150
        assert stats.total_imports == 25
        assert stats.total_strings == 300
        assert stats.analysis_duration_seconds == 120.5
        assert stats.confidence_score == 0.92
    
    def test_performance_metrics(self):
        """Test performance calculation methods."""
        stats = AnalysisStatistics(
            total_functions=100,
            total_imports=20,
            total_strings=500,
            analysis_duration_seconds=60.0,
            file_size_bytes=1024 * 1024  # 1MB
        )
        
        throughput = stats.get_processing_throughput()
        assert throughput > 0  # bytes per second
        
        efficiency = stats.get_analysis_efficiency()
        assert efficiency > 0  # items per second
    
    def test_complexity_metrics(self):
        """Test code complexity indicators."""
        stats = AnalysisStatistics(
            total_functions=200,
            total_imports=50,
            total_strings=1000,
            exported_functions=10,
            internal_functions=190
        )
        
        complexity_score = stats.calculate_complexity_score()
        assert 0 <= complexity_score <= 10
        
        import_ratio = stats.get_import_to_function_ratio()
        assert import_ratio == 0.25  # 50/200
    
    def test_quality_indicators(self):
        """Test analysis quality indicators."""
        stats = AnalysisStatistics(
            total_functions=100,
            confidence_score=0.95,
            analysis_depth="comprehensive",
            coverage_percentage=92.0
        )
        
        quality_score = stats.get_quality_score()
        assert 0 <= quality_score <= 1
        assert quality_score > 0.9  # High confidence and coverage


class TestAnalysisError:
    """Test cases for AnalysisError model."""
    
    def test_basic_instantiation(self):
        """Test basic error creation."""
        error = AnalysisError(
            error_type="timeout",
            message="Analysis timed out after 300 seconds",
            component="radare2_engine"
        )
        
        assert error.error_type == "timeout"
        assert error.message == "Analysis timed out after 300 seconds"
        assert error.component == "radare2_engine"
        assert error.details is None
        assert error.is_recoverable is False
    
    def test_with_details(self):
        """Test error with additional details."""
        error = AnalysisError(
            error_type="format_error",
            message="Unsupported file format",
            component="file_parser",
            details={"detected_format": "unknown", "file_size": 1024},
            is_recoverable=True
        )
        
        assert error.details["detected_format"] == "unknown"
        assert error.is_recoverable is True
    
    def test_severity_classification(self):
        """Test error severity classification."""
        # Critical error
        critical_error = AnalysisError(
            error_type="system_crash",
            message="System crashed",
            component="core"
        )
        assert critical_error.get_severity() == "critical"
        
        # Warning level error
        warning_error = AnalysisError(
            error_type="partial_analysis",
            message="Some functions could not be analyzed",
            component="function_analyzer",
            is_recoverable=True
        )
        assert warning_error.get_severity() in ["warning", "minor"]
    
    def test_error_categorization(self):
        """Test error categorization."""
        timeout_error = AnalysisError(
            error_type="timeout",
            message="Timeout occurred",
            component="engine"
        )
        assert timeout_error.get_category() == "performance"
        
        format_error = AnalysisError(
            error_type="format_error",
            message="Invalid format",
            component="parser"
        )
        assert format_error.get_category() == "input_validation"


class TestAnalysisResult:
    """Test cases for AnalysisResult model."""
    
    def test_basic_instantiation(self):
        """Test basic result creation."""
        result = AnalysisResult(
            analysis_id=uuid4(),
            file_hash="a" * 64,
            file_format=FileFormat.PE,
            platform=Platform.WINDOWS,
            success=True
        )
        
        assert isinstance(result.analysis_id, UUID)
        assert result.file_hash == "a" * 64
        assert result.file_format == FileFormat.PE
        assert result.platform == Platform.WINDOWS
        assert result.success is True
        assert isinstance(result.timestamp, datetime)
    
    def test_with_complete_analysis(self):
        """Test result with complete analysis data."""
        functions = [
            FunctionInfo(name="main", address="0x401000", size=256),
            FunctionInfo(name="helper", address="0x401100", size=128)
        ]
        
        imports = [
            ImportInfo(library="kernel32.dll", function="CreateFileA", address="0x405000"),
            ImportInfo(library="user32.dll", function="MessageBoxA", address="0x405010")
        ]
        
        strings = [
            StringExtraction(content="Hello World", address="0x403000", encoding="ascii"),
            StringExtraction(content="Error message", address="0x403010", encoding="ascii")
        ]
        
        security_findings = SecurityFindings(
            risk_score=5.5,
            network_behaviors=["HTTP requests"],
            file_operations=["File creation"]
        )
        
        statistics = AnalysisStatistics(
            total_functions=2,
            total_imports=2,
            total_strings=2,
            analysis_duration_seconds=45.0,
            confidence_score=0.88
        )
        
        result = AnalysisResult(
            analysis_id=uuid4(),
            file_hash="a" * 64,
            file_format=FileFormat.PE,
            platform=Platform.WINDOWS,
            success=True,
            functions=functions,
            imports=imports,
            strings=strings,
            security_findings=security_findings,
            statistics=statistics
        )
        
        assert len(result.functions) == 2
        assert len(result.imports) == 2
        assert len(result.strings) == 2
        assert result.security_findings.risk_score == 5.5
        assert result.statistics.confidence_score == 0.88
    
    def test_failed_analysis(self):
        """Test failed analysis result."""
        errors = [
            AnalysisError(
                error_type="timeout",
                message="Analysis timed out",
                component="engine"
            ),
            AnalysisError(
                error_type="format_error", 
                message="Unsupported format",
                component="parser"
            )
        ]
        
        result = AnalysisResult(
            analysis_id=uuid4(),
            file_hash="b" * 64,
            file_format=FileFormat.UNKNOWN,
            platform=Platform.UNKNOWN,
            success=False,
            errors=errors
        )
        
        assert result.success is False
        assert len(result.errors) == 2
        assert result.has_errors()
        assert not result.is_complete_analysis()
    
    def test_summary_generation(self):
        """Test analysis result summary."""
        functions = [FunctionInfo(name="main", address="0x401000", size=256)]
        imports = [ImportInfo(library="kernel32.dll", function="CreateFileA", address="0x405000")]
        
        result = AnalysisResult(
            analysis_id=uuid4(),
            file_hash="a" * 64,
            file_format=FileFormat.PE,
            platform=Platform.WINDOWS,
            success=True,
            functions=functions,
            imports=imports
        )
        
        summary = result.get_summary()
        assert isinstance(summary, dict)
        assert summary["success"] is True
        assert summary["function_count"] == 1
        assert summary["import_count"] == 1
        assert summary["file_format"] == "pe"
        assert summary["platform"] == "windows"
    
    def test_detailed_breakdown(self):
        """Test detailed analysis breakdown."""
        result = AnalysisResult(
            analysis_id=uuid4(),
            file_hash="a" * 64,
            file_format=FileFormat.PE,
            platform=Platform.WINDOWS,
            success=True
        )
        
        breakdown = result.get_detailed_breakdown()
        assert isinstance(breakdown, dict)
        assert "functions" in breakdown
        assert "imports" in breakdown
        assert "strings" in breakdown
        assert "security_findings" in breakdown
        assert "statistics" in breakdown
    
    def test_serialization(self):
        """Test result serialization."""
        result = AnalysisResult(
            analysis_id=uuid4(),
            file_hash="a" * 64,
            file_format=FileFormat.PE,
            platform=Platform.WINDOWS,
            success=True
        )
        
        serialized = result.to_dict()
        assert serialized["file_hash"] == "a" * 64
        assert serialized["file_format"] == "pe"
        assert serialized["success"] is True
        
        # Test JSON serialization
        json_str = result.to_json()
        assert isinstance(json_str, str)
        assert "analysis_id" in json_str
    
    def test_comparison_and_validation(self):
        """Test result comparison and validation."""
        result1 = AnalysisResult(
            analysis_id=uuid4(),
            file_hash="a" * 64,
            file_format=FileFormat.PE,
            platform=Platform.WINDOWS,
            success=True
        )
        
        result2 = AnalysisResult(
            analysis_id=uuid4(),
            file_hash="b" * 64,
            file_format=FileFormat.ELF,
            platform=Platform.LINUX,
            success=True
        )
        
        # Different results should not be equal
        assert result1 != result2
        
        # Validate result structure
        assert result1.validate_structure()
        assert result2.validate_structure()