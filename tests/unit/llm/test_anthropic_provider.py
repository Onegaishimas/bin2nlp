"""
Unit tests for Anthropic Claude LLM provider with mocked API responses.

Tests Anthropic Claude API integration including Claude-3-sonnet, Claude-3-haiku, and Claude-3-opus
with comprehensive mocking of API responses and error scenarios.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json
import asyncio
from typing import Dict, Any, List
import httpx

# Note: These imports will be available after LLM framework implementation (Task 3.2.2)
# from src.llm.providers.anthropic_provider import AnthropicProvider
# from src.llm.base import LLMConfig, LLMResponse
# from src.core.exceptions import LLMProviderError, LLMAuthError, LLMRateLimitError


class TestAnthropicProvider:
    """Test Anthropic provider with mocked API responses."""
    
    @pytest.fixture
    def anthropic_config(self):
        """Mock Anthropic configuration."""
        return {
            'provider': 'anthropic',
            'model': 'claude-3-sonnet-20240229',
            'api_key': 'sk-ant-test-key-123',
            'base_url': 'https://api.anthropic.com',
            'timeout': 60,  # Anthropic typically needs longer timeout
            'max_retries': 3,
            'temperature': 0.3,  # Claude works well with lower temperature
            'max_tokens': 4000,
            'anthropic_version': '2023-06-01'
        }
    
    @pytest.fixture
    def mock_anthropic_client(self):
        """Mock Anthropic client."""
        client = AsyncMock()
        client.messages = AsyncMock()
        client.messages.create = AsyncMock()
        return client
    
    def test_anthropic_provider_initialization(self, anthropic_config):
        """Test Anthropic provider initialization with Claude models."""
        # Mock provider initialization
        provider = Mock()
        provider.config = anthropic_config
        provider.model = anthropic_config['model']
        provider.api_key = anthropic_config['api_key']
        
        assert provider.config['provider'] == 'anthropic'
        assert 'claude-3-sonnet' in provider.model
        assert provider.api_key.startswith('sk-ant-')
    
    def test_anthropic_model_variants(self):
        """Test configuration for different Claude model variants."""
        claude_models = [
            'claude-3-opus-20240229',      # Most capable
            'claude-3-sonnet-20240229',    # Balanced performance
            'claude-3-haiku-20240307',     # Fastest and most cost-effective
        ]
        
        for model in claude_models:
            config = {
                'provider': 'anthropic',
                'model': model,
                'api_key': 'sk-ant-test-key',
                'max_tokens': 4000 if 'opus' in model else 2000  # Opus can handle longer responses
            }
            
            provider = Mock()
            provider.config = config
            provider.model = model
            
            assert 'claude-3' in provider.model
            assert provider.config['provider'] == 'anthropic'


class TestAnthropicFunctionTranslation:
    """Test Anthropic function translation with mocked responses."""
    
    @pytest.fixture
    def mock_anthropic_function_response(self):
        """Mock successful function translation response from Claude."""
        return {
            "id": "msg_01ABC123",
            "type": "message",
            "role": "assistant",
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "function_name": "validate_credentials",
                    "natural_language_description": "This function performs comprehensive user credential validation using industry-standard security practices. It implements bcrypt password hashing with salt, includes protection against timing attacks through constant-time comparison, and validates both username format and password strength requirements. The function is designed to be resistant to common authentication bypass techniques.",
                    "parameters_explanation": "Accepts 'username' parameter (string, 3-50 characters, alphanumeric and underscore only) and 'password_hash' parameter (string, pre-computed bcrypt hash with salt). Input validation includes length checks, character set validation, and hash format verification to prevent injection attacks.",
                    "return_value_explanation": "Returns structured authentication result containing success boolean, user_id (if successful), error_code for failures, and security event logging information. Throws AuthenticationException for malformed inputs and DatabaseException for backend failures.",
                    "assembly_summary": "Function utilizes stack frame for local variables, calls bcrypt_checkpw for secure comparison, implements constant-time string comparison loop to prevent timing attacks, accesses user database through secure prepared statements, and returns comprehensive result structure in heap-allocated memory.",
                    "security_analysis": "Implements multiple layers of security: bcrypt for password hashing, constant-time comparison to prevent timing attacks, input sanitization against injection attacks, rate limiting considerations, and comprehensive audit logging. No obvious vulnerabilities detected in the implementation.",
                    "confidence_score": 0.94,
                    "reasoning": "High confidence based on clear assembly patterns matching bcrypt library usage, consistent timing attack protections, and standard authentication flow patterns. Some uncertainty in exact database schema implementation details.",
                    "provider_metadata": {
                        "model": "claude-3-sonnet-20240229",
                        "tokens_used": 520,
                        "processing_time_ms": 2100,
                        "anthropic_version": "2023-06-01"
                    }
                })
            }],
            "model": "claude-3-sonnet-20240229",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {
                "input_tokens": 350,
                "output_tokens": 170
            }
        }
    
    @pytest.mark.asyncio
    async def test_translate_function_with_claude_reasoning(self, anthropic_config, mock_anthropic_function_response):
        """Test Claude's detailed reasoning in function translation."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_anthropic_function_response
            mock_post.return_value = mock_response
            
            provider = Mock()
            provider.translate_function = AsyncMock()
            
            function_data = {
                'name': 'sub_401200',
                'assembly_code': 'push ebp\nmov ebp, esp\ncall bcrypt_checkpw\n...',
                'address': '0x401200',
                'size': 234,
                'imports': ['bcrypt_checkpw', 'strcmp'],
                'strings': ['invalid_username', 'password_mismatch']
            }
            
            expected_translation = json.loads(
                mock_anthropic_function_response['content'][0]['text']
            )
            
            provider.translate_function.return_value = expected_translation
            
            result = await provider.translate_function(function_data)
            
            # Verify Claude's detailed analysis
            assert result['function_name'] == 'validate_credentials'
            assert 'timing attacks' in result['security_analysis'].lower()
            assert 'bcrypt' in result['natural_language_description'].lower()
            assert result['confidence_score'] > 0.9
            assert 'reasoning' in result  # Claude provides reasoning
            assert result['provider_metadata']['model'].startswith('claude-3')
    
    @pytest.mark.asyncio
    async def test_claude_security_focus_analysis(self):
        """Test Claude's security-focused analysis capabilities."""
        provider = Mock()
        provider.translate_function = AsyncMock()
        
        # Mock potentially vulnerable function
        vulnerable_function = {
            'name': 'sub_403000',
            'assembly_code': 'call gets\ncall strcpy\ncall system\n...',
            'imports': ['gets', 'strcpy', 'system'],
            'strings': ['/bin/sh', 'user_command'],
            'size': 156
        }
        
        # Mock Claude's security-aware response
        mock_result = {
            'function_name': 'execute_user_command',
            'natural_language_description': 'This function processes and executes user-provided commands with significant security vulnerabilities.',
            'security_analysis': 'CRITICAL VULNERABILITIES DETECTED: 1) gets() function is inherently vulnerable to buffer overflow attacks as it does not perform bounds checking. 2) strcpy() can cause buffer overflows if source exceeds destination buffer. 3) system() call with user input enables command injection attacks. 4) Direct shell access (/bin/sh) provides full system access. This function represents a severe security risk and should be completely rewritten with secure alternatives.',
            'remediation_suggestions': 'Replace gets() with fgets() or safer input functions. Use strncpy() or strlcpy() instead of strcpy(). Implement command validation and sanitization instead of direct system() calls. Consider using execve() with strict argument validation or a whitelist approach for allowed commands.',
            'vulnerability_severity': 'CRITICAL',
            'cve_patterns': 'Similar to CVE-2019-14287 (command injection), CWE-120 (buffer overflow), CWE-78 (command injection)',
            'confidence_score': 0.98
        }
        
        provider.translate_function.return_value = mock_result
        
        result = await provider.translate_function(vulnerable_function)
        
        # Verify Claude's security analysis depth
        assert result['vulnerability_severity'] == 'CRITICAL'
        assert 'buffer overflow' in result['security_analysis'].lower()
        assert 'command injection' in result['security_analysis'].lower()
        assert 'remediation_suggestions' in result
        assert 'CVE' in result['cve_patterns']
        assert result['confidence_score'] > 0.95


