"""
Application configuration management using pydantic-settings.

Provides centralized configuration with environment variable support,
validation, and type safety for all application components.
"""

import os
import sys
import warnings
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Dict, Any, Union, Tuple
from urllib.parse import urlparse

from pydantic import Field, field_validator, computed_field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Redis database configuration settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        case_sensitive=False
    )
    
    host: str = Field(
        default="localhost",
        description="Redis server hostname"
    )
    
    port: int = Field(
        default=6379,
        ge=1,
        le=65535,
        description="Redis server port"
    )
    
    db: int = Field(
        default=0,
        ge=0,
        le=15,
        description="Redis database number"
    )
    
    password: Optional[str] = Field(
        default=None,
        description="Redis authentication password"
    )
    
    username: Optional[str] = Field(
        default=None,
        description="Redis authentication username"
    )
    
    max_connections: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum connection pool size"
    )
    
    socket_connect_timeout: float = Field(
        default=5.0,
        ge=0.1,
        le=60.0,
        description="Socket connection timeout in seconds"
    )
    
    socket_keepalive: bool = Field(
        default=True,
        description="Enable TCP keepalive"
    )
    
    health_check_interval: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Health check interval in seconds"
    )
    
    @computed_field
    @property
    def url(self) -> str:
        """Construct Redis connection URL."""
        auth_part = ""
        if self.username and self.password:
            auth_part = f"{self.username}:{self.password}@"
        elif self.password:
            auth_part = f":{self.password}@"
        
        return f"redis://{auth_part}{self.host}:{self.port}/{self.db}"


class AnalysisSettings(BaseSettings):
    """Binary analysis engine configuration settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="ANALYSIS_",
        case_sensitive=False
    )
    
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum file size for analysis in MB"
    )
    
    default_timeout_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Default analysis timeout in seconds"
    )
    
    max_timeout_seconds: int = Field(
        default=1200,
        ge=60,
        le=7200,
        description="Maximum allowed analysis timeout in seconds"
    )
    
    max_functions_per_analysis: int = Field(
        default=10000,
        ge=100,
        le=100000,
        description="Maximum functions to analyze per file"
    )
    
    max_strings_per_analysis: int = Field(
        default=50000,
        ge=1000,
        le=500000,
        description="Maximum strings to extract per file"
    )
    
    radare2_command: str = Field(
        default="r2",
        description="Radare2 command path"
    )
    
    enable_sandboxing: bool = Field(
        default=True,
        description="Enable analysis sandboxing"
    )
    
    worker_memory_limit_mb: int = Field(
        default=2048,
        ge=512,
        le=8192,
        description="Memory limit for analysis workers in MB"
    )
    
    temp_directory: Path = Field(
        default=Path("/tmp/bin2nlp"),
        description="Temporary directory for analysis files"
    )
    
    supported_formats: List[str] = Field(
        default_factory=lambda: ["pe", "elf", "macho", "raw"],
        description="Supported binary file formats"
    )
    
    @field_validator('temp_directory')
    @classmethod
    def validate_temp_directory(cls, v: Union[str, Path]) -> Path:
        """Validate and create temp directory if needed."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise ValueError(f"Temp directory is not accessible: {path}")
        return path


class APISettings(BaseSettings):
    """API server configuration settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="API_",
        case_sensitive=False
    )
    
    host: str = Field(
        default="0.0.0.0",
        description="API server bind address"
    )
    
    port: int = Field(
        default=8000,
        ge=1024,
        le=65535,
        description="API server port"
    )
    
    workers: int = Field(
        default=1,
        ge=1,
        le=32,
        description="Number of worker processes"
    )
    
    max_request_size: int = Field(
        default=104857600,  # 100MB
        ge=1048576,  # 1MB
        le=1073741824,  # 1GB
        description="Maximum request size in bytes"
    )
    
    request_timeout: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Request timeout in seconds"
    )
    
    cors_origins: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS origins"
    )
    
    cors_methods: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Allowed CORS methods"
    )
    
    cors_headers: List[str] = Field(
        default_factory=lambda: ["*"],
        description="Allowed CORS headers"
    )
    
    docs_url: Optional[str] = Field(
        default="/docs",
        description="OpenAPI documentation URL (None to disable)"
    )
    
    redoc_url: Optional[str] = Field(
        default="/redoc",
        description="ReDoc documentation URL (None to disable)"
    )


class SecuritySettings(BaseSettings):
    """Security and authentication configuration settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        case_sensitive=False
    )
    
    api_key_length: int = Field(
        default=32,
        ge=16,
        le=64,
        description="API key length in characters"
    )
    
    api_key_prefix: str = Field(
        default="ak_",
        min_length=1,
        max_length=10,
        description="API key prefix"
    )
    
    default_rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        le=10000,
        description="Default rate limit per minute"
    )
    
    default_rate_limit_per_day: int = Field(
        default=86400,  # 60 per minute * 60 minutes * 24 hours
        ge=100,
        le=1000000,
        description="Default rate limit per day"
    )
    
    max_api_keys_per_user: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum API keys per user"
    )
    
    api_key_expiry_days: int = Field(
        default=90,
        ge=1,
        le=3650,
        description="Default API key expiry in days"
    )
    
    enforce_https: bool = Field(
        default=False,
        description="Enforce HTTPS for API access"
    )
    
    trusted_proxies: List[str] = Field(
        default_factory=list,
        description="List of trusted proxy IP addresses"
    )


