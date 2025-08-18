"""
Test fixtures for LLM provider mock responses.

Provides realistic mock responses for different LLM providers with varied
translation styles, complexity levels, and error scenarios for comprehensive testing.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import random


class MockLLMResponse:
    """Container for mock LLM response data."""
    
    def __init__(
        self,
        provider: str,
        model: str,
        content: str,
        tokens_used: int,
        response_time_ms: int,
        quality_score: float = 8.0,
        confidence: float = 0.9
    ):
        self.provider = provider
        self.model = model
        self.content = content
        self.tokens_used = tokens_used
        self.response_time_ms = response_time_ms
        self.quality_score = quality_score
        self.confidence = confidence
        self.timestamp = datetime.utcnow()


# OpenAI GPT-4 Style Responses - Technical and structured
OPENAI_FUNCTION_TRANSLATIONS = [
    MockLLMResponse(
        provider="openai",
        model="gpt-4",
        content="""This function implements a string comparison routine for password validation. It takes two parameters: a user-input password and a stored hash value. The function first validates the input length (must be between 8-64 characters), then applies a cryptographic hash function (appears to be SHA-256 based on the register usage patterns) to the input password. It performs a constant-time comparison against the stored hash to prevent timing attacks. The function returns 1 for successful validation, 0 for failure, with additional error codes for invalid input lengths.""",
        tokens_used=156,
        response_time_ms=850,
        quality_score=9.2,
        confidence=0.95
    ),
    MockLLMResponse(
        provider="openai", 
        model="gpt-4",
        content="""This appears to be a network communication handler function. It establishes a TCP socket connection, configures SSL/TLS encryption parameters, and manages data transmission with error handling and retry logic. The function includes buffer management for incoming/outgoing data streams and implements a state machine for connection management. Notable security features include certificate validation and protection against buffer overflow attacks through boundary checking.""",
        tokens_used=132,
        response_time_ms=720,
        quality_score=8.8,
        confidence=0.92
    ),
    MockLLMResponse(
        provider="openai",
        model="gpt-4",
        content="""This is a memory allocation wrapper function that provides additional safety checks beyond standard malloc(). It validates the requested size against system limits, initializes allocated memory to zero, and maintains metadata for tracking allocations. The function includes overflow detection and implements a simple garbage collection mechanism for automatic cleanup. This pattern is commonly used in security-conscious applications to prevent common memory-related vulnerabilities.""",
        tokens_used=144,
        response_time_ms=760,
        quality_score=9.0,
        confidence=0.94
    )
]

# Anthropic Claude Style Responses - Detailed and context-aware
ANTHROPIC_FUNCTION_TRANSLATIONS = [
    MockLLMResponse(
        provider="anthropic",
        model="claude-3-sonnet-20240229",
        content="""Looking at this function's assembly code, I can see it's implementing a sophisticated string processing routine with multiple layers of validation and transformation. The function begins by performing input sanitization - checking for null pointers, validating string length boundaries, and ensuring the input conforms to expected character encoding (appears to be UTF-8 based on the byte sequence checking patterns).

The core processing involves a multi-pass algorithm: first pass performs character-by-character validation and normalization, second pass applies what appears to be a compression or encoding transformation (possibly Base64 or similar), and a final pass that generates a checksum or hash for integrity verification. The function is particularly careful about memory management, using stack-allocated buffers where possible and implementing explicit bounds checking throughout.""",
        tokens_used=198,
        response_time_ms=1200,
        quality_score=9.5,
        confidence=0.96
    ),
    MockLLMResponse(
        provider="anthropic",
        model="claude-3-sonnet-20240229", 
        content="""This function represents a file I/O operation with advanced error recovery capabilities. It attempts to open, read, and process a file while implementing a comprehensive error handling strategy. The function includes retry logic for transient failures, alternative path resolution for missing files, and graceful degradation when permissions are insufficient.

