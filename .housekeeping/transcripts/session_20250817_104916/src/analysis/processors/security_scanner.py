"""
Security pattern detection scanner for binary analysis.

Provides comprehensive security pattern detection including network operations,
file system access, suspicious behavior patterns, and anti-analysis techniques.
"""

import re
import asyncio
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

from ..engines.r2_integration import R2Session, R2SessionException
from ...models.shared.enums import AnalysisDepth, Platform
from ...core.logging import get_logger
from ...core.exceptions import BinaryAnalysisException


logger = get_logger(__name__)


class SecurityRiskLevel(Enum):
    """Security risk assessment levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PatternCategory(Enum):
    """Security pattern categories."""
    NETWORK = "network"
    FILE_SYSTEM = "file_system"
    REGISTRY = "registry"
    PROCESS = "process"
    CRYPTO = "crypto"
    ANTI_ANALYSIS = "anti_analysis"
    PERSISTENCE = "persistence"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_THEFT = "data_theft"
    SYSTEM_MODIFICATION = "system_modification"


@dataclass
class SecurityPattern:
    """Individual security pattern detection."""
    category: PatternCategory
    name: str
    description: str
    risk_level: SecurityRiskLevel
    confidence: float  # 0.0 to 1.0
    
    # Pattern matching information
    pattern_type: str  # "function", "string", "instruction", "syscall"
    matched_content: List[str] = field(default_factory=list)
    locations: List[int] = field(default_factory=list)  # Addresses where found
    
    # Context information
    function_context: Optional[str] = None
    instruction_context: Optional[str] = None
    
    # Additional metadata
    mitigation_advice: Optional[str] = None
    references: List[str] = field(default_factory=list)


@dataclass
class SecurityFindings:
    """Complete security analysis results."""
    patterns: List[SecurityPattern]
    analysis_depth: AnalysisDepth
    analysis_time: float
    
    # Summary statistics
    total_patterns: int = 0
    risk_distribution: Dict[SecurityRiskLevel, int] = field(default_factory=dict)
    category_distribution: Dict[PatternCategory, int] = field(default_factory=dict)
    
    # Overall assessment
    overall_risk_score: float = 0.0  # 0.0 to 100.0
    is_malicious: bool = False
    is_suspicious: bool = False
    
    # Recommendations
    security_recommendations: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Calculate summary statistics."""
        self.total_patterns = len(self.patterns)
        
        # Initialize distributions
        self.risk_distribution = {level: 0 for level in SecurityRiskLevel}
        self.category_distribution = {cat: 0 for cat in PatternCategory}
        
        # Count patterns by risk and category
        for pattern in self.patterns:
            self.risk_distribution[pattern.risk_level] += 1
            self.category_distribution[pattern.category] += 1
        
        # Calculate overall risk score
        self._calculate_risk_score()
        
        # Generate recommendations
        self._generate_recommendations()
    
    def _calculate_risk_score(self) -> None:
        """Calculate overall risk score based on patterns."""
        if not self.patterns:
            self.overall_risk_score = 0.0
            return
        
        risk_weights = {
            SecurityRiskLevel.LOW: 1.0,
            SecurityRiskLevel.MEDIUM: 3.0,
            SecurityRiskLevel.HIGH: 7.0,
            SecurityRiskLevel.CRITICAL: 15.0
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for pattern in self.patterns:
            weight = risk_weights[pattern.risk_level]
            score = pattern.confidence * weight
            total_score += score
            total_weight += weight
        
        if total_weight > 0:
            self.overall_risk_score = min((total_score / total_weight) * 10, 100.0)
        
        # Set flags based on score and pattern distribution
        self.is_suspicious = self.overall_risk_score > 30.0
        self.is_malicious = (
            self.overall_risk_score > 70.0 or
            self.risk_distribution[SecurityRiskLevel.CRITICAL] > 0 or
            self.risk_distribution[SecurityRiskLevel.HIGH] >= 3
        )
    
    def _generate_recommendations(self) -> None:
        """Generate security recommendations based on findings."""
        self.security_recommendations = []
        
        if self.is_malicious:
            self.security_recommendations.append(
                "CRITICAL: This binary shows strong indicators of malicious activity. "
                "Do not execute in production environment."
            )
        
        if self.is_suspicious:
            self.security_recommendations.append(
                "WARNING: This binary exhibits suspicious behavior patterns. "
                "Execute only in sandboxed environment."
            )
        
        # Category-specific recommendations
        if self.category_distribution[PatternCategory.NETWORK] > 0:
            self.security_recommendations.append(
                "Monitor network traffic if executing this binary."
            )
        
        if self.category_distribution[PatternCategory.FILE_SYSTEM] > 0:
            self.security_recommendations.append(
                "Monitor file system changes during execution."
            )
        
        if self.category_distribution[PatternCategory.ANTI_ANALYSIS] > 0:
            self.security_recommendations.append(
                "Binary contains anti-analysis techniques. Dynamic analysis recommended."
            )


class SecurityScanner:
    """
    Comprehensive security pattern scanner for binary analysis.
    
    Detects various security-related patterns including:
    - Network operations (sockets, HTTP, DNS)
    - File system operations (file I/O, directory traversal)
    - Registry access and modification
    - Process manipulation and injection
    - Cryptographic operations
    - Anti-analysis and evasion techniques
    - Persistence mechanisms
    - Privilege escalation attempts
    """
    
    # Comprehensive security pattern definitions
    SECURITY_PATTERNS = {
        PatternCategory.NETWORK: {
            'function_patterns': [
                # Socket operations
                {
                    'patterns': [r'socket', r'bind', r'listen', r'accept', r'connect', 
                               r'send', r'recv', r'sendto', r'recvfrom', r'WSASocket', 
                               r'WSAConnect', r'WSASend', r'WSARecv', r'closesocket',
                               r'shutdown', r'select', r'poll', r'epoll'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'Network socket operations detected'
                },
                # HTTP operations
                {
                    'patterns': [r'HttpOpenRequest', r'HttpSendRequest', r'InternetOpen', 
                               r'InternetConnect', r'InternetReadFile', r'WinHttpOpen',
                               r'WinHttpConnect', r'WinHttpOpenRequest', r'curl_easy_init',
                               r'wget', r'urllib', r'URLDownloadToFile', r'InternetOpenUrl'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'HTTP/web communication detected'
                },
                # DNS operations
                {
                    'patterns': [r'gethostbyname', r'getaddrinfo', r'DnsQuery', 
                               r'DnsQueryEx', r'res_query', r'nslookup', r'gethostbyaddr'],
                    'risk_level': SecurityRiskLevel.LOW,
                    'description': 'DNS resolution operations detected'
                },
                # High-risk network operations
                {
                    'patterns': [r'bind_shell', r'reverse_shell', r'backdoor', r'C2',
                               r'command_control', r'beacon', r'exfiltrate'],
                    'risk_level': SecurityRiskLevel.CRITICAL,
                    'description': 'Malicious network communication patterns detected'
                },
                # Network scanning/reconnaissance
                {
                    'patterns': [r'portscan', r'nmap', r'ping', r'traceroute', r'netstat',
                               r'arp', r'ifconfig', r'ipconfig'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Network reconnaissance operations detected'
                }
            ],
            'string_patterns': [
                # URLs and network addresses
                {
                    'patterns': [r'https?://[^\s]+', r'ftp://[^\s]+', r'\d+\.\d+\.\d+\.\d+:\d+',
                               r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}:\d+'],
                    'risk_level': SecurityRiskLevel.LOW,
                    'description': 'Network URLs or IP addresses found'
                },
                # Suspicious network strings
                {
                    'patterns': [r'User-Agent:', r'POST\s+/', r'GET\s+/', r'HTTP/1\.[01]',
                               r'Content-Type:', r'Authorization:', r'Cookie:'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'HTTP headers or protocol strings found'
                },
                # Known malicious domains/IPs (examples)
                {
                    'patterns': [r'\.onion', r'dyndns\.org', r'no-ip\.org', r'pastebin\.com'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Potentially suspicious domain patterns found'
                }
            ],
            'syscall_patterns': [
                {
                    'patterns': [r'sys_socket', r'sys_connect', r'sys_sendto', r'sys_recvfrom'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'Direct network system calls detected'
                }
            ]
        },
        
        PatternCategory.FILE_SYSTEM: {
            'function_patterns': [
                # Basic file operations
                {
                    'patterns': [r'CreateFile', r'OpenFile', r'ReadFile', r'WriteFile', 
                               r'CopyFile', r'MoveFile', r'DeleteFile', r'FindFirstFile',
                               r'open', r'fopen', r'read', r'write', r'unlink', r'rename',
                               r'fread', r'fwrite', r'fseek', r'ftell', r'fclose'],
                    'risk_level': SecurityRiskLevel.LOW,
                    'description': 'File system operations detected'
                },
                # Directory operations
                {
                    'patterns': [r'CreateDirectory', r'RemoveDirectory', r'GetCurrentDirectory',
                               r'SetCurrentDirectory', r'mkdir', r'rmdir', r'opendir', 
                               r'readdir', r'chdir', r'FindFirstFile', r'FindNextFile'],
                    'risk_level': SecurityRiskLevel.LOW,
                    'description': 'Directory operations detected'
                },
                # File attribute manipulation
                {
                    'patterns': [r'SetFileAttributes', r'SetFileTime', r'GetFileAttributes',
                               r'chmod', r'chown', r'chgrp', r'stat', r'lstat', r'utime'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'File attribute manipulation detected'
                },
                # Temporary and system file access
                {
                    'patterns': [r'GetTempPath', r'GetTempFileName', r'GetSystemDirectory',
                               r'GetWindowsDirectory', r'SHGetFolderPath', r'tempfile',
                               r'mktemp', r'mkstemp'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'Temporary or system file access detected'
                },
                # High-risk file operations
                {
                    'patterns': [r'SHFileOperation', r'IFileOperation', r'MoveFileEx',
                               r'DeleteFileA', r'DeleteFileW', r'ReplaceFile',
                               r'shred', r'wipe', r'secure_delete'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Advanced file manipulation operations detected'
                },
                # File monitoring and watching
                {
                    'patterns': [r'ReadDirectoryChanges', r'FindFirstChangeNotification',
                               r'inotify_init', r'inotify_add_watch', r'kqueue', r'watch'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'File system monitoring operations detected'
                },
                # Archive and compression operations
                {
                    'patterns': [r'zip', r'unzip', r'gzip', r'gunzip', r'tar', r'rar',
                               r'compress', r'decompress', r'extract'],
                    'risk_level': SecurityRiskLevel.LOW,
                    'description': 'Archive/compression operations detected'
                }
            ],
            'string_patterns': [
                # File paths and directories
                {
                    'patterns': [r'[A-Za-z]:\\\\[^\\s]+', r'/[a-zA-Z0-9/_.-]+', r'\./[^\\s]+',
                               r'../[^\\s]+'],
                    'risk_level': SecurityRiskLevel.LOW,
                    'description': 'File paths found'
                },
                # Environment variables and system paths
                {
                    'patterns': [r'%TEMP%', r'%APPDATA%', r'%USERPROFILE%', r'%SYSTEMROOT%',
                               r'%PROGRAMFILES%', r'$HOME', r'$TEMP', r'/tmp/', r'/var/',
                               r'/etc/', r'/usr/bin/', r'/opt/'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'System environment variables or sensitive paths found'
                },
                # Executable and suspicious file extensions
                {
                    'patterns': [r'\.exe\b', r'\.dll\b', r'\.bat\b', r'\.cmd\b', r'\.scr\b',
                               r'\.pif\b', r'\.com\b', r'\.vbs\b', r'\.ps1\b', r'\.sh\b',
                               r'\.py\b', r'\.pl\b'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'Executable file extensions found'
                },
                # Log and configuration files
                {
                    'patterns': [r'\.log\b', r'\.cfg\b', r'\.conf\b', r'\.ini\b', r'\.xml\b',
                               r'\.json\b', r'\.yaml\b', r'\.yml\b'],
                    'risk_level': SecurityRiskLevel.LOW,
                    'description': 'Configuration or log file references found'
                },
                # Suspicious file operations patterns
                {
                    'patterns': [r'shadow', r'passwd', r'hosts', r'resolv\.conf', r'sudoers',
                               r'authorized_keys', r'known_hosts'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Critical system file references found'
                }
            ]
        },
        
        PatternCategory.REGISTRY: {
            'function_patterns': [
                {
                    'patterns': [r'RegOpenKey', r'RegQueryValue', r'RegSetValue', 
                               r'RegCreateKey', r'RegDeleteKey', r'RegDeleteValue',
                               r'RegCloseKey', r'RegEnumKey', r'RegEnumValue'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'Windows registry operations detected'
                }
            ],
            'string_patterns': [
                {
                    'patterns': [r'HKEY_[A-Z_]+\\\\[^\\s]*', r'SOFTWARE\\\\', r'SYSTEM\\\\',
                               r'Run\\\\', r'RunOnce\\\\', r'Winlogon\\\\'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Registry keys for persistence or system modification found'
                }
            ]
        },
        
        PatternCategory.PROCESS: {
            'function_patterns': [
                # Basic process creation
                {
                    'patterns': [r'CreateProcess', r'WinExec', r'ShellExecute', r'ShellExecuteEx',
                               r'system', r'exec', r'execv', r'execl', r'fork', r'spawn', r'popen',
                               r'CreateProcessAsUser', r'CreateProcessWithToken'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'Process creation operations detected'
                },
                # Process injection techniques
                {
                    'patterns': [r'OpenProcess', r'VirtualAllocEx', r'WriteProcessMemory',
                               r'CreateRemoteThread', r'SetWindowsHookEx', r'NtCreateThread',
                               r'RtlCreateUserThread', r'NtMapViewOfSection', r'ZwMapViewOfSection',
                               r'QueueUserAPC', r'NtQueueApcThread'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Process injection techniques detected'
                },
                # Advanced injection methods
                {
                    'patterns': [r'SetThreadContext', r'GetThreadContext', r'SuspendThread',
                               r'ResumeThread', r'NtUnmapViewOfSection', r'VirtualProtectEx',
                               r'FlushInstructionCache'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Advanced process manipulation detected'
                },
                # Process debugging and analysis
                {
                    'patterns': [r'DebugActiveProcess', r'WaitForDebugEvent', r'ContinueDebugEvent',
                               r'DebugSetProcessKillOnExit', r'ptrace', r'waitpid', r'kill',
                               r'IsDebuggerPresent', r'CheckRemoteDebuggerPresent'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Process debugging/manipulation detected'
                },
                # Process enumeration and information gathering
                {
                    'patterns': [r'EnumProcesses', r'Process32First', r'Process32Next',
                               r'OpenProcessToken', r'GetTokenInformation', r'CreateToolhelp32Snapshot',
                               r'NtQueryInformationProcess', r'NtQuerySystemInformation'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'Process enumeration and information gathering detected'
                },
                # Memory manipulation
                {
                    'patterns': [r'VirtualAlloc', r'VirtualFree', r'VirtualProtect', r'HeapAlloc',
                               r'HeapFree', r'malloc', r'calloc', r'realloc', r'free',
                               r'mmap', r'munmap', r'mprotect'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'Memory allocation and manipulation detected'
                },
                # DLL injection and loading
                {
                    'patterns': [r'LoadLibrary', r'LoadLibraryEx', r'GetProcAddress', r'FreeLibrary',
                               r'LdrLoadDll', r'LdrGetDllHandle', r'dlopen', r'dlsym', r'dlclose'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'Dynamic library loading operations detected'
                },
                # Thread manipulation
                {
                    'patterns': [r'CreateThread', r'ExitThread', r'TerminateThread', r'GetExitCodeThread',
                               r'WaitForSingleObject', r'WaitForMultipleObjects', r'pthread_create',
                               r'pthread_join', r'pthread_exit'],
                    'risk_level': SecurityRiskLevel.LOW,
                    'description': 'Thread management operations detected'
                },
                # Privilege escalation
                {
                    'patterns': [r'AdjustTokenPrivileges', r'LookupPrivilegeValue', r'OpenProcessToken',
                               r'ImpersonateLoggedOnUser', r'RevertToSelf', r'SetTokenInformation',
                               r'sudo', r'su', r'setuid', r'seteuid', r'setgid', r'setegid'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Privilege escalation operations detected'
                }
            ],
            'string_patterns': [
                # Shellcode and injection indicators
                {
                    'patterns': [r'shellcode', r'payload', r'inject', r'meterpreter', r'cobalt',
                               r'beacon', r'stager', r'dropper'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Shellcode or injection-related strings found'
                },
                # Process names and paths
                {
                    'patterns': [r'cmd\.exe', r'powershell\.exe', r'explorer\.exe', r'svchost\.exe',
                               r'winlogon\.exe', r'lsass\.exe', r'csrss\.exe'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'System process references found'
                }
            ]
        },
        
        PatternCategory.CRYPTO: {
            'function_patterns': [
                {
                    'patterns': [r'CryptAcquireContext', r'CryptCreateHash', r'CryptEncrypt',
                               r'CryptDecrypt', r'CryptGenKey', r'encrypt', r'decrypt',
                               r'AES_', r'DES_', r'RSA_', r'MD5', r'SHA', r'Base64'],
                    'risk_level': SecurityRiskLevel.LOW,
                    'description': 'Cryptographic operations detected'
                }
            ],
            'string_patterns': [
                {
                    'patterns': [r'[A-Za-z0-9+/]{20,}={0,2}', r'[0-9a-fA-F]{32,}'],
                    'risk_level': SecurityRiskLevel.LOW,
                    'description': 'Encoded data or cryptographic material found'
                }
            ]
        },
        
        PatternCategory.ANTI_ANALYSIS: {
            'function_patterns': [
                {
                    'patterns': [r'IsDebuggerPresent', r'CheckRemoteDebuggerPresent', 
                               r'NtQueryInformationProcess', r'GetTickCount', r'Sleep',
                               r'anti', r'detect', r'check', r'vm', r'sandbox'],
                    'risk_level': SecurityRiskLevel.HIGH,
                    'description': 'Anti-analysis or evasion techniques detected'
                }
            ],
            'instruction_patterns': [
                {
                    'patterns': [r'rdtsc', r'cpuid', r'int\s+3', r'int\s+2d'],
                    'risk_level': SecurityRiskLevel.MEDIUM,
                    'description': 'Anti-debugging instructions detected'
                }
            ]
        }
    }
    
    def __init__(self, platform: Platform = Platform.UNKNOWN):
        """
        Initialize security scanner.
        
        Args:
            platform: Target platform for platform-specific analysis
        """
        self.platform = platform
        self.logger = logger.bind(component="security_scanner")
    
    async def scan_security_patterns(
        self,
        r2_session: R2Session,
        analysis_depth: AnalysisDepth = AnalysisDepth.STANDARD,
        focus_categories: Optional[List[PatternCategory]] = None
    ) -> SecurityFindings:
        """
        Perform comprehensive security pattern analysis.
        
        Args:
            r2_session: Active radare2 session
            analysis_depth: Depth of analysis to perform
            focus_categories: Specific categories to focus on (None for all)
            
        Returns:
            Complete security analysis results
        """
        start_time = asyncio.get_event_loop().time()
        
        self.logger.info(
            "Starting security pattern analysis",
            depth=analysis_depth.value,
            platform=self.platform.value,
            focus_categories=[cat.value for cat in focus_categories] if focus_categories else "all"
        )
        
        detected_patterns = []
        
        try:
            # Determine which categories to scan
            categories_to_scan = focus_categories or list(PatternCategory)
            
            for category in categories_to_scan:
                self.logger.debug(f"Scanning category: {category.value}")
                
                category_patterns = await self._scan_category(
                    r2_session, category, analysis_depth
                )
                detected_patterns.extend(category_patterns)
                
                # Progress logging
                progress = (categories_to_scan.index(category) + 1) / len(categories_to_scan) * 100
                self.logger.debug(
                    "Security scan progress",
                    category=category.value,
                    patterns_found=len(category_patterns),
                    progress=round(progress, 1)
                )
            
            analysis_time = asyncio.get_event_loop().time() - start_time
            
            findings = SecurityFindings(
                patterns=detected_patterns,
                analysis_depth=analysis_depth,
                analysis_time=analysis_time
            )
            
            self.logger.info(
                "Security pattern analysis completed",
                total_patterns=findings.total_patterns,
                overall_risk_score=findings.overall_risk_score,
                is_suspicious=findings.is_suspicious,
                is_malicious=findings.is_malicious,
                analysis_time=analysis_time
            )
            
            return findings
            
        except Exception as e:
            self.logger.error(
                "Security pattern analysis failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise BinaryAnalysisException(f"Security pattern analysis failed: {e}")
    
    async def _scan_category(
        self,
        r2_session: R2Session,
        category: PatternCategory,
        analysis_depth: AnalysisDepth
    ) -> List[SecurityPattern]:
        """Scan for patterns in a specific category."""
        patterns = []
        
        if category not in self.SECURITY_PATTERNS:
            return patterns
        
        category_config = self.SECURITY_PATTERNS[category]
        
        # Scan function patterns
        if 'function_patterns' in category_config:
            function_patterns = await self._scan_function_patterns(
                r2_session, category, category_config['function_patterns']
            )
            patterns.extend(function_patterns)
        
        # Scan string patterns
        if 'string_patterns' in category_config:
            string_patterns = await self._scan_string_patterns(
                r2_session, category, category_config['string_patterns']
            )
            patterns.extend(string_patterns)
        
        # Scan instruction patterns
        if 'instruction_patterns' in category_config:
            instruction_patterns = await self._scan_instruction_patterns(
                r2_session, category, category_config['instruction_patterns']
            )
            patterns.extend(instruction_patterns)
        
        # Scan syscall patterns
        if 'syscall_patterns' in category_config:
            syscall_patterns = await self._scan_syscall_patterns(
                r2_session, category, category_config['syscall_patterns']
            )
            patterns.extend(syscall_patterns)
        
        return patterns
    
    async def _scan_function_patterns(
        self,
        r2_session: R2Session,
        category: PatternCategory,
        pattern_configs: List[Dict[str, Any]]
    ) -> List[SecurityPattern]:
        """Scan for function-based security patterns."""
        patterns = []
        
        try:
            # Get all functions
            functions_result = await r2_session.execute_command("aflj")
            if not functions_result.success or not functions_result.output:
                return patterns
            
            functions = functions_result.output
            
            for config in pattern_configs:
                for pattern_regex in config['patterns']:
                    for func in functions:
                        func_name = func.get('name', '').lower()
                        
                        if re.search(pattern_regex, func_name, re.IGNORECASE):
                            security_pattern = SecurityPattern(
                                category=category,
                                name=pattern_regex,
                                description=config['description'],
                                risk_level=config['risk_level'],
                                confidence=0.8,  # High confidence for function name matches
                                pattern_type="function",
                                matched_content=[func_name],
                                locations=[func.get('offset', 0)],
                                function_context=func_name
                            )
                            patterns.append(security_pattern)
            
        except Exception as e:
            self.logger.warning(
                "Error scanning function patterns",
                category=category.value,
                error=str(e)
            )
        
        return patterns
    
    async def _scan_string_patterns(
        self,
        r2_session: R2Session,
        category: PatternCategory,
        pattern_configs: List[Dict[str, Any]]
    ) -> List[SecurityPattern]:
        """Scan for string-based security patterns."""
        patterns = []
        
        try:
            # Get all strings from binary
            strings_result = await r2_session.execute_command("izzj")
            if not strings_result.success or not strings_result.output:
                return patterns
            
            strings = strings_result.output
            
            for config in pattern_configs:
                for pattern_regex in config['patterns']:
                    for string_obj in strings:
                        string_content = string_obj.get('string', '')
                        
                        if re.search(pattern_regex, string_content, re.IGNORECASE):
                            security_pattern = SecurityPattern(
                                category=category,
                                name=pattern_regex,
                                description=config['description'],
                                risk_level=config['risk_level'],
                                confidence=0.6,  # Medium confidence for string matches
                                pattern_type="string",
                                matched_content=[string_content],
                                locations=[string_obj.get('vaddr', 0)]
                            )
                            patterns.append(security_pattern)
            
        except Exception as e:
            self.logger.warning(
                "Error scanning string patterns",
                category=category.value,
                error=str(e)
            )
        
        return patterns
    
    async def _scan_instruction_patterns(
        self,
        r2_session: R2Session,
        category: PatternCategory,
        pattern_configs: List[Dict[str, Any]]
    ) -> List[SecurityPattern]:
        """Scan for instruction-based security patterns."""
        patterns = []
        
        try:
            # Get disassembly for main functions (entry points)
            entry_result = await r2_session.execute_command("iej")
            if not entry_result.success or not entry_result.output:
                return patterns
            
            entries = entry_result.output
            
            for entry in entries[:5]:  # Limit to first 5 entry points
                address = entry.get('vaddr', 0)
                if address == 0:
                    continue
                
                # Get disassembly around entry point
                disasm_result = await r2_session.execute_command(
                    f"pd 100 @ 0x{address:x}",
                    expected_type="text"
                )
                
                if not disasm_result.success or not disasm_result.output:
                    continue
                
                disasm_text = disasm_result.output
                
                for config in pattern_configs:
                    for pattern_regex in config['patterns']:
                        matches = re.finditer(pattern_regex, disasm_text, re.IGNORECASE | re.MULTILINE)
                        
                        for match in matches:
                            security_pattern = SecurityPattern(
                                category=category,
                                name=pattern_regex,
                                description=config['description'],
                                risk_level=config['risk_level'],
                                confidence=0.7,  # Good confidence for instruction matches
                                pattern_type="instruction",
                                matched_content=[match.group()],
                                locations=[address],
                                instruction_context=match.group()
                            )
                            patterns.append(security_pattern)
        
        except Exception as e:
            self.logger.warning(
                "Error scanning instruction patterns",
                category=category.value,
                error=str(e)
            )
        
        return patterns
    
    async def _scan_syscall_patterns(
        self,
        r2_session: R2Session,
        category: PatternCategory,
        pattern_configs: List[Dict[str, Any]]
    ) -> List[SecurityPattern]:
        """Scan for system call based security patterns."""
        patterns = []
        
        try:
            # Get system calls from the binary
            syscalls_result = await r2_session.execute_command("axtj sym.imp.*")
            if syscalls_result.success and syscalls_result.output:
                syscalls = syscalls_result.output
                
                for config in pattern_configs:
                    for pattern_regex in config['patterns']:
                        for syscall in syscalls:
                            syscall_name = syscall.get('name', '').lower()
                            
                            if re.search(pattern_regex, syscall_name, re.IGNORECASE):
                                security_pattern = SecurityPattern(
                                    category=category,
                                    name=pattern_regex,
                                    description=config['description'],
                                    risk_level=config['risk_level'],
                                    confidence=0.9,  # Very high confidence for syscall matches
                                    pattern_type="syscall",
                                    matched_content=[syscall_name],
                                    locations=[syscall.get('addr', 0)]
                                )
                                patterns.append(security_pattern)
        
        except Exception as e:
            self.logger.warning(
                "Error scanning syscall patterns",
                category=category.value,
                error=str(e)
            )
        
        return patterns
    
    async def get_detailed_analysis(
        self,
        r2_session: R2Session,
        pattern: SecurityPattern
    ) -> Dict[str, Any]:
        """
        Get detailed analysis for a specific security pattern.
        
        Args:
            r2_session: Active radare2 session
            pattern: Security pattern to analyze in detail
            
        Returns:
            Detailed analysis information
        """
        details = {
            'pattern': pattern,
            'context': {},
            'related_functions': [],
            'disassembly': None,
            'cross_references': []
        }
        
        try:
            if pattern.locations:
                primary_address = pattern.locations[0]
                
                # Get function context
                func_result = await r2_session.execute_command(f"afij @ 0x{primary_address:x}")
                if func_result.success and func_result.output:
                    details['context']['function'] = func_result.output
                
                # Get disassembly context
                disasm_result = await r2_session.execute_command(
                    f"pd 20 @ 0x{primary_address:x}",
                    expected_type="text"
                )
                if disasm_result.success and disasm_result.output:
                    details['disassembly'] = disasm_result.output
                
                # Get cross-references
                xrefs_result = await r2_session.execute_command(f"axtj @ 0x{primary_address:x}")
                if xrefs_result.success and xrefs_result.output:
                    details['cross_references'] = xrefs_result.output
        
        except Exception as e:
            self.logger.warning(
                "Error getting detailed analysis",
                pattern_name=pattern.name,
                error=str(e)
            )
        
        return details