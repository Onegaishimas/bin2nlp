"""
Function analysis and extraction processor.

Provides comprehensive function analysis including discovery, metadata extraction,
calling convention detection, and signature analysis using radare2.
"""

import re
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

from ..engines.r2_integration import R2Session, R2SessionException
from ...models.shared.enums import AnalysisDepth, Platform
from ...core.logging import get_logger
from ...core.exceptions import BinaryAnalysisException


logger = get_logger(__name__)


class CallingConvention(Enum):
    """Supported calling conventions."""
    CDECL = "cdecl"
    STDCALL = "stdcall"
    FASTCALL = "fastcall"
    THISCALL = "thiscall"
    VECTORCALL = "vectorcall"
    SYSCALL = "syscall"
    UNKNOWN = "unknown"


class FunctionType(Enum):
    """Function types based on analysis."""
    USER_DEFINED = "user_defined"
    LIBRARY = "library"
    IMPORT = "import"
    EXPORT = "export"
    WRAPPER = "wrapper"
    THUNK = "thunk"
    ENTRY_POINT = "entry_point"
    CONSTRUCTOR = "constructor"
    DESTRUCTOR = "destructor"
    VIRTUAL = "virtual"
    UNKNOWN = "unknown"


@dataclass
class FunctionMetadata:
    """Comprehensive function metadata."""
    address: int
    name: str
    size: int
    offset: int
    
    # Basic properties
    function_type: FunctionType = FunctionType.UNKNOWN
    calling_convention: CallingConvention = CallingConvention.UNKNOWN
    is_recursive: bool = False
    complexity: int = 0  # Cyclomatic complexity
    
    # Call information
    calls_to: List[str] = field(default_factory=list)
    calls_from: List[str] = field(default_factory=list)
    syscalls: List[str] = field(default_factory=list)
    
    # Import/Export information
    imports_used: List[str] = field(default_factory=list)
    strings_referenced: List[str] = field(default_factory=list)
    
    # Signature analysis
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    return_type: Optional[str] = None
    signature: Optional[str] = None
    
    # Security indicators
    stack_frame_size: Optional[int] = None
    has_stack_canary: bool = False
    modifies_return_address: bool = False
    suspicious_patterns: List[str] = field(default_factory=list)
    
    # Assembly information
    instruction_count: int = 0
    basic_blocks: int = 0
    disassembly_preview: Optional[str] = None
    
    @property
    def hex_address(self) -> str:
        """Get hexadecimal representation of address."""
        return f"0x{self.address:x}"
    
    @property
    def is_suspicious(self) -> bool:
        """Check if function has suspicious characteristics."""
        return len(self.suspicious_patterns) > 0


