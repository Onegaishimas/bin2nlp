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

from pydantic import Field, field_validator, computed_field, ValidationError, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="DATABASE_",
        case_sensitive=False
    )
    
    host: str = Field(
        default="localhost",
        description="PostgreSQL server hostname"
    )
    
    port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        description="PostgreSQL server port"
    )
    
    name: str = Field(
        default="bin2nlp",
        description="PostgreSQL database name"
    )
    
    user: str = Field(
        default="bin2nlp",
        description="PostgreSQL database user"
    )
    
    password: str = Field(
        default="bin2nlp_password",
        description="PostgreSQL authentication password"
    )
    
    echo: bool = Field(
        default=False,
        description="Enable SQL query logging"
    )
    
    pool_size: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Connection pool size"
    )
    
    max_overflow: int = Field(
        default=20,
        ge=0,
        le=100,
        description="Maximum pool overflow connections"
    )
    
    pool_timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Pool connection timeout in seconds"
    )
    
    pool_recycle: int = Field(
        default=3600,
        ge=300,
        le=86400,
        description="Connection recycle time in seconds"
    )
    
    @computed_field
    @property
    def url(self) -> str:
        """Construct PostgreSQL connection URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


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


# SecuritySettings class removed - open access system


class StorageSettings(BaseSettings):
    """File storage configuration settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="STORAGE_",
        case_sensitive=False
    )
    
    base_path: Path = Field(
        default=Path("/var/lib/app/data"),
        description="Base path for file storage"
    )
    
    cache_ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="File cache TTL in hours"
    )
    
    max_file_size_mb: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum stored file size in MB"
    )
    
    enable_compression: bool = Field(
        default=True,
        description="Enable file compression"
    )
    
    cleanup_interval_hours: int = Field(
        default=6,
        ge=1,
        le=24,
        description="Cleanup interval in hours"
    )
    
    @field_validator('base_path')
    @classmethod
    def validate_base_path(cls, v: Union[str, Path]) -> Path:
        """Validate and create base path if needed."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        if not path.is_dir():
            raise ValueError(f"Storage base path is not accessible: {path}")
        return path


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


class LLMSettings(BaseSettings):
    """LLM provider configuration settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        case_sensitive=False
    )
    
    # Provider Configuration
    enabled_providers: List[str] = Field(
        default_factory=lambda: ["openai"],
        description="List of enabled LLM providers (openai, anthropic, gemini)"
    )
    
    default_provider: str = Field(
        default="openai",
        description="Default LLM provider to use"
    )
    
    # OpenAI Configuration
    openai_api_key: Optional[SecretStr] = Field(
        default=None,
        description="OpenAI API key"
    )
    
    openai_base_url: Optional[str] = Field(
        default=None,
        description="Custom OpenAI API base URL (for compatible endpoints)"
    )
    
    openai_default_model: str = Field(
        default="gpt-4",
        description="Default OpenAI model"
    )
    
    openai_organization: Optional[str] = Field(
        default=None,
        description="OpenAI organization ID"
    )
    
    # Anthropic Configuration
    anthropic_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Anthropic API key"
    )
    
    anthropic_default_model: str = Field(
        default="claude-3-sonnet-20240229",
        description="Default Anthropic model"
    )
    
    # Google Gemini Configuration
    gemini_api_key: Optional[SecretStr] = Field(
        default=None,
        description="Google Gemini API key"
    )
    
    gemini_default_model: str = Field(
        default="gemini-pro",
        description="Default Gemini model"
    )
    
    # Common Provider Settings
    default_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Default temperature for text generation"
    )
    
    default_max_tokens: int = Field(
        default=2048,
        ge=100,
        le=8192,
        description="Default maximum tokens for responses"
    )
    
    request_timeout_seconds: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Request timeout for LLM API calls"
    )
    
    # Rate Limiting
    requests_per_minute: int = Field(
        default=60,
        ge=1,
        le=10000,
        description="Maximum LLM requests per minute"
    )
    
    tokens_per_minute: int = Field(
        default=40000,
        ge=1000,
        le=500000,
        description="Maximum tokens per minute across all providers"
    )
    
    # Cost Controls
    daily_spend_limit_usd: float = Field(
        default=100.0,
        ge=0.0,
        description="Daily spending limit in USD"
    )
    
    monthly_spend_limit_usd: float = Field(
        default=1000.0,
        ge=0.0,
        description="Monthly spending limit in USD"
    )
    
    cost_alert_thresholds: List[float] = Field(
        default_factory=lambda: [50.0, 75.0, 90.0],
        description="Cost alert thresholds as percentages of limits"
    )
    
    # Provider Selection
    enable_fallback: bool = Field(
        default=True,
        description="Enable automatic fallback between providers"
    )
    
    cost_optimization: bool = Field(
        default=False,
        description="Prioritize cost-optimized provider selection"
    )
    
    performance_priority: bool = Field(
        default=False,
        description="Prioritize performance-optimized provider selection"
    )
    
    # Health Monitoring
    health_check_interval_minutes: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Provider health check interval in minutes"
    )
    
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Consecutive failures before circuit breaker opens"
    )
    
    circuit_breaker_timeout_minutes: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Circuit breaker timeout in minutes"
    )
    
    @field_validator('enabled_providers')
    @classmethod
    def validate_enabled_providers(cls, v: List[str]) -> List[str]:
        """Validate enabled providers list."""
        valid_providers = {"openai", "anthropic", "gemini"}
        validated = []
        
        for provider in v:
            provider = provider.lower().strip()
            if provider not in valid_providers:
                raise ValueError(f"Invalid provider: {provider}. Valid providers: {valid_providers}")
            if provider not in validated:
                validated.append(provider)
        
        if not validated:
            raise ValueError("At least one provider must be enabled")
        
        return validated
    
    @field_validator('default_provider')
    @classmethod
    def validate_default_provider(cls, v: str) -> str:
        """Validate default provider."""
        valid_providers = {"openai", "anthropic", "gemini"}
        v = v.lower().strip()
        if v not in valid_providers:
            raise ValueError(f"Invalid default provider: {v}. Valid providers: {valid_providers}")
        return v
    
    @field_validator('openai_base_url')
    @classmethod
    def validate_base_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate API base URL format."""
        if v is None:
            return v
        
        v = v.strip()
        if not v.startswith(('http://', 'https://')):
            raise ValueError("Base URL must start with http:// or https://")
        
        return v.rstrip('/')
    
    @field_validator('cost_alert_thresholds')
    @classmethod
    def validate_cost_thresholds(cls, v: List[float]) -> List[float]:
        """Validate cost alert thresholds."""
        if not v:
            return []
        
        # Ensure all values are between 0 and 100
        for threshold in v:
            if not (0.0 <= threshold <= 100.0):
                raise ValueError("Cost alert thresholds must be between 0 and 100")
        
        # Sort and remove duplicates
        return sorted(list(set(v)))
    
    def get_provider_config(self, provider_id: str) -> Dict[str, Any]:
        """Get configuration for a specific provider."""
        provider_id = provider_id.lower()
        
        if provider_id == "openai":
            return {
                "provider_id": "openai",
                "api_key": self.openai_api_key,
                "base_url": self.openai_base_url,
                "default_model": self.openai_default_model,
                "organization": self.openai_organization,
                "temperature": self.default_temperature,
                "max_tokens": self.default_max_tokens,
                "timeout_seconds": self.request_timeout_seconds,
                "requests_per_minute": self.requests_per_minute,
                "tokens_per_minute": self.tokens_per_minute,
                "daily_spend_limit": self.daily_spend_limit_usd,
                "monthly_spend_limit": self.monthly_spend_limit_usd
            }
        
        elif provider_id == "anthropic":
            return {
                "provider_id": "anthropic",
                "api_key": self.anthropic_api_key,
                "default_model": self.anthropic_default_model,
                "temperature": self.default_temperature,
                "max_tokens": self.default_max_tokens,
                "timeout_seconds": self.request_timeout_seconds,
                "requests_per_minute": self.requests_per_minute,
                "tokens_per_minute": self.tokens_per_minute,
                "daily_spend_limit": self.daily_spend_limit_usd,
                "monthly_spend_limit": self.monthly_spend_limit_usd
            }
        
        elif provider_id == "gemini":
            return {
                "provider_id": "gemini",
                "api_key": self.gemini_api_key,
                "default_model": self.gemini_default_model,
                "temperature": self.default_temperature,
                "max_tokens": self.default_max_tokens,
                "timeout_seconds": self.request_timeout_seconds,
                "requests_per_minute": self.requests_per_minute,
                "tokens_per_minute": self.tokens_per_minute,
                "daily_spend_limit": self.daily_spend_limit_usd,
                "monthly_spend_limit": self.monthly_spend_limit_usd
            }
        
        else:
            raise ValueError(f"Unknown provider: {provider_id}")
    
    def get_enabled_provider_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get configurations for all enabled providers."""
        configs = {}
        for provider_id in self.enabled_providers:
            configs[provider_id] = self.get_provider_config(provider_id)
        return configs
    
    def validate_provider_credentials(self) -> Dict[str, bool]:
        """Validate that required credentials are configured for enabled providers."""
        validation_results = {}
        
        for provider_id in self.enabled_providers:
            if provider_id == "openai":
                validation_results[provider_id] = self.openai_api_key is not None
            elif provider_id == "anthropic":
                validation_results[provider_id] = self.anthropic_api_key is not None
            elif provider_id == "gemini":
                validation_results[provider_id] = self.gemini_api_key is not None
        
        return validation_results


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
    