What's particularly interesting is the function's approach to data validation - it appears to be parsing a structured file format (possibly JSON or XML based on the parsing patterns) and includes schema validation to ensure data integrity. The function maintains detailed logging throughout the process, which would be valuable for debugging and monitoring in production environments. The return value encoding suggests it can provide detailed error information to callers, not just binary success/failure.""",
        tokens_used=225,
        response_time_ms=1350,
        quality_score=9.3,
        confidence=0.93
    )
]

# Google Gemini Style Responses - Balanced and practical
GEMINI_FUNCTION_TRANSLATIONS = [
    MockLLMResponse(
        provider="gemini", 
        model="gemini-pro",
        content="""This function handles user authentication through a multi-factor verification process. It first validates the username and password combination using secure hashing, then proceeds to verify a secondary authentication factor (likely TOTP or SMS-based). The function implements proper session management, creating secure tokens and setting appropriate expiration times. Security features include rate limiting to prevent brute force attacks and secure storage of authentication state.""",
        tokens_used=118,
        response_time_ms=650,
        quality_score=8.5,
        confidence=0.91
    ),
    MockLLMResponse(
        provider="gemini",
        model="gemini-pro", 
        content="""This appears to be a data processing pipeline function that transforms input data through multiple stages. It begins with input validation and normalization, applies business logic transformations (possibly data enrichment or formatting), and concludes with output generation in a standardized format. The function includes comprehensive error handling and logging at each stage, making it suitable for production data processing workloads.""",
        tokens_used=105,
        response_time_ms=580,
        quality_score=8.3,
        confidence=0.89
    )
]

# Ollama Style Responses - Concise and focused
OLLAMA_FUNCTION_TRANSLATIONS = [
    MockLLMResponse(
        provider="ollama",
        model="huihui_ai/phi4-abliterated",
        content="""This function implements a secure random number generator for cryptographic purposes. It uses system entropy sources and applies additional randomness processing to ensure unpredictable output. The function includes seed management and periodic reseeding for long-running applications.""",
        tokens_used=78,
        response_time_ms=450,
        quality_score=8.0,
        confidence=0.87
    ),
    MockLLMResponse(
        provider="ollama",
        model="huihui_ai/phi4-abliterated",
        content="""Network packet processing function that parses incoming data, validates packet structure, and routes packets to appropriate handlers. Includes basic intrusion detection and packet filtering capabilities.""",
        tokens_used=65,
        response_time_ms=380,
        quality_score=7.8,
        confidence=0.85
    )
]

# Import/Library Explanations by Provider
OPENAI_IMPORT_EXPLANATIONS = [
    MockLLMResponse(
        provider="openai",
        model="gpt-4", 
        content="""**CreateFileW** (kernel32.dll): Windows API function for creating or opening files with Unicode filename support. Commonly used in applications that need to handle international filenames or when explicit Unicode support is required. Parameters include desired access rights, sharing mode, security attributes, creation disposition, and file attributes. Essential for file I/O operations in Windows applications.""",
        tokens_used=95,
        response_time_ms=520,
        quality_score=9.0,
        confidence=0.94
    ),
    MockLLMResponse(
        provider="openai", 
        model="gpt-4",
        content="""**WSAStartup** (ws2_32.dll): Initializes the Windows Sockets API for network communication. Must be called before any other Winsock functions. Specifies the version of Winsock being requested and receives details about the Winsock implementation. Critical for applications that perform network operations including HTTP requests, socket communication, or any TCP/UDP networking.""",
        tokens_used=108,
        response_time_ms=580,
        quality_score=8.9,
        confidence=0.93
    )
]

ANTHROPIC_IMPORT_EXPLANATIONS = [
    MockLLMResponse(
        provider="anthropic",
        model="claude-3-sonnet-20240229",
        content="""**VirtualAlloc** from kernel32.dll is a Windows memory management function that allows applications to reserve or commit virtual memory pages. This function is particularly significant in reverse engineering contexts because it's often used by malware for code injection, shellcode execution, or dynamic code generation. The function can allocate memory with specific protection attributes (read, write, execute), making it a key indicator of potential security-relevant behavior. Legitimate uses include memory pool management, dynamic loading scenarios, and performance optimization through custom memory allocation strategies.""",
        tokens_used=142,
        response_time_ms=850,
        quality_score=9.4,
        confidence=0.95
    )
]