class CacheSettings(BaseSettings):
    """Cache configuration settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="CACHE_",
        case_sensitive=False
    )
    
    default_ttl_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="Default cache TTL in seconds"
    )
    
    analysis_result_ttl_seconds: int = Field(
        default=86400,
        ge=300,
        le=604800,
        description="Analysis result cache TTL in seconds"
    )
    
    job_status_ttl_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Job status cache TTL in seconds"
    )
    
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        description="Rate limit window in seconds"
    )
    
    max_cache_size_mb: int = Field(
        default=512,
        ge=64,
        le=4096,
        description="Maximum cache size in MB"
    )
    
    enable_compression: bool = Field(
        default=True,
        description="Enable cache value compression"
    )


class LoggingSettings(BaseSettings):
    """Logging configuration settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        case_sensitive=False
    )
    
    level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level"
    )
    
    format: str = Field(
        default="json",
        pattern="^(json|text)$",
        description="Log format (json or text)"
    )
    
    file_path: Optional[Path] = Field(
        default=None,
        description="Log file path (None for stdout only)"
    )
    
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum log file size in MB"
    )
    
    backup_count: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of backup log files to keep"
    )
    
    enable_correlation_id: bool = Field(
        default=True,
        description="Enable correlation ID logging"
    )
    
    sensitive_fields: List[str] = Field(
        default_factory=lambda: ["password", "api_key", "token", "secret"],
        description="Fields to redact in logs"
    )


class Settings(BaseSettings):
    """Main application settings container."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application metadata
    app_name: str = Field(
        default="bin2nlp",
        description="Application name"
    )
    
    app_version: str = Field(
        default="1.0.0",
        description="Application version"
    )
    
    environment: str = Field(
        default="development",
        pattern="^(development|testing|staging|production)$",
        description="Application environment"
    )
    
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    # Component settings
    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
        description="Database configuration"
    )
    
    analysis: AnalysisSettings = Field(
        default_factory=AnalysisSettings,
        description="Analysis engine configuration"
    )
    
    api: APISettings = Field(
        default_factory=APISettings,
        description="API server configuration"
    )
    
    security: SecuritySettings = Field(
        default_factory=SecuritySettings,
        description="Security configuration"
    )
    
    cache: CacheSettings = Field(
        default_factory=CacheSettings,
        description="Cache configuration"
    )
    
    logging: LoggingSettings = Field(
        default_factory=LoggingSettings,
        description="Logging configuration"
    )
    
    @computed_field
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"
    
    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"
    
    @computed_field
    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        return self.database.url
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment setting."""
        v = v.lower()
        if v not in ["development", "testing", "staging", "production"]:
            raise ValueError("Invalid environment")
        return v
    
    def get_max_file_size_bytes(self) -> int:
        """Get maximum file size in bytes."""
        return self.analysis.max_file_size_mb * 1024 * 1024
    
    def get_worker_memory_limit_bytes(self) -> int:
        """Get worker memory limit in bytes."""
        return self.analysis.worker_memory_limit_mb * 1024 * 1024
    
    def get_rate_limits(self) -> Dict[str, Dict[str, int]]:
        """Get rate limit configuration by tier."""
        return {
            "basic": {
                "per_minute": 10,
                "per_hour": 600,
                "per_day": 14400,
                "burst": 5
            },
            "standard": {
                "per_minute": self.security.default_rate_limit_per_minute,
                "per_hour": self.security.default_rate_limit_per_minute * 60,
                "per_day": self.security.default_rate_limit_per_day,
                "burst": 20
            },
            "premium": {
                "per_minute": 300,
                "per_hour": 18000,
                "per_day": 432000,
                "burst": 50
            },
            "enterprise": {
                "per_minute": 1000,
                "per_hour": 60000,
                "per_day": 1440000,
                "burst": 100
            },
            "unlimited": {
                "per_minute": 999999,
                "per_hour": 999999,
                "per_day": 999999,
                "burst": 999999
            }
        }
    
    def get_analysis_timeouts(self) -> Dict[str, int]:
        """Get analysis timeout configuration by depth."""
        return {
            "quick": min(60, self.analysis.default_timeout_seconds),
            "standard": self.analysis.default_timeout_seconds,
            "comprehensive": min(self.analysis.max_timeout_seconds, 
                                self.analysis.default_timeout_seconds * 2),
            "deep": self.analysis.max_timeout_seconds
        }
    
    def to_config_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary for debugging."""
        config = self.model_dump()
        
        # Redact sensitive information
        if "database" in config and "password" in config["database"]:
            config["database"]["password"] = "***REDACTED***"
        
        return config


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings singleton.
    
    Returns cached settings instance, loading from environment
    variables and configuration files on first call.
    """
    return Settings()


