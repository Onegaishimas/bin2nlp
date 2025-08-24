"""
Configuration validation and environment variable handling utilities.

Provides advanced validation, environment variable management, and 
configuration health checks for the bin2nlp analysis system.
"""

import os
import socket
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from urllib.parse import urlparse
import subprocess
import shutil

from .config import Settings, get_settings
from .exceptions import ConfigurationException, ValidationException


class ConfigurationValidator:
    """Advanced configuration validation with system checks."""
    
    def __init__(self):
        """Initialize configuration validator."""
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []
    
    def validate_all_settings(self, settings: Optional[Settings] = None) -> Dict[str, Any]:
        """
        Perform comprehensive validation of all configuration settings.
        
        Args:
            settings: Settings instance to validate (uses default if None)
            
        Returns:
            Dictionary with validation results and recommendations
            
        Raises:
            ConfigurationException: If critical validation errors are found
        """
        if settings is None:
            settings = get_settings()
        
        self.validation_errors.clear()
        self.validation_warnings.clear()
        
        # Validate different configuration sections
        self._validate_analysis_config(settings.analysis)
        self._validate_api_config(settings.api)
        self._validate_security_config(settings.security)
        self._validate_cache_config(settings.cache)
        self._validate_logging_config(settings.logging)
        self._validate_environment_consistency(settings)
        
        # Perform system-level checks
        self._validate_system_requirements()
        self._validate_network_connectivity(settings)
        self._validate_file_permissions(settings)
        
        # Generate validation report
        validation_report = {
            "is_valid": len(self.validation_errors) == 0,
            "errors": self.validation_errors.copy(),
            "warnings": self.validation_warnings.copy(),
            "recommendations": self._generate_recommendations(settings),
            "system_info": self._get_system_info(),
            "environment": settings.environment,
            "validation_timestamp": settings.to_config_dict().get("timestamp", "unknown")
        }
        
        # Raise exception if critical errors found
        if self.validation_errors:
            raise ConfigurationException(
                f"Configuration validation failed with {len(self.validation_errors)} errors",
                config_section="validation",
                details={
                    "errors": self.validation_errors,
                    "warnings": self.validation_warnings
                }
            )
        
        return validation_report
    
    
    def _validate_analysis_config(self, analysis_config) -> None:
        """Validate binary analysis configuration."""
        # Check file size limits
        if analysis_config.max_file_size_mb < 1:
            self.validation_errors.append("max_file_size_mb must be at least 1MB")
        elif analysis_config.max_file_size_mb > 1000:
            self.validation_warnings.append("max_file_size_mb is very large, may cause memory issues")
        
        # Check timeout settings
        if analysis_config.default_timeout_seconds < 30:
            self.validation_warnings.append("default_timeout_seconds is very low")
        
        if analysis_config.max_timeout_seconds <= analysis_config.default_timeout_seconds:
            self.validation_errors.append("max_timeout_seconds must be greater than default_timeout_seconds")
        
        # Check analysis limits
        if analysis_config.max_functions_per_analysis < 100:
            self.validation_warnings.append("max_functions_per_analysis is very low")
        elif analysis_config.max_functions_per_analysis > 100000:
            self.validation_warnings.append("max_functions_per_analysis is very high, may cause performance issues")
        
        if analysis_config.max_strings_per_analysis < 1000:
            self.validation_warnings.append("max_strings_per_analysis is very low")
        elif analysis_config.max_strings_per_analysis > 500000:
            self.validation_warnings.append("max_strings_per_analysis is very high, may cause memory issues")
        
        # Check worker memory limit
        if analysis_config.worker_memory_limit_mb < 512:
            self.validation_warnings.append("worker_memory_limit_mb is low for binary analysis")
        elif analysis_config.worker_memory_limit_mb > 8192:
            self.validation_warnings.append("worker_memory_limit_mb is very high")
        
        # Validate temp directory
        try:
            temp_dir = Path(analysis_config.temp_directory)
            if not temp_dir.exists():
                self.validation_warnings.append(f"Temp directory does not exist: {temp_dir}")
            elif not temp_dir.is_dir():
                self.validation_errors.append(f"Temp directory path is not a directory: {temp_dir}")
            elif not os.access(temp_dir, os.W_OK):
                self.validation_errors.append(f"Temp directory is not writable: {temp_dir}")
        except Exception as e:
            self.validation_errors.append(f"Cannot validate temp directory: {e}")
        
        # Check radare2 availability
        try:
            result = subprocess.run(
                [analysis_config.radare2_command, "-v"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                self.validation_warnings.append(f"radare2 command failed: {analysis_config.radare2_command}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.validation_warnings.append(f"radare2 command not found or not responding: {analysis_config.radare2_command}")
        except Exception as e:
            self.validation_warnings.append(f"Cannot validate radare2: {e}")
    
    def _validate_api_config(self, api_config) -> None:
        """Validate API server configuration."""
        # Check host binding
        if api_config.host not in ["0.0.0.0", "127.0.0.1", "localhost"]:
            try:
                socket.inet_aton(api_config.host)
            except socket.error:
                self.validation_errors.append(f"Invalid API host: {api_config.host}")
        
        # Check port
        if not (1024 <= api_config.port <= 65535):
            self.validation_errors.append(f"API port {api_config.port} should be between 1024-65535")
        
        # Check if port is available
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((api_config.host, api_config.port))
            sock.close()
            if result == 0:
                self.validation_warnings.append(f"Port {api_config.port} appears to be in use")
        except Exception:
            pass  # Port check failed, but not critical
        
        # Check worker count
        if api_config.workers < 1:
            self.validation_errors.append("API workers must be at least 1")
        elif api_config.workers > 32:
            self.validation_warnings.append("High number of API workers may consume excessive resources")
        
        # Check request size
        if api_config.max_request_size < 1048576:  # 1MB
            self.validation_warnings.append("max_request_size is very low for binary files")
        elif api_config.max_request_size > 1073741824:  # 1GB
            self.validation_warnings.append("max_request_size is very high, may cause memory issues")
        
        # Check timeout
        if api_config.request_timeout < 30:
            self.validation_warnings.append("request_timeout is very low for analysis operations")
        elif api_config.request_timeout > 3600:
            self.validation_warnings.append("request_timeout is very high")
        
        # Validate CORS origins
        for origin in api_config.cors_origins:
            if origin != "*":
                try:
                    parsed = urlparse(origin)
                    if not parsed.scheme or not parsed.netloc:
                        self.validation_warnings.append(f"Invalid CORS origin format: {origin}")
                except Exception:
                    self.validation_warnings.append(f"Cannot parse CORS origin: {origin}")
    
    def _validate_security_config(self, security_config) -> None:
        """Validate security configuration."""
        # Check API key settings
        if security_config.api_key_length < 16:
            self.validation_warnings.append("api_key_length is low for security")
        elif security_config.api_key_length > 64:
            self.validation_warnings.append("api_key_length is unnecessarily high")
        
        if not security_config.api_key_prefix:
            self.validation_warnings.append("api_key_prefix should not be empty")
        
        # Check rate limits
        if security_config.default_rate_limit_per_minute < 1:
            self.validation_errors.append("default_rate_limit_per_minute must be at least 1")
        elif security_config.default_rate_limit_per_minute > 10000:
            self.validation_warnings.append("default_rate_limit_per_minute is very high")
        
        if security_config.default_rate_limit_per_day < 100:
            self.validation_warnings.append("default_rate_limit_per_day is very low")
        elif security_config.default_rate_limit_per_day > 1000000:
            self.validation_warnings.append("default_rate_limit_per_day is very high")
        
        # Validate rate limit consistency
        daily_from_minute = security_config.default_rate_limit_per_minute * 24 * 60
        if security_config.default_rate_limit_per_day > daily_from_minute:
            self.validation_warnings.append("Daily rate limit is higher than minute limit allows")
        
        # Check API key limits
        if security_config.max_api_keys_per_user < 1:
            self.validation_errors.append("max_api_keys_per_user must be at least 1")
        elif security_config.max_api_keys_per_user > 100:
            self.validation_warnings.append("max_api_keys_per_user is very high")
        
        # Check expiry settings
        if security_config.api_key_expiry_days < 1:
            self.validation_errors.append("api_key_expiry_days must be at least 1")
        elif security_config.api_key_expiry_days > 3650:
            self.validation_warnings.append("api_key_expiry_days is very long (>10 years)")
        
        # Validate trusted proxies
        for proxy in security_config.trusted_proxies:
            try:
                socket.inet_aton(proxy)
            except socket.error:
                self.validation_warnings.append(f"Invalid trusted proxy IP: {proxy}")
    
    def _validate_cache_config(self, cache_config) -> None:
        """Validate cache configuration."""
        # Check TTL settings
        if cache_config.default_ttl_seconds < 60:
            self.validation_warnings.append("default_ttl_seconds is very low")
        elif cache_config.default_ttl_seconds > 86400:
            self.validation_warnings.append("default_ttl_seconds is very high")
        
        if cache_config.analysis_result_ttl_seconds < 300:
            self.validation_warnings.append("analysis_result_ttl_seconds is very low")
        elif cache_config.analysis_result_ttl_seconds > 604800:
            self.validation_warnings.append("analysis_result_ttl_seconds is very high (>1 week)")
        
        if cache_config.job_status_ttl_seconds < 30:
            self.validation_warnings.append("job_status_ttl_seconds is very low")
        elif cache_config.job_status_ttl_seconds > 3600:
            self.validation_warnings.append("job_status_ttl_seconds is very high")
        
        # Check rate limit window
        if cache_config.rate_limit_window_seconds < 1:
            self.validation_errors.append("rate_limit_window_seconds must be at least 1")
        elif cache_config.rate_limit_window_seconds > 3600:
            self.validation_warnings.append("rate_limit_window_seconds is very high")
        
        # Check cache size
        if cache_config.max_cache_size_mb < 64:
            self.validation_warnings.append("max_cache_size_mb is very low")
        elif cache_config.max_cache_size_mb > 4096:
            self.validation_warnings.append("max_cache_size_mb is very high")
    
    def _validate_logging_config(self, logging_config) -> None:
        """Validate logging configuration."""
        # Check log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if logging_config.level not in valid_levels:
            self.validation_errors.append(f"Invalid log level: {logging_config.level}")
        
        # Check log format
        valid_formats = ["json", "text"]
        if logging_config.format not in valid_formats:
            self.validation_errors.append(f"Invalid log format: {logging_config.format}")
        
        # Validate log file path
        if logging_config.file_path:
            try:
                log_path = Path(logging_config.file_path)
                log_dir = log_path.parent
                
                if not log_dir.exists():
                    self.validation_warnings.append(f"Log directory does not exist: {log_dir}")
                elif not os.access(log_dir, os.W_OK):
                    self.validation_errors.append(f"Log directory is not writable: {log_dir}")
                    
                # Check disk space for log files
                try:
                    disk_usage = shutil.disk_usage(log_dir)
                    free_mb = disk_usage.free // (1024 * 1024)
                    max_log_size = logging_config.max_file_size_mb * logging_config.backup_count
                    
                    if free_mb < max_log_size * 2:  # Need at least 2x log size free
                        self.validation_warnings.append(f"Low disk space for logs: {free_mb}MB free")
                except Exception:
                    pass  # Disk space check failed, not critical
                    
            except Exception as e:
                self.validation_warnings.append(f"Cannot validate log file path: {e}")
        
        # Check file size limits
        if logging_config.max_file_size_mb < 1:
            self.validation_warnings.append("max_file_size_mb is very low")
        elif logging_config.max_file_size_mb > 1000:
            self.validation_warnings.append("max_file_size_mb is very high")
        
        # Check backup count
        if logging_config.backup_count < 1:
            self.validation_warnings.append("backup_count should be at least 1")
        elif logging_config.backup_count > 20:
            self.validation_warnings.append("backup_count is very high")
    
    def _validate_environment_consistency(self, settings: Settings) -> None:
        """Validate environment-specific consistency."""
        if settings.is_production:
            # Production-specific validations
            if settings.debug:
                self.validation_warnings.append("Debug mode enabled in production")
            
            if settings.logging.level == "DEBUG":
                self.validation_warnings.append("Debug logging enabled in production")
            
            if not settings.security.enforce_https:
                self.validation_warnings.append("HTTPS not enforced in production")
            
            if "*" in settings.api.cors_origins:
                self.validation_warnings.append("Wildcard CORS origins in production")
            
            if settings.api.docs_url or settings.api.redoc_url:
                self.validation_warnings.append("API documentation enabled in production")
        
        elif settings.is_development:
            # Development-specific validations
            if settings.security.enforce_https:
                self.validation_warnings.append("HTTPS enforcement may complicate development")
    
    def _validate_system_requirements(self) -> None:
        """Validate system-level requirements."""
        # Check Python version
        import sys
        if sys.version_info < (3, 11):
            self.validation_warnings.append(f"Python {sys.version} may not be fully supported")
        
        # Check available memory
        try:
            import psutil
            memory = psutil.virtual_memory()
            available_gb = memory.available // (1024 ** 3)
            
            if available_gb < 1:
                self.validation_warnings.append("Low available memory (< 1GB)")
            elif available_gb < 2:
                self.validation_warnings.append("Limited available memory (< 2GB)")
        except ImportError:
            pass  # psutil not available, skip memory check
        
        # Check disk space in temp directory
        try:
            temp_dir = Path(tempfile.gettempdir())
            disk_usage = shutil.disk_usage(temp_dir)
            free_gb = disk_usage.free // (1024 ** 3)
            
            if free_gb < 1:
                self.validation_warnings.append("Low disk space in temp directory (< 1GB)")
            elif free_gb < 5:
                self.validation_warnings.append("Limited disk space in temp directory (< 5GB)")
        except Exception:
            pass  # Disk space check failed, not critical
    
    def _validate_network_connectivity(self, settings: Settings) -> None:
        """Validate network connectivity for external dependencies."""
        # No network connectivity tests needed for file-based storage
    
    def _validate_file_permissions(self, settings: Settings) -> None:
        """Validate file system permissions."""
        # Check temp directory permissions
        temp_dir = settings.analysis.temp_directory
        
        try:
            test_file = temp_dir / ".permission_test"
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            self.validation_errors.append(f"Cannot write to temp directory {temp_dir}: {e}")
        
        # Check log directory permissions
        if settings.logging.file_path:
            try:
                log_dir = Path(settings.logging.file_path).parent
                test_file = log_dir / ".log_permission_test"
                test_file.write_text("test")
                test_file.unlink()
            except Exception as e:
                self.validation_errors.append(f"Cannot write to log directory: {e}")
    
    def _generate_recommendations(self, settings: Settings) -> List[str]:
        """Generate configuration recommendations."""
        recommendations = []
        
        # Performance recommendations
        if settings.analysis.worker_memory_limit_mb < 1024:
            recommendations.append("Consider increasing worker_memory_limit_mb to 1GB+ for better analysis performance")
        
        if settings.cache.max_cache_size_mb < 256:
            recommendations.append("Consider increasing cache size for better performance")
        
        
        # Security recommendations
        if settings.security.api_key_length < 32:
            recommendations.append("Consider increasing API key length to 32+ characters for better security")
        
        if not settings.security.trusted_proxies and settings.is_production:
            recommendations.append("Configure trusted_proxies if using load balancers or reverse proxies")
        
        # Monitoring recommendations
        if settings.logging.level == "INFO" and settings.is_development:
            recommendations.append("Consider using DEBUG log level for development")
        
        if not settings.logging.enable_correlation_id:
            recommendations.append("Enable correlation_id logging for better request tracing")
        
        return recommendations
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information for validation report."""
        import platform
        import sys
        
        system_info = {
            "platform": platform.platform(),
            "python_version": sys.version,
            "architecture": platform.architecture(),
            "processor": platform.processor(),
            "hostname": socket.gethostname(),
        }
        
        try:
            import psutil
            memory = psutil.virtual_memory()
            disk = shutil.disk_usage("/")
            
            system_info.update({
                "memory_total_gb": round(memory.total / (1024 ** 3), 2),
                "memory_available_gb": round(memory.available / (1024 ** 3), 2),
                "disk_total_gb": round(disk.total / (1024 ** 3), 2),
                "disk_free_gb": round(disk.free / (1024 ** 3), 2),
                "cpu_count": psutil.cpu_count(),
            })
        except ImportError:
            pass  # psutil not available
        
        return system_info


class EnvironmentManager:
    """Environment variable management and validation utilities."""
    
    @staticmethod
    def get_required_env_vars() -> Dict[str, str]:
        """
        Get list of required environment variables with descriptions.
        
        Returns:
            Dictionary mapping env var names to descriptions
        """
        return {
            # API
            "API_HOST": "API server bind address",
            "API_PORT": "API server port",
            
            # Analysis
            "ANALYSIS_MAX_FILE_SIZE_MB": "Maximum file size for analysis in MB",
            "ANALYSIS_TEMP_DIRECTORY": "Temporary directory for analysis files",
            
            # Security
            "SECURITY_API_KEY_PREFIX": "Prefix for generated API keys",
            "SECURITY_ENFORCE_HTTPS": "Whether to enforce HTTPS (true/false)",
            
            # Logging
            "LOG_LEVEL": "Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
            "LOG_FILE_PATH": "Path to log file (optional)",
        }
    
    @staticmethod
    def get_optional_env_vars() -> Dict[str, str]:
        """
        Get list of optional environment variables with descriptions.
        
        Returns:
            Dictionary mapping env var names to descriptions
        """
        return {
            
            # API optional
            "API_WORKERS": "Number of API worker processes",
            "API_MAX_REQUEST_SIZE": "Maximum request size in bytes",
            "API_REQUEST_TIMEOUT": "Request timeout in seconds",
            "API_CORS_ORIGINS": "Comma-separated list of allowed CORS origins",
            
            # Analysis optional
            "ANALYSIS_DEFAULT_TIMEOUT_SECONDS": "Default analysis timeout",
            "ANALYSIS_MAX_TIMEOUT_SECONDS": "Maximum analysis timeout",
            "ANALYSIS_RADARE2_COMMAND": "Path to radare2 command",
            "ANALYSIS_ENABLE_SANDBOXING": "Enable analysis sandboxing (true/false)",
            
            # Cache optional
            "CACHE_DEFAULT_TTL_SECONDS": "Default cache TTL in seconds",
            "CACHE_ANALYSIS_RESULT_TTL_SECONDS": "Analysis result cache TTL",
            "CACHE_ENABLE_COMPRESSION": "Enable cache compression (true/false)",
            
            # Security optional
            "SECURITY_API_KEY_LENGTH": "API key length in characters",
            "SECURITY_DEFAULT_RATE_LIMIT_PER_MINUTE": "Default rate limit per minute",
            "SECURITY_DEFAULT_RATE_LIMIT_PER_DAY": "Default rate limit per day",
            
            # Logging optional
            "LOG_FORMAT": "Log format (json or text)",
            "LOG_MAX_FILE_SIZE_MB": "Maximum log file size in MB",
            "LOG_BACKUP_COUNT": "Number of backup log files to keep",
        }
    
    @staticmethod
    def validate_environment() -> Dict[str, Any]:
        """
        Validate current environment variables.
        
        Returns:
            Dictionary with validation results
        """
        required_vars = EnvironmentManager.get_required_env_vars()
        optional_vars = EnvironmentManager.get_optional_env_vars()
        all_vars = {**required_vars, **optional_vars}
        
        missing_required = []
        present_vars = {}
        invalid_vars = {}
        
        # Check required variables
        for var_name, description in required_vars.items():
            value = os.getenv(var_name)
            if value is None:
                missing_required.append(var_name)
            else:
                present_vars[var_name] = value
        
        # Check all present variables
        for var_name in all_vars:
            value = os.getenv(var_name)
            if value is not None:
                validation_error = EnvironmentManager._validate_env_var_value(var_name, value)
                if validation_error:
                    invalid_vars[var_name] = validation_error
        
        return {
            "is_valid": len(missing_required) == 0 and len(invalid_vars) == 0,
            "missing_required": missing_required,
            "present_vars": list(present_vars.keys()),
            "invalid_vars": invalid_vars,
            "total_required": len(required_vars),
            "total_optional": len(optional_vars),
            "total_present": len(present_vars),
        }
    
    @staticmethod
    def _validate_env_var_value(var_name: str, value: str) -> Optional[str]:
        """
        Validate environment variable value.
        
        Args:
            var_name: Environment variable name
            value: Environment variable value
            
        Returns:
            Error message if invalid, None if valid
        """
        # Port validation
        if var_name.endswith("_PORT"):
            try:
                port = int(value)
                if not (1 <= port <= 65535):
                    return f"Port must be between 1-65535, got {port}"
            except ValueError:
                return f"Port must be a number, got '{value}'"
        
        # Boolean validation
        if var_name.endswith(("_ENABLE_", "_ENFORCE_")) or "ENABLE" in var_name:
            if value.lower() not in ("true", "false", "1", "0", "yes", "no"):
                return f"Boolean value expected, got '{value}'"
        
        # Number validation
        if "SIZE_MB" in var_name or "TIMEOUT" in var_name or "LIMIT" in var_name:
            try:
                num = float(value)
                if num < 0:
                    return f"Non-negative number expected, got {num}"
            except ValueError:
                return f"Number expected, got '{value}'"
        
        # Log level validation
        if var_name == "LOG_LEVEL":
            valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if value.upper() not in valid_levels:
                return f"Invalid log level '{value}', must be one of: {valid_levels}"
        
        # Path validation
        if "DIRECTORY" in var_name or "PATH" in var_name:
            try:
                path = Path(value)
                if not path.is_absolute():
                    return f"Absolute path expected, got '{value}'"
            except Exception as e:
                return f"Invalid path '{value}': {e}"
        
        return None  # Valid
    
    @staticmethod
    def generate_env_file_template(include_optional: bool = True) -> str:
        """
        Generate .env file template with all configuration options.
        
        Args:
            include_optional: Whether to include optional variables
            
        Returns:
            .env file template content
        """
        required_vars = EnvironmentManager.get_required_env_vars()
        optional_vars = EnvironmentManager.get_optional_env_vars()
        
        template_lines = [
            "# bin2nlp Configuration File",
            "# Copy this file to .env and customize for your environment",
            "",
            "# =================================================================",
            "# REQUIRED CONFIGURATION",
            "# =================================================================",
            ""
        ]
        
        # Add required variables
        for var_name, description in sorted(required_vars.items()):
            template_lines.extend([
                f"# {description}",
                f"{var_name}=",
                ""
            ])
        
        if include_optional:
            template_lines.extend([
                "",
                "# =================================================================", 
                "# OPTIONAL CONFIGURATION",
                "# =================================================================",
                ""
            ])
            
            # Group optional variables by prefix
            grouped_vars = {}
            for var_name, description in optional_vars.items():
                prefix = var_name.split("_")[0]
                if prefix not in grouped_vars:
                    grouped_vars[prefix] = []
                grouped_vars[prefix].append((var_name, description))
            
            # Add grouped optional variables
            for prefix in sorted(grouped_vars.keys()):
                template_lines.extend([
                    f"# {prefix.title()} Configuration",
                    ""
                ])
                
                for var_name, description in sorted(grouped_vars[prefix]):
                    template_lines.extend([
                        f"# {description}",
                        f"# {var_name}=",
                        ""
                    ])
                
                template_lines.append("")
        
        return "\n".join(template_lines)
    
    @staticmethod
    def export_current_config() -> Dict[str, str]:
        """
        Export current configuration as environment variables.
        
        Returns:
            Dictionary of environment variable names and values
        """
        settings = get_settings()
        env_vars = {}
        
        # Database settings (PostgreSQL)
        env_vars.update({
            "DATABASE_HOST": settings.database.host,
            "DATABASE_PORT": str(settings.database.port),
            "DATABASE_NAME": settings.database.name,
            "DATABASE_USER": settings.database.user,
            "DATABASE_PASSWORD": settings.database.password,
            "DATABASE_POOL_SIZE": str(settings.database.pool_size),
            "DATABASE_POOL_TIMEOUT": str(settings.database.pool_timeout),
        })
        
        # API settings
        env_vars.update({
            "API_HOST": settings.api.host,
            "API_PORT": str(settings.api.port),
            "API_WORKERS": str(settings.api.workers),
            "API_MAX_REQUEST_SIZE": str(settings.api.max_request_size),
            "API_REQUEST_TIMEOUT": str(settings.api.request_timeout),
            "API_CORS_ORIGINS": ",".join(settings.api.cors_origins),
        })
        
        # Analysis settings
        env_vars.update({
            "ANALYSIS_MAX_FILE_SIZE_MB": str(settings.analysis.max_file_size_mb),
            "ANALYSIS_DEFAULT_TIMEOUT_SECONDS": str(settings.analysis.default_timeout_seconds),
            "ANALYSIS_MAX_TIMEOUT_SECONDS": str(settings.analysis.max_timeout_seconds),
            "ANALYSIS_TEMP_DIRECTORY": str(settings.analysis.temp_directory),
            "ANALYSIS_RADARE2_COMMAND": settings.analysis.radare2_command,
            "ANALYSIS_ENABLE_SANDBOXING": str(settings.analysis.enable_sandboxing).lower(),
        })
        
        # Security settings
        env_vars.update({
            "SECURITY_API_KEY_LENGTH": str(settings.security.api_key_length),
            "SECURITY_API_KEY_PREFIX": settings.security.api_key_prefix,
            "SECURITY_ENFORCE_HTTPS": str(settings.security.enforce_https).lower(),
        })
        
        # Logging settings
        env_vars.update({
            "LOG_LEVEL": settings.logging.level,
            "LOG_FORMAT": settings.logging.format,
            "LOG_MAX_FILE_SIZE_MB": str(settings.logging.max_file_size_mb),
            "LOG_BACKUP_COUNT": str(settings.logging.backup_count),
        })
        
        if settings.logging.file_path:
            env_vars["LOG_FILE_PATH"] = str(settings.logging.file_path)
        
        return env_vars