# Overall Summary Examples by Provider
OPENAI_SUMMARIES = [
    MockLLMResponse(
        provider="openai",
        model="gpt-4",
        content="""This appears to be a Windows service application focused on system monitoring and data collection. The program implements a multi-threaded architecture with separate threads for data collection, processing, and network communication. Key functionalities include:

**Primary Purpose**: System performance monitoring with remote reporting capabilities
**Core Behaviors**: 
- Continuous monitoring of system resources (CPU, memory, disk I/O)
- Data aggregation and statistical analysis
- Encrypted transmission of collected data to remote servers
- Configuration management through registry settings

**Security Considerations**: The application uses legitimate Windows APIs but includes network communication capabilities that could potentially be misused for data exfiltration. The encryption implementation appears standard, but the destination servers should be verified.

**Technical Implementation**: Well-structured code with proper error handling and resource management. Uses standard Windows service patterns with appropriate privilege management.""",
        tokens_used=198,
        response_time_ms=1100,
        quality_score=9.1,
        confidence=0.93
    )
]

ANTHROPIC_SUMMARIES = [
    MockLLMResponse(
        provider="anthropic",
        model="claude-3-sonnet-20240229", 
        content="""Based on my analysis of this binary, this appears to be a sophisticated network utility application with both legitimate and potentially concerning capabilities.

**Core Functionality**: The application implements a comprehensive network scanning and monitoring framework. It can perform port scanning, service enumeration, network topology discovery, and maintain persistent connections to remote hosts. The program includes a modular architecture allowing for plugin-based extensibility.

**Key Behavioral Patterns**:
- Advanced network discovery and reconnaissance capabilities
- Encrypted command and control communication protocols
- Dynamic code loading and execution mechanisms
- Sophisticated evasion techniques including process injection and API hooking
- Comprehensive logging and data collection systems

**Security Analysis**: While the technical implementation is sophisticated and well-engineered, the combination of reconnaissance capabilities, encryption, and evasion techniques raises significant security concerns. The application could serve legitimate penetration testing purposes, but the same features make it suitable for malicious reconnaissance and potential attack coordination.

**Recommendation**: This application should be classified as dual-use technology requiring careful evaluation of deployment context and access controls.""",
        tokens_used=267,
        response_time_ms=1500,
        quality_score=9.6,
        confidence=0.97
    )
]

# Error Response Scenarios
ERROR_RESPONSES = {
    "rate_limit": {
        "openai": {
            "error": "Rate limit exceeded",
            "code": "rate_limit_exceeded", 
            "retry_after": 60,
            "tokens_used": 0
        },
        "anthropic": {
            "error": "Too many requests", 
            "code": "rate_limit_error",
            "retry_after": 120,
            "tokens_used": 0
        },
        "gemini": {
            "error": "Quota exceeded",
            "code": "quota_exceeded",
            "retry_after": 90,
            "tokens_used": 0
        }
    },
    "api_key_invalid": {
        "openai": {
            "error": "Invalid API key provided",
            "code": "invalid_api_key",
            "tokens_used": 0
        },
        "anthropic": {
            "error": "Authentication failed",
            "code": "authentication_error", 
            "tokens_used": 0
        },
        "gemini": {
            "error": "API key not valid",
            "code": "invalid_key",
            "tokens_used": 0
        }
    },
    "content_filter": {
        "openai": {
            "error": "Content filtered due to policy violation",
            "code": "content_policy_violation",
            "tokens_used": 15
        },
        "anthropic": {
            "error": "Request blocked by safety filters", 
            "code": "content_blocked",
            "tokens_used": 12
        }
    }
}

# Performance benchmarks for different providers
PROVIDER_PERFORMANCE_PROFILES = {
    "openai": {
        "average_response_time_ms": 750,
        "token_processing_rate": 85,  # tokens per second
        "reliability": 0.97,
        "cost_per_1k_tokens": 0.03
    },
    "anthropic": {
        "average_response_time_ms": 1200,
        "token_processing_rate": 65,
        "reliability": 0.96,
        "cost_per_1k_tokens": 0.025
    },
    "gemini": {
        "average_response_time_ms": 650,
        "token_processing_rate": 95,
        "reliability": 0.94,
        "cost_per_1k_tokens": 0.015
    },
    "ollama": {
        "average_response_time_ms": 2500,
        "token_processing_rate": 25,
        "reliability": 0.92,
        "cost_per_1k_tokens": 0.0  # Local inference
    }
}