def validate_settings() -> bool:
    """
    Validate current settings configuration.
    
    Returns:
        bool: True if settings are valid, raises exception otherwise
    """
    try:
        settings = get_settings()
        
        # Test Redis connection URL parsing
        parsed_url = urlparse(settings.redis_url)
        if not parsed_url.hostname:
            raise ValueError("Invalid Redis URL")
        
        # Validate temp directory is writable
        temp_dir = settings.analysis.temp_directory
        test_file = temp_dir / ".write_test"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            raise ValueError(f"Temp directory not writable: {e}")
        
        # Validate rate limit consistency
        rate_limits = settings.get_rate_limits()
        for tier, limits in rate_limits.items():
            if limits["per_minute"] * 60 > limits["per_hour"]:
                raise ValueError(f"Rate limit inconsistency in tier {tier}")
        
        return True
        
    except Exception as e:
        raise ValueError(f"Settings validation failed: {e}")


def create_example_env_file(path: str = ".env.example") -> None:
    """
    Create an example environment file with all configuration options.
    
    Args:
        path: Path to create the example file
    """
    env_content = """# bin2nlp Configuration Example
# Copy this file to .env and customize for your environment

# Application Settings
APP_NAME=bin2nlp
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=false

# Redis Database Settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_USERNAME=
REDIS_MAX_CONNECTIONS=20
REDIS_SOCKET_CONNECT_TIMEOUT=5.0
REDIS_SOCKET_KEEPALIVE=true
REDIS_HEALTH_CHECK_INTERVAL=30

# Analysis Engine Settings
ANALYSIS_MAX_FILE_SIZE_MB=100
ANALYSIS_DEFAULT_TIMEOUT_SECONDS=300
ANALYSIS_MAX_TIMEOUT_SECONDS=1200
ANALYSIS_MAX_FUNCTIONS_PER_ANALYSIS=10000
ANALYSIS_MAX_STRINGS_PER_ANALYSIS=50000
ANALYSIS_RADARE2_COMMAND=r2
ANALYSIS_ENABLE_SANDBOXING=true
ANALYSIS_WORKER_MEMORY_LIMIT_MB=2048
ANALYSIS_TEMP_DIRECTORY=/tmp/bin2nlp

# API Server Settings
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1
API_MAX_REQUEST_SIZE=104857600
API_REQUEST_TIMEOUT=300
API_CORS_ORIGINS=*
API_DOCS_URL=/docs
API_REDOC_URL=/redoc

# Security Settings
SECURITY_API_KEY_LENGTH=32
SECURITY_API_KEY_PREFIX=ak_
SECURITY_DEFAULT_RATE_LIMIT_PER_MINUTE=60
SECURITY_DEFAULT_RATE_LIMIT_PER_DAY=10000
SECURITY_MAX_API_KEYS_PER_USER=10
SECURITY_API_KEY_EXPIRY_DAYS=90
SECURITY_ENFORCE_HTTPS=false

# Cache Settings
CACHE_DEFAULT_TTL_SECONDS=3600
CACHE_ANALYSIS_RESULT_TTL_SECONDS=86400
CACHE_JOB_STATUS_TTL_SECONDS=300
CACHE_RATE_LIMIT_WINDOW_SECONDS=60
CACHE_MAX_CACHE_SIZE_MB=512
CACHE_ENABLE_COMPRESSION=true

# Logging Settings
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE_PATH=
LOG_MAX_FILE_SIZE_MB=100
LOG_BACKUP_COUNT=5
LOG_ENABLE_CORRELATION_ID=true
"""
    
    with open(path, 'w') as f:
        f.write(env_content)


