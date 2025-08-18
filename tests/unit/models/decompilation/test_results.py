"""
Unit tests for decompilation result models.

Tests the new decompilation-focused Pydantic models including LLM translation results,
validation logic, computed fields, and business logic methods.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
import uuid

from src.models.decompilation.results import (
    DecompilationDepth,
    TranslationDetail,
    LLMProviderMetadata,
    FunctionTranslation,
    ImportTranslation,
    StringTranslation,
    OverallSummary,
    DecompilationResult
)
from src.models.shared.enums import FileFormat, Platform


class TestEnums:
    """Test enumeration classes."""
    
    def test_decompilation_depth_values(self):
        """Test DecompilationDepth enum values."""
        assert DecompilationDepth.BASIC == "basic"
        assert DecompilationDepth.STANDARD == "standard"
        assert DecompilationDepth.COMPREHENSIVE == "comprehensive"
        
        # Test enum membership
        assert "basic" in DecompilationDepth
        assert "invalid" not in DecompilationDepth
    
    def test_translation_detail_values(self):
        """Test TranslationDetail enum values."""
        assert TranslationDetail.BRIEF == "brief"
        assert TranslationDetail.STANDARD == "standard"
        assert TranslationDetail.COMPREHENSIVE == "comprehensive"


class TestLLMProviderMetadata:
    """Test LLMProviderMetadata model."""
    
    @pytest.fixture
    def valid_llm_metadata(self):
        """Create valid LLM provider metadata."""
        return {
            "provider": "openai",
            "model": "gpt-4",
            "tokens_used": 450,
            "processing_time_ms": 1200,
            "api_version": "2023-12-01",
            "temperature": 0.1,
            "max_tokens": 2048,
            "cost_estimate_usd": 0.0125
        }
    
    def test_llm_metadata_creation(self, valid_llm_metadata):
        """Test creating valid LLM metadata."""
        metadata = LLMProviderMetadata(**valid_llm_metadata)
        
        assert metadata.provider == "openai"
        assert metadata.model == "gpt-4"
        assert metadata.tokens_used == 450
        assert metadata.processing_time_ms == 1200
        assert metadata.api_version == "2023-12-01"
        assert metadata.temperature == 0.1
        assert metadata.max_tokens == 2048
        assert metadata.cost_estimate_usd == 0.0125
    
    def test_llm_metadata_minimal(self):
        """Test creating LLM metadata with minimal required fields."""
        metadata = LLMProviderMetadata(
            provider="anthropic",
            model="claude-3-sonnet",
            tokens_used=300,
            processing_time_ms=800
        )
        
        assert metadata.provider == "anthropic"
        assert metadata.model == "claude-3-sonnet"
        assert metadata.tokens_used == 300
        assert metadata.processing_time_ms == 800
        assert metadata.api_version is None
        assert metadata.custom_endpoint is None
        assert metadata.temperature is None
    
    def test_llm_metadata_validation(self):
        """Test LLM metadata validation."""
        # Test negative tokens
        with pytest.raises(ValueError):
            LLMProviderMetadata(
                provider="openai",
                model="gpt-4",
                tokens_used=-10,
                processing_time_ms=1000
            )
        
        # Test negative processing time
        with pytest.raises(ValueError):
            LLMProviderMetadata(
                provider="openai",
                model="gpt-4",
                tokens_used=100,
                processing_time_ms=-500
            )
        
        # Test invalid temperature
        with pytest.raises(ValueError):
            LLMProviderMetadata(
                provider="openai",
                model="gpt-4",
                tokens_used=100,
                processing_time_ms=1000,
                temperature=3.0  # Too high
            )


class TestFunctionTranslation:
    """Test FunctionTranslation model."""
    
    @pytest.fixture
    def valid_llm_metadata(self):
        """LLM metadata for testing."""
        return LLMProviderMetadata(
            provider="openai",
            model="gpt-4",
            tokens_used=350,
            processing_time_ms=1100
        )
    
    @pytest.fixture
    def valid_function_translation(self, valid_llm_metadata):
        """Create valid function translation."""
        return {
            "function_name": "authenticate_user",
            "address": "0x401000",
            "size": 256,
            "assembly_code": "push rbp\nmov rbp, rsp\ncall verify_password\npop rbp\nret",
            "natural_language_description": "This function validates user credentials using bcrypt hashing and implements secure password verification with proper timing attack protection.",
            "parameters_explanation": "Takes username (string) and password_hash (string) parameters passed via registers.",
            "return_value_explanation": "Returns boolean in EAX indicating authentication success (1) or failure (0).",
            "security_analysis": "Implements secure password hashing with timing attack protection and proper error handling.",
            "confidence_score": 0.92,
            "llm_provider": valid_llm_metadata,
            "context_used": {"imports": ["bcrypt"], "strings": ["Invalid credentials"]}
        }
    
    def test_function_translation_creation(self, valid_function_translation):
        """Test creating valid function translation."""
        func = FunctionTranslation(**valid_function_translation)
        
        assert func.function_name == "authenticate_user"
        assert func.address == "0x401000"
        assert func.size == 256
        assert func.confidence_score == 0.92
        assert func.llm_provider.provider == "openai"
        assert "bcrypt" in func.context_used["imports"]
    
    def test_function_address_validation(self, valid_function_translation):
        """Test address validation and formatting."""
        # Test address without 0x prefix
        valid_function_translation["address"] = "401000"
        func = FunctionTranslation(**valid_function_translation)
        assert func.address == "0x401000"
        
        # Test address with uppercase
        valid_function_translation["address"] = "0x401ABC"
        func = FunctionTranslation(**valid_function_translation)
        assert func.address == "0x401abc"
        
        # Test invalid address
        valid_function_translation["address"] = "invalid"
        with pytest.raises(ValueError, match="Invalid hexadecimal address"):
            FunctionTranslation(**valid_function_translation)
        
        # Test empty address
        valid_function_translation["address"] = ""
        with pytest.raises(ValueError, match="Address cannot be empty"):
            FunctionTranslation(**valid_function_translation)
    
    def test_function_computed_fields(self, valid_function_translation):
        """Test computed field properties."""
        # Test high confidence
        func = FunctionTranslation(**valid_function_translation)
        assert func.is_high_confidence is True  # 0.92 >= 0.8
        
        # Test low confidence
        valid_function_translation["confidence_score"] = 0.5
        func = FunctionTranslation(**valid_function_translation)
        assert func.is_high_confidence is False
        
        # Test security implications
        valid_function_translation["security_analysis"] = "Some security analysis"
        func = FunctionTranslation(**valid_function_translation)
        assert func.has_security_implications is True
        
        # Test no security implications
        valid_function_translation["security_analysis"] = None
        func = FunctionTranslation(**valid_function_translation)
        assert func.has_security_implications is False
    
    def test_function_translation_summary(self, valid_function_translation):
        """Test translation summary computed field."""
        func = FunctionTranslation(**valid_function_translation)
        summary = func.translation_summary
        
        assert summary["function_name"] == "authenticate_user"
        assert summary["address"] == "0x401000"
        assert summary["size"] == 256
        assert summary["confidence_score"] == 0.92
        assert summary["is_high_confidence"] is True
        assert summary["has_security_implications"] is True
        assert summary["llm_provider"] == "openai"
        assert summary["llm_model"] == "gpt-4"
        assert summary["tokens_used"] == 350
        assert summary["has_parameters"] is True
        assert summary["has_return_info"] is True


class TestImportTranslation:
    """Test ImportTranslation model."""
    
    @pytest.fixture
    def valid_import_translation(self):
        """Create valid import translation."""
        return {
            "library_name": "kernel32.dll",
            "function_name": "CreateFileA",
            "api_documentation_summary": "Creates or opens a file for I/O operations with specified access rights and sharing modes.",
            "usage_context": "Used for file creation and access in Windows applications, commonly for reading configuration files or creating temporary files.",
            "parameters_description": "lpFileName: path to file, dwDesiredAccess: access rights, dwShareMode: sharing permissions, lpSecurityAttributes: security descriptor, dwCreationDisposition: action if file exists, dwFlagsAndAttributes: file attributes, hTemplateFile: template file handle",
            "security_implications": "Requires path validation to prevent directory traversal attacks and proper access control validation.",
            "alternative_apis": ["CreateFileW", "OpenFile", "_open"],
            "common_misuses": ["Insufficient path validation", "Overly permissive access rights"],
            "detection_signatures": ["CreateFileA with suspicious paths", "CreateFileA with WRITE access to system directories"],
            "confidence_score": 0.95,
            "llm_provider": LLMProviderMetadata(
                provider="gemini",
                model="gemini-pro",
                tokens_used=280,
                processing_time_ms=950
            ),
            "cross_references": ["authenticate_user", "load_config"]
        }
    
    def test_import_translation_creation(self, valid_import_translation):
        """Test creating valid import translation."""
        imp = ImportTranslation(**valid_import_translation)
        
        assert imp.library_name == "kernel32.dll"
        assert imp.function_name == "CreateFileA"
        assert imp.confidence_score == 0.95
        assert len(imp.alternative_apis) == 3
        assert len(imp.common_misuses) == 2
        assert "authenticate_user" in imp.cross_references
    
    def test_import_full_api_name(self, valid_import_translation):
        """Test full API name computed field."""
        imp = ImportTranslation(**valid_import_translation)
        assert imp.full_api_name == "kernel32.dll!CreateFileA"
    
    def test_import_risk_assessment(self, valid_import_translation):
        """Test risk assessment computed field."""
        # Test high risk
        valid_import_translation["security_implications"] = "Critical vulnerability risk with potential for privilege escalation"
        imp = ImportTranslation(**valid_import_translation)
        assert imp.is_high_risk is True
        
        # Test low risk
        valid_import_translation["security_implications"] = "Standard API with no special security considerations"
        imp = ImportTranslation(**valid_import_translation)
        assert imp.is_high_risk is False
        
        # Test no security analysis
        valid_import_translation["security_implications"] = None
        imp = ImportTranslation(**valid_import_translation)
        assert imp.is_high_risk is False
    
    def test_import_list_validation(self, valid_import_translation):
        """Test string list validation and deduplication."""
        # Test with duplicates and empty strings
        valid_import_translation["alternative_apis"] = ["CreateFileW", "", "CreateFileW", "OpenFile", "  ", "OpenFile"]
        imp = ImportTranslation(**valid_import_translation)
        
        # Should remove duplicates and empty strings
        assert len(imp.alternative_apis) == 2
        assert "CreateFileW" in imp.alternative_apis
        assert "OpenFile" in imp.alternative_apis
        assert "" not in imp.alternative_apis


class TestStringTranslation:
    """Test StringTranslation model."""
    
    @pytest.fixture
    def valid_string_translation(self):
        """Create valid string translation."""
        return {
            "string_value": "SELECT * FROM users WHERE id = ?",
            "address": "0x403000",
            "size": 33,
            "encoding": "ascii",
            "usage_context": "Database query for user lookup in authentication system",
            "interpretation": "Parameterized SQL query using prepared statements to prevent SQL injection attacks. Retrieves user record by ID.",
            "security_analysis": "Properly parameterized query prevents SQL injection. Uses placeholder (?) for safe parameter binding.",
            "data_classification": "sql_query",
            "confidence_score": 0.88,
            "llm_provider": LLMProviderMetadata(
                provider="openai",
                model="gpt-4",
                tokens_used=180,
                processing_time_ms=750
            ),
            "cross_references": ["authenticate_user", "validate_user_id"],
            "related_strings": ["Invalid user ID", "Database connection failed"]
        }
    
    def test_string_translation_creation(self, valid_string_translation):
        """Test creating valid string translation."""
        string = StringTranslation(**valid_string_translation)
        
        assert string.string_value == "SELECT * FROM users WHERE id = ?"
        assert string.address == "0x403000"
        assert string.size == 33
        assert string.encoding == "ascii"
        assert string.confidence_score == 0.88
        assert len(string.cross_references) == 2
        assert len(string.related_strings) == 2
    
    def test_string_address_validation(self, valid_string_translation):
        """Test string address validation."""
        # Test address formatting
        valid_string_translation["address"] = "403000"
        string = StringTranslation(**valid_string_translation)
        assert string.address == "0x403000"
        
        # Test invalid address
        valid_string_translation["address"] = "invalid_address"
        with pytest.raises(ValueError, match="Invalid hexadecimal address"):
            StringTranslation(**valid_string_translation)
    
    def test_string_sensitivity_detection(self, valid_string_translation):
        """Test potentially sensitive string detection."""
        # Test sensitive string
        valid_string_translation["security_analysis"] = "Contains sensitive credential information that should be protected"
        string = StringTranslation(**valid_string_translation)
        assert string.is_potentially_sensitive is True
        
        # Test non-sensitive string
        valid_string_translation["security_analysis"] = "Standard configuration string with no security implications"
        string = StringTranslation(**valid_string_translation)
        assert string.is_potentially_sensitive is False
    
    def test_string_categorization(self, valid_string_translation):
        """Test automatic string categorization."""
        # Test SQL query
        string = StringTranslation(**valid_string_translation)
        assert string.string_category == "sql_query"
        
        # Test URL
        valid_string_translation["string_value"] = "https://api.example.com/users"
        string = StringTranslation(**valid_string_translation)
        assert string.string_category == "url"
        
        # Test file path
        valid_string_translation["string_value"] = "C:\\Program Files\\MyApp\\config.exe"
        string = StringTranslation(**valid_string_translation)
        assert string.string_category == "file_path"
        
        # Test registry path
        valid_string_translation["string_value"] = "HKEY_CURRENT_USER\\Software\\MyApp"
        string = StringTranslation(**valid_string_translation)
        assert string.string_category == "registry_path"
        
        # Test error message
        valid_string_translation["string_value"] = "Error: Connection failed"
        string = StringTranslation(**valid_string_translation)
        assert string.string_category == "error_message"
        
        # Test format string
        valid_string_translation["string_value"] = "Username: %s, ID: %d"
        string = StringTranslation(**valid_string_translation)
        assert string.string_category == "format_string"
        
        # Test general string
        valid_string_translation["string_value"] = "Hello World"
        string = StringTranslation(**valid_string_translation)
        assert string.string_category == "general"


class TestOverallSummary:
    """Test OverallSummary model."""
    
    @pytest.fixture
    def valid_overall_summary(self):
        """Create valid overall summary."""
        return {
            "program_purpose": "Network file transfer utility with encryption capabilities",
            "main_functionality": "Provides secure file transfer over TCP with AES encryption and user authentication",
            "architecture_overview": "Multi-threaded client-server application using Windows sockets API with modular encryption layer",
            "data_flow_description": "Input files are encrypted using AES-256, transmitted via TCP sockets, and decrypted on the receiving end",
            "security_analysis": "Implements AES-256 encryption with proper key exchange, but lacks certificate validation for SSL connections",
            "technology_stack": ["WinSock2", "OpenSSL", "AES-256", "TCP/IP", "Windows API"],
            "key_insights": [
                "Uses secure cryptographic libraries",
                "Proper error handling implemented",
                "Multi-threaded design for concurrent connections",
                "Configuration stored in encrypted registry keys"
            ],
            "potential_use_cases": [
                "Legitimate: Secure file backup and synchronization",
                "Malicious: Covert data exfiltration channel"
            ],
            "risk_assessment": "Medium risk - legitimate functionality but could be misused for data exfiltration",
            "behavioral_indicators": [
                "Creates network connections",
                "Encrypts files before transmission",
                "Modifies registry keys for configuration"
            ],
            "confidence_score": 0.87,
            "llm_provider": LLMProviderMetadata(
                provider="anthropic",
                model="claude-3-opus",
                tokens_used=850,
                processing_time_ms=2100
            )
        }
    
    def test_overall_summary_creation(self, valid_overall_summary):
        """Test creating valid overall summary."""
        summary = OverallSummary(**valid_overall_summary)
        
        assert summary.program_purpose == "Network file transfer utility with encryption capabilities"
        assert summary.confidence_score == 0.87
        assert len(summary.technology_stack) == 5
        assert len(summary.key_insights) == 4
        assert len(summary.potential_use_cases) == 2
        assert "WinSock2" in summary.technology_stack
    
    def test_summary_malicious_detection(self, valid_overall_summary):
        """Test malicious software detection."""
        # Test legitimate software
        summary = OverallSummary(**valid_overall_summary)
        assert summary.is_likely_malicious is False
        
        # Test malicious indicators
        valid_overall_summary["risk_assessment"] = "High risk - exhibits malware characteristics including keylogger functionality"
        summary = OverallSummary(**valid_overall_summary)
        assert summary.is_likely_malicious is True
        
        # Test no risk assessment
        valid_overall_summary["risk_assessment"] = None
        summary = OverallSummary(**valid_overall_summary)
        assert summary.is_likely_malicious is False
    
    def test_summary_complexity_assessment(self, valid_overall_summary):
        """Test complexity level assessment."""
        # Test high complexity
        summary = OverallSummary(**valid_overall_summary)
        assert summary.complexity_level == "medium"  # 4 insights, 5 tech stack items
        
        # Test low complexity
        valid_overall_summary["key_insights"] = ["Simple program"]
        valid_overall_summary["technology_stack"] = ["Basic API"]
        summary = OverallSummary(**valid_overall_summary)
        assert summary.complexity_level == "low"
        
        # Test high complexity
        valid_overall_summary["key_insights"] = ["insight" + str(i) for i in range(12)]
        summary = OverallSummary(**valid_overall_summary)
        assert summary.complexity_level == "high"


class TestDecompilationResult:
    """Test DecompilationResult model."""
    
    @pytest.fixture
    def valid_decompilation_result(self):
        """Create valid decompilation result."""
        return {
            "decompilation_id": str(uuid.uuid4()),
            "file_hash": "sha256:abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "file_size": 245760,
            "file_format": FileFormat.PE,
            "platform": Platform.WINDOWS,
            "architecture": "x64",
            "success": True,
            "decompilation_duration_seconds": 12.5,
            "translation_duration_seconds": 45.8,
            "functions": [],
            "imports": [],
            "strings": [],
            "llm_providers_used": ["openai", "anthropic"],
            "decompilation_config": {"analysis_level": "aa", "timeout": 300},
            "translation_config": {"detail_level": "standard", "providers": ["openai"]},
            "errors": [],
            "warnings": ["Large file size may impact performance"],
            "partial_results": False
        }
    
    def test_decompilation_result_creation(self, valid_decompilation_result):
        """Test creating valid decompilation result."""
        result = DecompilationResult(**valid_decompilation_result)
        
        assert result.success is True
        assert result.file_size == 245760
        assert result.file_format == FileFormat.PE
        assert result.platform == Platform.WINDOWS
        assert result.architecture == "x64"
        assert result.decompilation_duration_seconds == 12.5
        assert result.translation_duration_seconds == 45.8
        assert len(result.llm_providers_used) == 2
        assert len(result.warnings) == 1
        assert result.partial_results is False
    
    def test_file_hash_validation(self, valid_decompilation_result):
        """Test file hash validation."""
        # Test valid hash with algorithm prefix
        result = DecompilationResult(**valid_decompilation_result)
        assert result.file_hash.startswith("sha256:")
        
        # Test hash without algorithm prefix
        valid_decompilation_result["file_hash"] = "abcdef1234567890"
        with pytest.raises(ValueError, match="must include algorithm prefix"):
            DecompilationResult(**valid_decompilation_result)
        
        # Test invalid algorithm
        valid_decompilation_result["file_hash"] = "invalid:abcdef1234567890"
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            DecompilationResult(**valid_decompilation_result)
        
        # Test invalid hash characters
        valid_decompilation_result["file_hash"] = "sha256:xyz123"
        with pytest.raises(ValueError, match="invalid characters"):
            DecompilationResult(**valid_decompilation_result)
    
    def test_computed_fields(self, valid_decompilation_result):
        """Test computed field calculations."""
        result = DecompilationResult(**valid_decompilation_result)
        
        # Test total duration
        assert result.total_duration_seconds == 58.3  # 12.5 + 45.8
        
        # Test token calculation (empty lists)
        assert result.total_llm_tokens_used == 0
        
        # Test cost calculation (empty lists)
        assert result.estimated_total_cost_usd == 0.0
    
    def test_decompilation_summary(self, valid_decompilation_result):
        """Test decompilation summary computed field."""
        result = DecompilationResult(**valid_decompilation_result)
        summary = result.decompilation_summary
        
        assert "file_info" in summary
        assert "processing_stats" in summary
        assert "llm_stats" in summary
        assert summary["file_info"]["format"] == FileFormat.PE
        assert summary["processing_stats"]["success"] is True
        assert summary["processing_stats"]["function_count"] == 0
        assert summary["llm_stats"]["providers_used"] == ["openai", "anthropic"]
    
    def test_with_translations(self, valid_decompilation_result):
        """Test decompilation result with actual translation data."""
        # Add some translation data
        llm_metadata = LLMProviderMetadata(
            provider="openai",
            model="gpt-4",
            tokens_used=300,
            processing_time_ms=1000,
            cost_estimate_usd=0.006
        )
        
        function_translation = FunctionTranslation(
            function_name="main",
            address="0x401000",
            size=128,
            natural_language_description="Main entry point function",
            confidence_score=0.9,
            llm_provider=llm_metadata
        )
        
        valid_decompilation_result["functions"] = [function_translation]
        result = DecompilationResult(**valid_decompilation_result)
        
        # Test token counting
        assert result.total_llm_tokens_used == 300
        
        # Test cost calculation
        assert result.estimated_total_cost_usd == 0.006
        
        # Test high confidence translations
        high_conf = result.high_confidence_translations
        assert len(high_conf["functions"]) == 1
        assert high_conf["functions"][0].function_name == "main"
    
    def test_error_and_warning_management(self, valid_decompilation_result):
        """Test error and warning management methods."""
        result = DecompilationResult(**valid_decompilation_result)
        
        # Test adding errors
        result.add_error("Test error message")
        assert "Test error message" in result.errors
        assert result.partial_results is True
        
        # Test duplicate error prevention
        result.add_error("Test error message")
        assert result.errors.count("Test error message") == 1
        
        # Test adding warnings
        result.add_warning("Test warning message")
        assert "Test warning message" in result.warnings
        
        # Test duplicate warning prevention
        result.add_warning("Test warning message")
        assert result.warnings.count("Test warning message") == 1
    
    def test_decompilation_completion_check(self, valid_decompilation_result):
        """Test decompilation completion check."""
        # Test incomplete (no content)
        result = DecompilationResult(**valid_decompilation_result)
        assert result.is_decompilation_complete() is False  # No functions/imports/strings
        
        # Test complete with content
        function_translation = FunctionTranslation(
            function_name="main",
            address="0x401000",
            size=128,
            natural_language_description="Main function",
            confidence_score=0.9,
            llm_provider=LLMProviderMetadata(
                provider="openai",
                model="gpt-4",
                tokens_used=100,
                processing_time_ms=500
            )
        )
        valid_decompilation_result["functions"] = [function_translation]
        result = DecompilationResult(**valid_decompilation_result)
        assert result.is_decompilation_complete() is True
        
        # Test incomplete with errors
        result.add_error("Some error")
        assert result.is_decompilation_complete() is False
    
    def test_provider_usage_stats(self, valid_decompilation_result):
        """Test provider usage statistics."""
        # Add translations with different providers
        openai_metadata = LLMProviderMetadata(
            provider="openai",
            model="gpt-4",
            tokens_used=200,
            processing_time_ms=800,
            cost_estimate_usd=0.004
        )
        
        anthropic_metadata = LLMProviderMetadata(
            provider="anthropic",
            model="claude-3-sonnet",
            tokens_used=150,
            processing_time_ms=600,
            cost_estimate_usd=0.003
        )
        
        function_translation = FunctionTranslation(
            function_name="main",
            address="0x401000",
            size=128,
            natural_language_description="Main function",
            confidence_score=0.9,
            llm_provider=openai_metadata
        )
        
        import_translation = ImportTranslation(
            library_name="kernel32.dll",
            function_name="CreateFileA",
            api_documentation_summary="Creates files",
            usage_context="File operations",
            confidence_score=0.85,
            llm_provider=anthropic_metadata
        )
        
        valid_decompilation_result["functions"] = [function_translation]
        valid_decompilation_result["imports"] = [import_translation]
        result = DecompilationResult(**valid_decompilation_result)
        
        stats = result.get_provider_usage_stats()
        
        assert "openai" in stats
        assert "anthropic" in stats
        assert stats["openai"]["translation_count"] == 1
        assert stats["openai"]["total_tokens"] == 200
        assert stats["openai"]["total_cost_usd"] == 0.004
        assert stats["anthropic"]["translation_count"] == 1
        assert stats["anthropic"]["total_tokens"] == 150
        assert "function" in stats["openai"]["translation_types"]
        assert "import" in stats["anthropic"]["translation_types"]