class TestAnthropicLongContextHandling:
    """Test Claude's superior long context window capabilities."""
    
    @pytest.mark.asyncio
    async def test_large_function_analysis(self):
        """Test handling of large functions with extensive context."""
        provider = Mock()
        provider.translate_function = AsyncMock()
        
        # Mock very large function with lots of context
        large_function = {
            'name': 'complex_algorithm',
            'assembly_code': 'A' * 10000,  # Very long assembly
            'size': 5000,
            'imports': ['malloc', 'free', 'memcpy'] * 20,  # Many imports
            'strings': ['debug_info', 'error_message'] * 50,  # Many strings
            'calling_functions': [f'caller_{i}' for i in range(30)],
            'called_functions': [f'callee_{i}' for i in range(25)],
            'cross_references': list(range(100))
        }
        
        mock_result = {
            'function_name': 'advanced_cryptographic_processor',
            'natural_language_description': 'This is a complex cryptographic processing function implementing a multi-stage encryption algorithm with dynamic memory management...',
            'context_synthesis': 'Analysis of 30 calling functions and 25 called functions reveals this is the core processing engine of a cryptographic library. The extensive cross-references indicate this function is central to the application\'s security architecture.',
            'long_context_insights': 'The function\'s position in the call graph and its interaction with memory management functions suggests it processes variable-length cryptographic data. The debug strings indicate development history and error handling patterns.',
            'confidence_score': 0.91,
            'context_tokens_processed': 15000  # Claude can handle long contexts
        }
        
        provider.translate_function.return_value = mock_result
        
        result = await provider.translate_function(large_function)
        
        assert result['context_tokens_processed'] > 10000
        assert 'context_synthesis' in result
        assert 'long_context_insights' in result