def get_mock_response(
    provider: str,
    operation_type: str,
    complexity: str = "medium",
    include_error: bool = False,
    error_type: Optional[str] = None
) -> MockLLMResponse:
    """
    Get a realistic mock response for testing.
    
    Args:
        provider: LLM provider (openai, anthropic, gemini, ollama)
        operation_type: function_translation, import_explanation, overall_summary
        complexity: low, medium, high (affects response length and detail)
        include_error: Whether to return an error response
        error_type: Type of error (rate_limit, api_key_invalid, content_filter)
        
    Returns:
        MockLLMResponse object
    """
    if include_error and error_type:
        error_data = ERROR_RESPONSES.get(error_type, {}).get(provider)
        if error_data:
            return MockLLMResponse(
                provider=provider,
                model="error",
                content=f"ERROR: {error_data['error']}",
                tokens_used=error_data.get("tokens_used", 0),
                response_time_ms=200,
                quality_score=0.0,
                confidence=0.0
            )
    
    # Select response based on provider and operation type
    responses = []
    
    if operation_type == "function_translation":
        if provider == "openai":
            responses = OPENAI_FUNCTION_TRANSLATIONS
        elif provider == "anthropic":
            responses = ANTHROPIC_FUNCTION_TRANSLATIONS
        elif provider == "gemini":
            responses = GEMINI_FUNCTION_TRANSLATIONS
        elif provider == "ollama":
            responses = OLLAMA_FUNCTION_TRANSLATIONS
    elif operation_type == "import_explanation":
        if provider == "openai":
            responses = OPENAI_IMPORT_EXPLANATIONS
        elif provider == "anthropic":
            responses = ANTHROPIC_IMPORT_EXPLANATIONS
    elif operation_type == "overall_summary":
        if provider == "openai":
            responses = OPENAI_SUMMARIES
        elif provider == "anthropic":
            responses = ANTHROPIC_SUMMARIES
    
    if not responses:
        # Generate a generic response
        return MockLLMResponse(
            provider=provider,
            model=f"{provider}-default",
            content=f"This is a {complexity} complexity {operation_type} from {provider}.",
            tokens_used=50,
            response_time_ms=500,
            quality_score=7.0,
            confidence=0.8
        )
    
    # Select random response and adjust for complexity
    response = random.choice(responses)
    
    # Adjust for complexity
    if complexity == "low":
        # Truncate response for low complexity
        words = response.content.split()
        truncated = " ".join(words[:len(words)//2])
        response.content = truncated + "..."
        response.tokens_used = response.tokens_used // 2
        response.response_time_ms = response.response_time_ms // 2
    elif complexity == "high":
        # Extend response for high complexity
        response.content += "\n\nAdditional technical details: This implementation demonstrates advanced software engineering patterns with robust error handling and performance optimizations suitable for production deployment."
        response.tokens_used = int(response.tokens_used * 1.3)
        response.response_time_ms = int(response.response_time_ms * 1.4)
    
    return response


def get_provider_performance(provider: str) -> Dict[str, Any]:
    """Get performance profile for a provider."""
    return PROVIDER_PERFORMANCE_PROFILES.get(provider, PROVIDER_PERFORMANCE_PROFILES["ollama"])


def simulate_provider_latency(provider: str, base_tokens: int = 100) -> int:
    """Simulate realistic response time based on provider and token count."""
    profile = get_provider_performance(provider)
    base_time = profile["average_response_time_ms"]
    processing_time = (base_tokens / profile["token_processing_rate"]) * 1000
    
    # Add realistic variance (±20%)
    variance = random.uniform(0.8, 1.2)
    return int((base_time + processing_time) * variance)


def simulate_provider_reliability(provider: str) -> bool:
    """Simulate provider reliability (success/failure)."""
    profile = get_provider_performance(provider)
    return random.random() < profile["reliability"]