@dataclass
class FunctionAnalysisResult:
    """Complete function analysis results."""
    functions: List[FunctionMetadata]
    analysis_depth: AnalysisDepth
    total_functions: int
    analysis_time: float
    
    # Summary statistics
    user_functions: int = 0
    library_functions: int = 0
    import_functions: int = 0
    suspicious_functions: int = 0
    
    # Call graph statistics
    total_calls: int = 0
    recursive_functions: int = 0
    orphaned_functions: int = 0  # Functions with no callers
    
    # Platform-specific information
    calling_conventions: Dict[CallingConvention, int] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate summary statistics."""
        self.total_functions = len(self.functions)
        self.user_functions = sum(1 for f in self.functions if f.function_type == FunctionType.USER_DEFINED)
        self.library_functions = sum(1 for f in self.functions if f.function_type == FunctionType.LIBRARY)
        self.import_functions = sum(1 for f in self.functions if f.function_type == FunctionType.IMPORT)
        self.suspicious_functions = sum(1 for f in self.functions if f.is_suspicious)
        self.recursive_functions = sum(1 for f in self.functions if f.is_recursive)
        self.total_calls = sum(len(f.calls_to) for f in self.functions)
        
        # Count calling conventions
        self.calling_conventions = {}
        for func in self.functions:
            cc = func.calling_convention
            self.calling_conventions[cc] = self.calling_conventions.get(cc, 0) + 1
        
        # Find orphaned functions (no incoming calls)
        called_functions = set()
        for func in self.functions:
            called_functions.update(func.calls_to)
        
        function_names = {func.name for func in self.functions}
        self.orphaned_functions = len(function_names - called_functions)


class FunctionAnalyzer:
    """
    Comprehensive function analyzer using radare2.
    
    Provides function discovery, metadata extraction, calling convention analysis,
    and security-focused function assessment.
    """
    
    # Suspicious function patterns
    SUSPICIOUS_PATTERNS = {
        'crypto': [
            r'encrypt', r'decrypt', r'crypt', r'cipher', r'hash', r'md5', r'sha',
            r'aes', r'des', r'rsa', r'key', r'random'
        ],
        'network': [
            r'socket', r'connect', r'send', r'recv', r'http', r'ftp', r'url',
            r'download', r'upload', r'internet'
        ],
        'file_ops': [
            r'file', r'read', r'write', r'open', r'create', r'delete', r'copy',
            r'move', r'directory'
        ],
        'registry': [
            r'registry', r'regkey', r'hkey', r'regedit'
        ],
        'process': [
            r'process', r'thread', r'inject', r'hook', r'debug', r'attach',
            r'createprocess', r'shellcode'
        ],
        'evasion': [
            r'anti', r'detect', r'sandbox', r'vm', r'virtual', r'debug',
            r'analysis', r'reverse'
        ]
    }
    
    def __init__(self, platform: Platform = Platform.UNKNOWN):
        """
        Initialize function analyzer.
        
        Args:
            platform: Target platform for platform-specific analysis
        """
        self.platform = platform
        self.logger = logger.bind(component="function_analyzer")
    
    async def analyze_functions(
        self,
        r2_session: R2Session,
        analysis_depth: AnalysisDepth = AnalysisDepth.STANDARD,
        max_functions: Optional[int] = None
    ) -> FunctionAnalysisResult:
        """
        Perform comprehensive function analysis.
        
        Args:
            r2_session: Active radare2 session
            analysis_depth: Depth of analysis to perform
            max_functions: Maximum number of functions to analyze (None for all)
            
        Returns:
            Complete function analysis results
        """
        start_time = asyncio.get_event_loop().time()
        
        self.logger.info(
            "Starting function analysis",
            depth=analysis_depth.value,
            platform=self.platform.value,
            max_functions=max_functions
        )
        
        try:
            # Step 1: Function discovery
            raw_functions = await self._discover_functions(r2_session, analysis_depth)
            
            if max_functions and len(raw_functions) > max_functions:
                raw_functions = raw_functions[:max_functions]
                self.logger.warning(
                    "Limited function analysis due to max_functions constraint",
                    total_found=len(raw_functions),
                    analyzing=max_functions
                )
            
            # Step 2: Extract detailed metadata for each function
            functions = []
            for i, raw_func in enumerate(raw_functions):
                if i % 50 == 0:  # Progress logging
                    self.logger.debug(
                        "Function analysis progress",
                        completed=i,
                        total=len(raw_functions),
                        percent=round((i / len(raw_functions)) * 100, 1)
                    )
                
                try:
                    func_metadata = await self._analyze_single_function(r2_session, raw_func)
                    if func_metadata:
                        functions.append(func_metadata)
                except Exception as e:
                    self.logger.warning(
                        "Failed to analyze function",
                        function_name=raw_func.get('name', 'unknown'),
                        error=str(e)
                    )
            
            # Step 3: Build call graph and cross-references
            await self._build_call_graph(r2_session, functions)
            
            # Step 4: Detect suspicious patterns
            self._detect_suspicious_patterns(functions)
            
            analysis_time = asyncio.get_event_loop().time() - start_time
            
            result = FunctionAnalysisResult(
                functions=functions,
                analysis_depth=analysis_depth,
                total_functions=len(functions),
                analysis_time=analysis_time
            )
            
            self.logger.info(
                "Function analysis completed",
                total_functions=result.total_functions,
                user_functions=result.user_functions,
                suspicious_functions=result.suspicious_functions,
                analysis_time=analysis_time
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Function analysis failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise BinaryAnalysisException(f"Function analysis failed: {e}")
    
    async def _discover_functions(
        self,
        r2_session: R2Session,
        analysis_depth: AnalysisDepth
    ) -> List[Dict[str, Any]]:
        """Discover functions using radare2 analysis."""
        
        # Run appropriate analysis level
        analysis_commands = {
            AnalysisDepth.QUICK: ["aa"],      # Basic analysis
            AnalysisDepth.STANDARD: ["aaa"],  # Standard analysis  
            AnalysisDepth.COMPREHENSIVE: ["aaaa", "aac"]  # Deep analysis + call refs
        }
        
        commands = analysis_commands.get(analysis_depth, ["aaa"])
        
        for cmd in commands:
            self.logger.debug(f"Running R2 analysis command: {cmd}")
            result = await r2_session.execute_command(cmd, timeout=300.0)
            if not result.success:
                self.logger.warning(
                    "Analysis command failed",
                    command=cmd,
                    error=result.error_message
                )
        
        # Get function list
        functions = await r2_session.analyze_functions(analysis_depth.value)
        
        self.logger.info(
            f"Discovered {len(functions)} functions",
            analysis_depth=analysis_depth.value
        )
        
        return functions
    
    async def _analyze_single_function(
        self,
        r2_session: R2Session,
        raw_function: Dict[str, Any]
    ) -> Optional[FunctionMetadata]:
        """Analyze a single function in detail."""
        
        try:
            address = raw_function.get('offset', 0)
            name = raw_function.get('name', f'fcn.{address:08x}')
            size = raw_function.get('size', 0)
            
            if address == 0:
                return None
            
            metadata = FunctionMetadata(
                address=address,
                name=name,
                size=size,
                offset=address
            )
            
            # Get basic function information
            await self._extract_basic_info(r2_session, metadata, raw_function)
            
            # Get function calls
            await self._extract_call_info(r2_session, metadata)
            
            # Analyze function signature and calling convention
            await self._analyze_signature(r2_session, metadata)
            
            # Security analysis
            await self._analyze_security_features(r2_session, metadata)
            
            # Get disassembly preview
            await self._get_disassembly_preview(r2_session, metadata)
            
            return metadata
            
        except Exception as e:
            self.logger.warning(
                "Error analyzing function",
                function_name=raw_function.get('name', 'unknown'),
                error=str(e)
            )
            return None
    
    async def _extract_basic_info(
        self,
        r2_session: R2Session,
        metadata: FunctionMetadata,
        raw_function: Dict[str, Any]
    ) -> None:
        """Extract basic function information."""
        
        # Function type classification
        name_lower = metadata.name.lower()
        
        if metadata.name.startswith('imp.'):
            metadata.function_type = FunctionType.IMPORT
        elif metadata.name.startswith('exp.') or 'export' in name_lower:
            metadata.function_type = FunctionType.EXPORT
        elif metadata.name.startswith('entry') or metadata.name == 'main':
            metadata.function_type = FunctionType.ENTRY_POINT
        elif any(keyword in name_lower for keyword in ['constructor', 'ctor', '__init__']):
            metadata.function_type = FunctionType.CONSTRUCTOR
        elif any(keyword in name_lower for keyword in ['destructor', 'dtor', '__del__']):
            metadata.function_type = FunctionType.DESTRUCTOR
        elif 'thunk' in name_lower:
            metadata.function_type = FunctionType.THUNK
        elif any(lib in name_lower for lib in ['msvcrt', 'kernel32', 'user32', 'ntdll']):
            metadata.function_type = FunctionType.LIBRARY
        else:
            metadata.function_type = FunctionType.USER_DEFINED
        
        # Extract complexity metrics
        metadata.complexity = raw_function.get('cc', 1)  # Cyclomatic complexity
        metadata.instruction_count = raw_function.get('ninstr', 0)
        metadata.basic_blocks = raw_function.get('nbb', 0)
        
        # Check for recursion (basic heuristic)
        if metadata.name in raw_function.get('callrefs', []):
            metadata.is_recursive = True
    
    async def _extract_call_info(
        self,
        r2_session: R2Session,
        metadata: FunctionMetadata
    ) -> None:
        """Extract function call information."""
        
        try:
            # Get function calls using axffj (calls from function)
            result = await r2_session.execute_command(f"axffj @ {metadata.hex_address}")
            if result.success and result.output:
                for call in result.output:
                    call_name = call.get('name', '')
                    if call_name:
                        metadata.calls_to.append(call_name)
            
            # Get calls to this function using axtfj (calls to function)
            result = await r2_session.execute_command(f"axtfj @ {metadata.hex_address}")
            if result.success and result.output:
                for caller in result.output:
                    caller_name = caller.get('name', '')
                    if caller_name:
                        metadata.calls_from.append(caller_name)
            
            # Detect system calls
            disasm_result = await r2_session.execute_command(
                f"pdf @ {metadata.hex_address}",
                expected_type="text"
            )
            if disasm_result.success and disasm_result.output:
                disasm_text = disasm_result.output
                syscall_patterns = [
                    r'int\s+0x80',      # Linux 32-bit syscall
                    r'syscall',         # Linux 64-bit syscall  
                    r'sysenter',        # Windows/Linux fast syscall
                    r'int\s+0x2e'       # Windows syscall
                ]
                
                for pattern in syscall_patterns:
                    matches = re.findall(pattern, disasm_text, re.IGNORECASE)
                    metadata.syscalls.extend(matches)
            
        except Exception as e:
            self.logger.debug(
                "Error extracting call info",
                function=metadata.name,
                error=str(e)
            )
    
    async def _analyze_signature(
        self,
        r2_session: R2Session,
        metadata: FunctionMetadata
    ) -> None:
        """Analyze function signature and calling convention."""
        
        try:
            # Get function signature if available
            sig_result = await r2_session.execute_command(f"afvj @ {metadata.hex_address}")
            if sig_result.success and sig_result.output:
                # Process argument information
                for var in sig_result.output:
                    var_info = {
                        'name': var.get('name', ''),
                        'type': var.get('type', 'unknown'),
                        'offset': var.get('delta', 0)
                    }
                    metadata.parameters.append(var_info)
            
            # Infer calling convention based on platform and analysis
            metadata.calling_convention = self._infer_calling_convention(
                metadata,
                len(metadata.parameters)
            )
            
            # Try to get function signature string
            type_result = await r2_session.execute_command(f"aft @ {metadata.hex_address}")
            if type_result.success and type_result.output:
                metadata.signature = type_result.output.strip()
                
        except Exception as e:
            self.logger.debug(
                "Error analyzing signature",
                function=metadata.name,
                error=str(e)
            )
    
    def _infer_calling_convention(
        self,
        metadata: FunctionMetadata,
        param_count: int
    ) -> CallingConvention:
        """Infer calling convention based on platform and function characteristics."""
        
        if self.platform == Platform.WINDOWS:
            if 'stdcall' in metadata.name.lower():
                return CallingConvention.STDCALL
            elif 'fastcall' in metadata.name.lower():
                return CallingConvention.FASTCALL
            elif 'thiscall' in metadata.name.lower() or metadata.function_type == FunctionType.VIRTUAL:
                return CallingConvention.THISCALL
            elif param_count <= 2:
                return CallingConvention.FASTCALL
            else:
                return CallingConvention.CDECL
        
        elif self.platform in [Platform.LINUX, Platform.MACOS]:
            if 'syscall' in metadata.name.lower() or metadata.syscalls:
                return CallingConvention.SYSCALL
            else:
                return CallingConvention.CDECL
        
        return CallingConvention.UNKNOWN
    
    async def _analyze_security_features(
        self,
        r2_session: R2Session,
        metadata: FunctionMetadata
    ) -> None:
        """Analyze security-related function features."""
        
        try:
            # Get function stack information
            stack_result = await r2_session.execute_command(f"afvs @ {metadata.hex_address}")
            if stack_result.success and stack_result.output:
                # Parse stack frame size
                if isinstance(stack_result.output, list) and stack_result.output:
                    metadata.stack_frame_size = len(stack_result.output) * 8  # Approximate
            
            # Check for stack canaries and security features
            disasm_result = await r2_session.execute_command(
                f"pdf @ {metadata.hex_address}",
                expected_type="text"
            )
            
            if disasm_result.success and disasm_result.output:
                disasm_text = disasm_result.output.lower()
                
                # Stack canary detection
                canary_patterns = [
                    r'__security_cookie',
                    r'__stack_chk_guard',
                    r'gs:\[0x28\]',
                    r'fs:\[0x28\]'
                ]
                
                for pattern in canary_patterns:
                    if re.search(pattern, disasm_text):
                        metadata.has_stack_canary = True
                        break
                
                # Return address modification detection
                ret_patterns = [
                    r'mov.*,.*\[.*bp.*\+.*\]',  # Modify return address on stack
                    r'pop.*ret',                  # Return address manipulation
                ]
                
                for pattern in ret_patterns:
                    if re.search(pattern, disasm_text):
                        metadata.modifies_return_address = True
                        break
                        
        except Exception as e:
            self.logger.debug(
                "Error analyzing security features",
                function=metadata.name,
                error=str(e)
            )
    
    async def _get_disassembly_preview(
        self,
        r2_session: R2Session,
        metadata: FunctionMetadata,
        max_lines: int = 10
    ) -> None:
        """Get disassembly preview for the function."""
        
        try:
            disasm_result = await r2_session.execute_command(
                f"pd {max_lines} @ {metadata.hex_address}",
                expected_type="text"
            )
            
            if disasm_result.success and disasm_result.output:
                metadata.disassembly_preview = disasm_result.output.strip()
                
        except Exception as e:
            self.logger.debug(
                "Error getting disassembly preview",
                function=metadata.name,
                error=str(e)
            )
    
    async def _build_call_graph(
        self,
        r2_session: R2Session,
        functions: List[FunctionMetadata]
    ) -> None:
        """Build call graph relationships between functions."""
        
        # Create lookup map for faster access
        func_map = {func.name: func for func in functions}
        
        # Update cross-references
        for func in functions:
            # Update calls_from based on calls_to of other functions
            for other_func in functions:
                if func.name in other_func.calls_to and other_func.name not in func.calls_from:
                    func.calls_from.append(other_func.name)
    
    def _detect_suspicious_patterns(self, functions: List[FunctionMetadata]) -> None:
        """Detect suspicious patterns in function names and behavior."""
        
        for func in functions:
            name_lower = func.name.lower()
            
            # Check suspicious function names
            for category, patterns in self.SUSPICIOUS_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, name_lower):
                        func.suspicious_patterns.append(f"{category}:{pattern}")
            
            # Check for suspicious characteristics
            if func.modifies_return_address:
                func.suspicious_patterns.append("return_address_manipulation")
            
            if len(func.syscalls) > 0:
                func.suspicious_patterns.append("direct_syscalls")
            
            if func.complexity > 20:
                func.suspicious_patterns.append("high_complexity")
            
            if func.size > 10000:  # Very large functions
                func.suspicious_patterns.append("oversized_function")
            
            # Anti-analysis patterns
            anti_analysis_keywords = [
                'debug', 'trace', 'break', 'step', 'bp', 'watch',
                'patch', 'hook', 'detour'
            ]
            
            if any(keyword in name_lower for keyword in anti_analysis_keywords):
                func.suspicious_patterns.append("anti_analysis")
    
    async def get_function_details(
        self,
        r2_session: R2Session,
        function_address: int,
        include_disassembly: bool = False
    ) -> Optional[FunctionMetadata]:
        """
        Get detailed information for a specific function.
        
        Args:
            r2_session: Active radare2 session
            function_address: Address of the function to analyze
            include_disassembly: Whether to include full disassembly
            
        Returns:
            Detailed function metadata or None if not found
        """
        
        # Get function info at address
        result = await r2_session.execute_command(f"afij @ 0x{function_address:x}")
        
        if not result.success or not result.output:
            return None
        
        raw_function = result.output[0] if isinstance(result.output, list) else result.output
        metadata = await self._analyze_single_function(r2_session, raw_function)
        
        if include_disassembly and metadata:
            disasm_result = await r2_session.disassemble_function(function_address)
            metadata.disassembly_preview = disasm_result
        
        return metadata