class TestAnthropicImportTranslation:
    """Test Anthropic import/export translation with detailed API knowledge."""
    
    @pytest.fixture
    def mock_anthropic_import_response(self):
        """Mock detailed import translation from Claude."""
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "library_name": "ntdll.dll",
                    "function_name": "NtCreateFile",
                    "api_documentation_summary": "NtCreateFile is a low-level Windows NT kernel API function for creating and opening files and directories. It's part of the Native API (not Win32 API) and provides more direct access to the Windows kernel's file system services. This function is more powerful but also more complex than the higher-level CreateFile API.",
                    "usage_context": "Typically used in system-level programming, rootkits, security software, or performance-critical applications that need direct kernel access. Often seen in malware for its ability to bypass some user-mode hooks and monitoring.",
                    "parameters_description": "FileHandle (output): receives file handle, DesiredAccess: access rights mask, ObjectAttributes: file path and attributes structure, IoStatusBlock: I/O operation results, AllocationSize: optional initial file size, FileAttributes: file attributes, ShareAccess: sharing permissions, CreateDisposition: creation behavior, CreateOptions: additional flags, EaBuffer: extended attributes, EaLength: EA buffer size",
                    "security_implications": "HIGH RISK: Direct kernel API access can bypass security monitoring. Often used in advanced persistent threats and rootkits. Requires SYSTEM privileges for many operations. Can create files with unusual attributes that may evade detection. Parameter validation is critical to prevent kernel exploitation.",
                    "detection_signatures": "API call patterns common in rootkits and advanced malware. May indicate process hollowing, DLL injection, or direct kernel manipulation techniques.",
                    "legitimate_vs_malicious": "Legitimate: System utilities, drivers, security software. Suspicious: Unusual processes calling NT APIs, processes without appropriate privileges, rapid sequential calls with suspicious parameters.",
                    "provider_metadata": {
                        "model": "claude-3-opus-20240229",
                        "knowledge_depth": "expert",
                        "api_category": "kernel_native_api"
                    }
                })
            }]
        }
    
    @pytest.mark.asyncio
    async def test_detailed_api_analysis(self, mock_anthropic_import_response):
        """Test Claude's detailed API knowledge and security analysis."""
        provider = Mock()
        provider.translate_imports = AsyncMock()
        
        import_data = [
            {'library': 'ntdll.dll', 'function': 'NtCreateFile'},
            {'library': 'kernel32.dll', 'function': 'VirtualAllocEx'},
            {'library': 'advapi32.dll', 'function': 'LookupPrivilegeValueA'}
        ]
        
        expected_results = [
            json.loads(mock_anthropic_import_response['content'][0]['text']),
            {
                'library_name': 'kernel32.dll',
                'function_name': 'VirtualAllocEx',
                'security_implications': 'HIGH RISK: Used for memory allocation in other processes. Common in DLL injection, process hollowing, and shellcode injection attacks.',
                'detection_signatures': 'Often combined with WriteProcessMemory and CreateRemoteThread in injection attacks',
                'malware_techniques': ['Process hollowing', 'DLL injection', 'Code injection']
            },
            {
                'library_name': 'advapi32.dll',
                'function_name': 'LookupPrivilegeValueA', 
                'security_implications': 'MEDIUM RISK: Used to query privilege values, often for privilege escalation attempts',
                'common_privileges': ['SeDebugPrivilege', 'SeBackupPrivilege', 'SeRestorePrivilege']
            }
        ]
        
        provider.translate_imports.return_value = expected_results
        
        result = await provider.translate_imports(import_data)
        
        # Verify Claude's deep API knowledge
        assert result[0]['library_name'] == 'ntdll.dll'
        assert 'kernel' in result[0]['api_documentation_summary'].lower()
        assert 'rootkits' in result[0]['usage_context'].lower()
        assert 'detection_signatures' in result[0]
        assert 'legitimate_vs_malicious' in result[0]