def check_required_environment_variables() -> Tuple[bool, List[str]]:
    """
    Check for required environment variables and system dependencies.
    
    Returns:
        Tuple of (success, list of missing/invalid items)
    """
    missing_items = []
    
    # Check critical environment variables for production
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        critical_vars = [
            "REDIS_HOST",
            "REDIS_PASSWORD",
            "SECURITY_ENFORCE_HTTPS",
            "LOG_LEVEL"
        ]
        
        for var in critical_vars:
            if not os.getenv(var):
                missing_items.append(f"Environment variable {var} is required in production")
    
    # Check system dependencies
    try:
        import redis
    except ImportError:
        missing_items.append("Redis Python client not installed (pip install redis)")
    
    try:
        import r2pipe
    except ImportError:
        missing_items.append("r2pipe not installed (pip install r2pipe)")
    
    # Check radare2 availability
    radare2_cmd = os.getenv("ANALYSIS_RADARE2_COMMAND", "r2")
    if os.system(f"which {radare2_cmd} >/dev/null 2>&1") != 0:
        missing_items.append(f"radare2 not found in PATH (command: {radare2_cmd})")
    
    # Check temp directory permissions
    temp_dir = Path(os.getenv("ANALYSIS_TEMP_DIRECTORY", "/tmp/bin2nlp"))
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
        test_file = temp_dir / ".write_test"
        test_file.write_text("test")
        test_file.unlink()
    except Exception as e:
        missing_items.append(f"Cannot write to temp directory {temp_dir}: {e}")
    
    return len(missing_items) == 0, missing_items


def validate_configuration_consistency() -> Tuple[bool, List[str]]:
    """
    Validate internal configuration consistency and logical constraints.
    
    Returns:
        Tuple of (success, list of validation errors)
    """
    errors = []
    
    try:
        settings = get_settings()
        
        # Timeout validation
        if settings.analysis.default_timeout_seconds > settings.analysis.max_timeout_seconds:
            errors.append("Default timeout cannot exceed maximum timeout")
        
        # Memory validation
        if settings.analysis.worker_memory_limit_mb < 512:
            errors.append("Worker memory limit too low (minimum 512MB)")
        
        # Port validation
        if settings.api.port == settings.database.port:
            errors.append("API and Redis ports cannot be the same")
        
        # Rate limit validation
        rate_limits = settings.get_rate_limits()
        for tier, limits in rate_limits.items():
            if tier == "unlimited":
                continue
            
            # Check minute/hour consistency
            if limits["per_minute"] * 60 > limits["per_hour"]:
                errors.append(f"Rate limit inconsistency in {tier} tier: "
                            f"per_minute ({limits['per_minute']}) * 60 > per_hour ({limits['per_hour']})")
            
            # Check hour/day consistency
            if limits["per_hour"] * 24 > limits["per_day"]:
                errors.append(f"Rate limit inconsistency in {tier} tier: "
                            f"per_hour ({limits['per_hour']}) * 24 > per_day ({limits['per_day']})")
        
        # File size validation
        max_request_size_mb = settings.api.max_request_size / (1024 * 1024)
        if max_request_size_mb < settings.analysis.max_file_size_mb:
            errors.append("API max request size should be >= analysis max file size")
        
        # CORS validation for production
        if settings.is_production and "*" in settings.api.cors_origins:
            errors.append("Wildcard CORS origins not recommended for production")
        
        # HTTPS validation for production
        if settings.is_production and not settings.security.enforce_https:
            errors.append("HTTPS should be enforced in production")
        
    except Exception as e:
        errors.append(f"Configuration validation failed: {e}")
    
    return len(errors) == 0, errors


