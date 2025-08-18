"""
Unit tests for shared enumeration types.

Tests the enumeration classes including validation, methods, and utility functions.
"""

import pytest

from src.models.shared.enums import (
    JobStatus, AnalysisDepth, FileFormat, Platform, AnalysisFocus,
    validate_job_transition, get_file_format_from_extension
)


class TestJobStatus:
    """Test cases for JobStatus enum."""
    
    def test_enum_values(self):
        """Test that all expected enum values exist."""
        expected_values = ['pending', 'processing', 'completed', 'failed', 'cancelled']
        actual_values = [status.value for status in JobStatus]
        assert set(actual_values) == set(expected_values)
    
    def test_terminal_states(self):
        """Test terminal state identification."""
        terminal_states = JobStatus.terminal_states()
        assert JobStatus.COMPLETED in terminal_states
        assert JobStatus.FAILED in terminal_states
        assert JobStatus.CANCELLED in terminal_states
        assert JobStatus.PENDING not in terminal_states
        assert JobStatus.PROCESSING not in terminal_states
    
    def test_active_states(self):
        """Test active state identification."""
        active_states = JobStatus.active_states()
        assert JobStatus.PENDING in active_states
        assert JobStatus.PROCESSING in active_states
        assert JobStatus.COMPLETED not in active_states
    
    def test_state_methods(self):
        """Test individual state check methods."""
        assert JobStatus.PENDING.is_active()
        assert not JobStatus.PENDING.is_terminal()
        
        assert JobStatus.COMPLETED.is_terminal()
        assert not JobStatus.COMPLETED.is_active()


class TestAnalysisDepth:
    """Test cases for AnalysisDepth enum."""
    
    def test_enum_values(self):
        """Test that all expected enum values exist."""
        expected_values = ['quick', 'standard', 'comprehensive']
        actual_values = [depth.value for depth in AnalysisDepth]
        assert set(actual_values) == set(expected_values)
    
    def test_timeout_mapping(self):
        """Test timeout value retrieval."""
        assert AnalysisDepth.QUICK.get_timeout() == 30
        assert AnalysisDepth.STANDARD.get_timeout() == 300
        assert AnalysisDepth.COMPREHENSIVE.get_timeout() == 1200
    
    def test_descriptions(self):
        """Test description property."""
        for depth in AnalysisDepth:
            description = depth.description
            assert isinstance(description, str)
            assert len(description) > 0


class TestFileFormat:
    """Test cases for FileFormat enum."""
    
    def test_enum_values(self):
        """Test that all expected enum values exist."""
        expected_values = ['pe', 'elf', 'macho', 'apk', 'ipa', 'java', 'wasm', 'raw', 'unknown']
        actual_values = [fmt.value for fmt in FileFormat]
        assert set(actual_values) == set(expected_values)
    
    def test_supported_formats(self):
        """Test supported format identification."""
        supported = FileFormat.get_supported_formats()
        assert FileFormat.PE in supported
        assert FileFormat.ELF in supported
        assert FileFormat.MACHO in supported
        assert FileFormat.APK not in supported
    
    def test_experimental_formats(self):
        """Test experimental format identification."""
        experimental = FileFormat.get_experimental_formats()
        assert FileFormat.APK in experimental
        assert FileFormat.IPA in experimental
        assert FileFormat.PE not in experimental
    
    def test_support_methods(self):
        """Test individual support check methods."""
        assert FileFormat.PE.is_supported()
        assert not FileFormat.PE.is_experimental()
        
        assert FileFormat.APK.is_experimental()
        assert not FileFormat.APK.is_supported()


class TestPlatform:
    """Test cases for Platform enum."""
    
    def test_enum_values(self):
        """Test that all expected enum values exist."""
        expected_values = ['windows', 'linux', 'macos', 'android', 'ios', 'unknown']
        actual_values = [platform.value for platform in Platform]
        assert set(actual_values) == set(expected_values)
    
    def test_platform_categories(self):
        """Test platform categorization."""
        desktop_platforms = Platform.get_desktop_platforms()
        mobile_platforms = Platform.get_mobile_platforms()
        
        assert Platform.WINDOWS in desktop_platforms
        assert Platform.LINUX in desktop_platforms
        assert Platform.MACOS in desktop_platforms
        
        assert Platform.ANDROID in mobile_platforms
        assert Platform.IOS in mobile_platforms
    
    def test_platform_methods(self):
        """Test individual platform check methods."""
        assert Platform.WINDOWS.is_desktop()
        assert not Platform.WINDOWS.is_mobile()
        
        assert Platform.ANDROID.is_mobile()
        assert not Platform.ANDROID.is_desktop()
    
    def test_from_file_format(self):
        """Test platform inference from file format."""
        assert Platform.from_file_format(FileFormat.PE) == Platform.WINDOWS
        assert Platform.from_file_format(FileFormat.ELF) == Platform.LINUX
        assert Platform.from_file_format(FileFormat.MACHO) == Platform.MACOS


class TestAnalysisFocus:
    """Test cases for AnalysisFocus enum."""
    
    def test_enum_values(self):
        """Test that all expected enum values exist."""
        expected_values = ['security', 'functions', 'strings', 'imports', 'metadata', 'all']
        actual_values = [focus.value for focus in AnalysisFocus]
        assert set(actual_values) == set(expected_values)
    
    def test_default_focus_areas(self):
        """Test default focus area selection."""
        defaults = AnalysisFocus.get_default_focus_areas()
        assert AnalysisFocus.SECURITY in defaults
        assert AnalysisFocus.FUNCTIONS in defaults
        assert AnalysisFocus.STRINGS in defaults


class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    def test_validate_job_transition(self):
        """Test job state transition validation."""
        # Valid transitions
        assert validate_job_transition(JobStatus.PENDING, JobStatus.PROCESSING)
        assert validate_job_transition(JobStatus.PROCESSING, JobStatus.COMPLETED)
        
        # Invalid transitions
        assert not validate_job_transition(JobStatus.COMPLETED, JobStatus.PROCESSING)
        assert not validate_job_transition(JobStatus.FAILED, JobStatus.PENDING)
    
    def test_get_file_format_from_extension(self):
        """Test file format detection from filename."""
        assert get_file_format_from_extension('test.exe') == FileFormat.PE
        assert get_file_format_from_extension('test.dll') == FileFormat.PE
        assert get_file_format_from_extension('test.so') == FileFormat.ELF
        assert get_file_format_from_extension('test.dylib') == FileFormat.MACHO
        assert get_file_format_from_extension('test.apk') == FileFormat.APK
        assert get_file_format_from_extension('test.ipa') == FileFormat.IPA
        assert get_file_format_from_extension('test.unknown') == FileFormat.UNKNOWN