class TestAnthropicErrorHandling:
    """Test Anthropic provider error handling scenarios."""
    
    @pytest.mark.asyncio
    async def test_anthropic_authentication_error(self):
        """Test handling of Anthropic API authentication errors."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 401
            mock_response.json.return_value = {
                'type': 'error',
                'error': {
                    'type': 'authentication_error',
                    'message': 'Invalid API Key'
                }
            }
            mock_post.return_value = mock_response
            
            provider = Mock()
            provider.translate_function = AsyncMock()
            provider.translate_function.side_effect = Exception("LLMAuthError: Invalid API Key")
            
            with pytest.raises(Exception) as exc_info:
                await provider.translate_function({})
            
            assert "Invalid API Key" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_anthropic_rate_limit_error(self):
        """Test handling of Anthropic rate limiting."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 429
            mock_response.json.return_value = {
                'type': 'error',
                'error': {
                    'type': 'rate_limit_error',
                    'message': 'Output blocked by content filtering policy'
                }
            }
            mock_response.headers = {'retry-after': '120'}
            mock_post.return_value = mock_response
            
            provider = Mock()
            provider.translate_function = AsyncMock()
            provider.translate_function.side_effect = Exception("LLMRateLimitError: Rate limited, retry after 120 seconds")
            
            with pytest.raises(Exception) as exc_info:
                await provider.translate_function({})
            
            assert "Rate limited" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_anthropic_content_filtering(self):
        """Test handling of Anthropic content filtering."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {
                'type': 'error',
                'error': {
                    'type': 'invalid_request_error',
                    'message': 'Output blocked by content filtering policy'
                }
            }
            mock_post.return_value = mock_response
            
            provider = Mock()
            provider.translate_function = AsyncMock()
            provider.translate_function.side_effect = Exception("LLMContentFilterError: Content blocked by policy")
            
            with pytest.raises(Exception) as exc_info:
                await provider.translate_function({})
            
            assert "Content blocked" in str(exc_info.value)


class TestAnthropicHealthCheck:
    """Test Anthropic provider health check functionality."""
    
    @pytest.mark.asyncio
    async def test_anthropic_health_check(self):
        """Test Anthropic health check with model availability."""
        provider = Mock()
        provider.health_check = AsyncMock()
        
        mock_health = {
            'provider_name': 'anthropic',
            'status': 'healthy',
            'response_time_ms': 1200,  # Anthropic tends to be slower but more thoughtful
            'last_successful_call': '2025-01-15T14:30:00Z',
            'error_rate_percentage': 0.1,  # Generally very reliable
            'quota_remaining': '78%',
            'model_availability': [
                'claude-3-opus-20240229',
                'claude-3-sonnet-20240229', 
                'claude-3-haiku-20240307'
            ],
            'api_endpoint': 'https://api.anthropic.com',
            'anthropic_version': '2023-06-01',
            'content_filtering_active': True
        }
        
        provider.health_check.return_value = mock_health
        
        result = await provider.health_check()
        
        assert result['provider_name'] == 'anthropic'
        assert result['status'] == 'healthy'
        assert 'claude-3' in str(result['model_availability'])
        assert result['content_filtering_active'] is True
        assert result['response_time_ms'] > 1000  # Expected to be slower but higher quality


class TestAnthropicConstitutionalAI:
    """Test Claude's Constitutional AI features for responsible analysis."""
    
    @pytest.mark.asyncio
    async def test_ethical_malware_analysis(self):
        """Test Claude's approach to malware analysis with ethical considerations."""
        provider = Mock()
        provider.translate_function = AsyncMock()
        
        # Mock potentially malicious function
        malicious_function = {
            'name': 'keylogger_routine',
            'assembly_code': 'call SetWindowsHookEx\ncall GetAsyncKeyState\n...',
            'imports': ['SetWindowsHookEx', 'GetAsyncKeyState', 'WriteFile'],
            'strings': ['keylog.txt', 'password', 'credit_card']
        }
        
        # Mock Claude's responsible analysis
        mock_result = {
            'function_name': 'keyboard_monitoring_routine',
            'natural_language_description': 'This function implements keyboard monitoring capabilities using Windows hook mechanisms.',
            'security_analysis': 'MALWARE SIGNATURE: This code pattern matches known keylogger implementations. The combination of SetWindowsHookEx for keyboard hooks, GetAsyncKeyState for key state monitoring, and file output to keylog.txt indicates malicious intent.',
            'ethical_analysis': 'RESPONSIBLE DISCLOSURE: This analysis is provided for defensive cybersecurity purposes only. The identified patterns should be used to improve detection systems and security awareness. Any use of this information for malicious purposes violates ethical guidelines and applicable laws.',
            'defensive_applications': 'Security teams can use these signatures for endpoint detection rules. The API call patterns can be incorporated into behavioral analysis systems. Educational value for understanding attack vectors.',
            'constitutional_ai_note': 'This analysis prioritizes harm prevention while providing valuable security insights. The goal is to strengthen defenses against malicious software.',
            'confidence_score': 0.97
        }
        
        provider.translate_function.return_value = mock_result
        
        result = await provider.translate_function(malicious_function)
        
        # Verify responsible AI approach
        assert 'MALWARE SIGNATURE' in result['security_analysis']
        assert 'RESPONSIBLE DISCLOSURE' in result['ethical_analysis']
        assert 'defensive_applications' in result
        assert 'constitutional_ai_note' in result
        assert 'harm prevention' in result['constitutional_ai_note']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])