def detect_configuration_issues() -> Dict[str, List[str]]:
    """
    Comprehensive configuration health check.
    
    Returns:
        Dictionary with categories of issues found
    """
    issues = {
        "critical": [],
        "warnings": [],
        "recommendations": []
    }
    
    # Check environment variables
    env_ok, env_issues = check_required_environment_variables()
    if not env_ok:
        issues["critical"].extend(env_issues)
    
    # Check configuration consistency
    config_ok, config_errors = validate_configuration_consistency()
    if not config_ok:
        issues["critical"].extend(config_errors)
    
    # Performance recommendations
    try:
        settings = get_settings()
        
        # Memory recommendations
        worker_memory_gb = settings.analysis.worker_memory_limit_mb / 1024
        if worker_memory_gb < 2:
            issues["recommendations"].append(
                f"Consider increasing worker memory limit (current: {worker_memory_gb}GB, recommended: 2GB+)"
            )
        
        # Connection pool recommendations
        if settings.database.max_connections < 10:
            issues["recommendations"].append(
                "Consider increasing Redis connection pool size for better concurrency"
            )
        
        # Cache size recommendations
        cache_size_gb = settings.cache.max_cache_size_mb / 1024
        if cache_size_gb < 1:
            issues["recommendations"].append(
                f"Consider increasing cache size (current: {cache_size_gb}GB, recommended: 1GB+)"
            )
        
        # Development warnings
        if settings.is_development:
            if settings.debug:
                issues["warnings"].append("Debug mode is enabled - disable in production")
            
            if not settings.security.enforce_https:
                issues["warnings"].append("HTTPS not enforced - ensure this is enabled in production")
    
    except Exception as e:
        issues["critical"].append(f"Failed to analyze configuration: {e}")
    
    return issues


def create_configuration_report() -> str:
    """
    Generate a comprehensive configuration status report.
    
    Returns:
        Formatted report string
    """
    report_lines = [
        "=== bin2nlp Configuration Report ===",
        ""
    ]
    
    # Basic info
    try:
        settings = get_settings()
        report_lines.extend([
            f"Environment: {settings.environment}",
            f"Debug Mode: {settings.debug}",
            f"Application: {settings.app_name} v{settings.app_version}",
            ""
        ])
    except Exception as e:
        report_lines.extend([
            f"ERROR: Failed to load settings: {e}",
            ""
        ])
        return "\n".join(report_lines)
    
    # Configuration issues
    issues = detect_configuration_issues()
    
    if issues["critical"]:
        report_lines.extend([
            "🚨 CRITICAL ISSUES:",
            *[f"  - {issue}" for issue in issues["critical"]],
            ""
        ])
    
    if issues["warnings"]:
        report_lines.extend([
            "⚠️  WARNINGS:",
            *[f"  - {warning}" for warning in issues["warnings"]],
            ""
        ])
    
    if issues["recommendations"]:
        report_lines.extend([
            "💡 RECOMMENDATIONS:",
            *[f"  - {rec}" for rec in issues["recommendations"]],
            ""
        ])
    
    if not any(issues.values()):
        report_lines.extend([
            "✅ Configuration looks good!",
            ""
        ])
    
    # Component summary
    report_lines.extend([
        "=== Component Configuration ===",
        f"Redis: {settings.database.host}:{settings.database.port}",
        f"API Server: {settings.api.host}:{settings.api.port}",
        f"Worker Memory Limit: {settings.analysis.worker_memory_limit_mb}MB",
        f"Max File Size: {settings.analysis.max_file_size_mb}MB",
        f"Cache TTL: {settings.cache.analysis_result_ttl_seconds}s",
        f"Rate Limit: {settings.security.default_rate_limit_per_minute}/min",
        ""
    ])
    
    return "\n".join(report_lines)


def validate_and_warn() -> bool:
    """
    Validate configuration and print warnings for development use.
    
    Returns:
        True if configuration is valid, False if critical issues found
    """
    issues = detect_configuration_issues()
    
    if issues["critical"]:
        print("🚨 CRITICAL CONFIGURATION ISSUES:", file=sys.stderr)
        for issue in issues["critical"]:
            print(f"  - {issue}", file=sys.stderr)
        return False
    
    if issues["warnings"]:
        for warning in issues["warnings"]:
            warnings.warn(f"Configuration warning: {warning}")
    
    return True


def load_and_validate_settings() -> Settings:
    """
    Load settings with comprehensive validation and error handling.
    
    Returns:
        Validated Settings instance
        
    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If critical dependencies are missing
    """
    # Check environment and dependencies first
    env_ok, env_issues = check_required_environment_variables()
    if not env_ok:
        raise RuntimeError("Critical environment issues:\n" + "\n".join(f"  - {issue}" for issue in env_issues))
    
    # Load settings
    try:
        settings = Settings()
    except ValidationError as e:
        raise ValueError(f"Configuration validation failed:\n{e}")
    
    # Validate configuration consistency
    config_ok, config_errors = validate_configuration_consistency()
    if not config_ok:
        raise ValueError("Configuration consistency errors:\n" + "\n".join(f"  - {error}" for error in config_errors))
    
    return settings