# Security configuration removed - open access system
    
    storage: StorageSettings = Field(
        default_factory=StorageSettings,
        description="File storage configuration"
    )
    
    logging: LoggingSettings = Field(
        default_factory=LoggingSettings,
        description="Logging configuration"
    )
    
    llm: LLMSettings = Field(
        default_factory=LLMSettings,
        description="LLM provider configuration"
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
    def database_url(self) -> str:
        """Get PostgreSQL connection URL."""
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
    
# Rate limiting methods removed - open access system
    
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
        
        # Redact LLM API keys
        if "llm" in config:
            for key in ["openai_api_key", "anthropic_api_key", "gemini_api_key"]:
                if key in config["llm"] and config["llm"][key]:
                    config["llm"][key] = "***REDACTED***"
        
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
        
        # Test PostgreSQL connection URL parsing
        parsed_url = urlparse(settings.database_url)
        if not parsed_url.hostname:
            raise ValueError("Invalid PostgreSQL URL")
        
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
            if tier == "unlimited":
                continue
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

# PostgreSQL Database Settings
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=bin2nlp
DATABASE_USER=bin2nlp
DATABASE_PASSWORD=bin2nlp_password
DATABASE_ECHO=false
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600

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

# Security Settings removed - open access system

# File Storage Settings
STORAGE_BASE_PATH=/var/lib/app/data
STORAGE_CACHE_TTL_HOURS=24
STORAGE_MAX_FILE_SIZE_MB=100
STORAGE_ENABLE_COMPRESSION=true
STORAGE_CLEANUP_INTERVAL_HOURS=6

# Logging Settings
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE_PATH=
LOG_MAX_FILE_SIZE_MB=100
LOG_BACKUP_COUNT=5
LOG_ENABLE_CORRELATION_ID=true

# LLM Provider Settings
LLM_ENABLED_PROVIDERS=openai,anthropic,gemini
LLM_DEFAULT_PROVIDER=openai
LLM_OPENAI_API_KEY=
LLM_OPENAI_BASE_URL=
LLM_OPENAI_DEFAULT_MODEL=gpt-4
LLM_OPENAI_ORGANIZATION=
LLM_ANTHROPIC_API_KEY=
LLM_ANTHROPIC_DEFAULT_MODEL=claude-3-sonnet-20240229
LLM_GEMINI_API_KEY=
LLM_GEMINI_DEFAULT_MODEL=gemini-pro
LLM_DEFAULT_TEMPERATURE=0.1
LLM_DEFAULT_MAX_TOKENS=2048
LLM_REQUEST_TIMEOUT_SECONDS=30
LLM_REQUESTS_PER_MINUTE=60
LLM_TOKENS_PER_MINUTE=40000
LLM_DAILY_SPEND_LIMIT_USD=100.0
LLM_MONTHLY_SPEND_LIMIT_USD=1000.0
LLM_COST_ALERT_THRESHOLDS=50.0,75.0,90.0
LLM_ENABLE_FALLBACK=true
LLM_COST_OPTIMIZATION=false
LLM_PERFORMANCE_PRIORITY=false
LLM_HEALTH_CHECK_INTERVAL_MINUTES=5
LLM_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
LLM_CIRCUIT_BREAKER_TIMEOUT_MINUTES=10
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
            "DATABASE_HOST",
            "DATABASE_PASSWORD",
            "SECURITY_ENFORCE_HTTPS",
            "LOG_LEVEL"
        ]
        
        for var in critical_vars:
            if not os.getenv(var):
                missing_items.append(f"Environment variable {var} is required in production")
    
    # Check system dependencies
    try:
        import asyncpg
    except ImportError:
        missing_items.append("PostgreSQL Python client not installed (pip install asyncpg)")
    
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
            errors.append("API and PostgreSQL ports cannot be the same")
        
        # File size validation
        max_request_size_mb = settings.api.max_request_size / (1024 * 1024)
        if max_request_size_mb < settings.analysis.max_file_size_mb:
            errors.append("API max request size should be >= analysis max file size")
        
        # CORS validation for production
        if settings.is_production and "*" in settings.api.cors_origins:
            errors.append("Wildcard CORS origins not recommended for production")
        
        # Note: HTTPS and rate limiting validation removed - open access system
        
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
        if settings.database.pool_size < 10:
            issues["recommendations"].append(
                "Consider increasing PostgreSQL connection pool size for better concurrency"
            )
        
        # Storage size recommendations  
        storage_size_mb = settings.storage.max_file_size_mb
        if storage_size_mb < 100:
            issues["recommendations"].append(
                f"Consider increasing storage file size limit (current: {storage_size_mb}MB, recommended: 100MB+)"
            )
        
        # Development warnings
        if settings.is_development:
            if settings.debug:
                issues["warnings"].append("Debug mode is enabled - disable in production")
            
            # Note: HTTPS enforcement removed for open access system
    
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
        f"PostgreSQL: {settings.database.host}:{settings.database.port}/{settings.database.name}",
        f"API Server: {settings.api.host}:{settings.api.port}",
        f"Worker Memory Limit: {settings.analysis.worker_memory_limit_mb}MB",
        f"Max File Size: {settings.analysis.max_file_size_mb}MB",
        f"Storage TTL: {settings.storage.cache_ttl_hours}h",
        "Rate Limiting: Disabled (open access)",
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