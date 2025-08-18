"""
Test fixtures for binary file data generation and validation.

Provides utilities to create test binary files with various characteristics
for comprehensive testing of the decompilation and translation pipeline.
"""

import tempfile
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import hashlib
import struct
import random


@dataclass
class TestBinaryMetadata:
    """Metadata for test binary files."""
    name: str
    file_format: str
    architecture: str
    platform: str
    size: int
    complexity: str
    file_type: str
    expected_functions: int
    expected_imports: int
    expected_strings: int
    sha256_hash: Optional[str] = None
    created_at: Optional[str] = None


class TestBinaryGenerator:
    """Generate test binary files with specific characteristics."""
    
    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.generated_files = []
    
    def create_pe_file(
        self,
        name: str = "test.exe",
        complexity: str = "medium",
        size_kb: int = 100
    ) -> Tuple[str, TestBinaryMetadata]:
        """
        Create a test PE file with realistic structure.
        
        Args:
            name: Filename for the test binary
            complexity: Complexity level (low, medium, high)
            size_kb: Approximate file size in KB
            
        Returns:
            Tuple of (file_path, metadata)
        """
        file_path = os.path.join(self.temp_dir, name)
        
        # Create minimal PE structure
        pe_data = self._create_pe_structure(complexity, size_kb)
        
        with open(file_path, 'wb') as f:
            f.write(pe_data)
        
        metadata = TestBinaryMetadata(
            name=name,
            file_format="pe",
            architecture="x86_64",
            platform="windows",
            size=len(pe_data),
            complexity=complexity,
            file_type="executable",
            expected_functions=self._get_expected_functions(complexity),
            expected_imports=self._get_expected_imports(complexity),
            expected_strings=self._get_expected_strings(complexity),
            sha256_hash=hashlib.sha256(pe_data).hexdigest()
        )
        
        self.generated_files.append(file_path)
        return file_path, metadata
    
    def create_elf_file(
        self,
        name: str = "test_binary",
        complexity: str = "medium",
        size_kb: int = 80
    ) -> Tuple[str, TestBinaryMetadata]:
        """Create a test ELF file."""
        file_path = os.path.join(self.temp_dir, name)
        
        elf_data = self._create_elf_structure(complexity, size_kb)
        
        with open(file_path, 'wb') as f:
            f.write(elf_data)
        
        metadata = TestBinaryMetadata(
            name=name,
            file_format="elf",
            architecture="x86_64",
            platform="linux",
            size=len(elf_data),
            complexity=complexity,
            file_type="executable",
            expected_functions=self._get_expected_functions(complexity),
            expected_imports=self._get_expected_imports(complexity),
            expected_strings=self._get_expected_strings(complexity),
            sha256_hash=hashlib.sha256(elf_data).hexdigest()
        )
        
        self.generated_files.append(file_path)
        return file_path, metadata
    
    def create_macho_file(
        self,
        name: str = "test_app",
        complexity: str = "medium",
        size_kb: int = 120
    ) -> Tuple[str, TestBinaryMetadata]:
        """Create a test Mach-O file."""
        file_path = os.path.join(self.temp_dir, name)
        
        macho_data = self._create_macho_structure(complexity, size_kb)
        
        with open(file_path, 'wb') as f:
            f.write(macho_data)
        
        metadata = TestBinaryMetadata(
            name=name,
            file_format="macho",
            architecture="x86_64",
            platform="macos",
            size=len(macho_data),
            complexity=complexity,
            file_type="executable",
            expected_functions=self._get_expected_functions(complexity),
            expected_imports=self._get_expected_imports(complexity),
            expected_strings=self._get_expected_strings(complexity),
            sha256_hash=hashlib.sha256(macho_data).hexdigest()
        )
        
        self.generated_files.append(file_path)
        return file_path, metadata
    
    def _create_pe_structure(self, complexity: str, size_kb: int) -> bytes:
        """Create minimal PE file structure."""
        # DOS header
        dos_header = b'MZ' + b'\x00' * 58 + struct.pack('<L', 0x80)  # e_lfanew
        
        # DOS stub
        dos_stub = b'\x0e\x1f\xba\x0e\x00\xb4\x09\xcd\x21\xb8\x01\x4c\xcd\x21This program cannot be run in DOS mode.\r\r\n$\x00\x00\x00\x00\x00\x00\x00'
        
        # Align to offset 0x80
        dos_stub += b'\x00' * (0x80 - len(dos_header) - len(dos_stub))
        
        # PE signature
        pe_signature = b'PE\x00\x00'
        
        # COFF header
        machine = 0x8664  # AMD64
        num_sections = 3 if complexity == "low" else 5 if complexity == "medium" else 8
        timestamp = 0x12345678
        ptr_to_symbol_table = 0
        num_symbols = 0
        size_of_optional_header = 0xF0
        characteristics = 0x0022  # IMAGE_FILE_EXECUTABLE_IMAGE | IMAGE_FILE_LARGE_ADDRESS_AWARE
        
        coff_header = struct.pack('<HHLLLLHH',
                                  machine, num_sections, timestamp, ptr_to_symbol_table,
                                  num_symbols, size_of_optional_header, characteristics)
        
        # Optional header (simplified)
        optional_header = struct.pack('<H', 0x20B)  # PE32+ magic
        optional_header += b'\x00' * (size_of_optional_header - 2)
        
        # Section headers (simplified)
        section_headers = b''
        for i in range(num_sections):
            section_name = f'.text{i}'.encode().ljust(8, b'\x00')[:8]
            section_headers += section_name + b'\x00' * 32  # Simplified section header
        
        # Pad to desired size
        current_size = len(dos_header + dos_stub + pe_signature + coff_header + optional_header + section_headers)
        padding_size = (size_kb * 1024) - current_size
        padding = self._generate_realistic_padding(padding_size, complexity)
        
        return dos_header + dos_stub + pe_signature + coff_header + optional_header + section_headers + padding
    
    def _create_elf_structure(self, complexity: str, size_kb: int) -> bytes:
        """Create minimal ELF file structure."""
        # ELF header
        elf_magic = b'\x7fELF'
        elf_class = b'\x02'  # 64-bit
        elf_data = b'\x01'   # Little endian
        elf_version = b'\x01'
        elf_osabi = b'\x00'  # System V ABI
        elf_abiversion = b'\x00'
        elf_pad = b'\x00' * 7
        
        e_type = struct.pack('<H', 2)  # ET_EXEC
        e_machine = struct.pack('<H', 62)  # EM_X86_64
        e_version = struct.pack('<L', 1)
        e_entry = struct.pack('<Q', 0x400000)  # Entry point
        e_phoff = struct.pack('<Q', 64)  # Program header offset
        e_shoff = struct.pack('<Q', 0)   # Section header offset
        e_flags = struct.pack('<L', 0)
        e_ehsize = struct.pack('<H', 64)
        e_phentsize = struct.pack('<H', 56)
        e_phnum = struct.pack('<H', 3 if complexity == "low" else 5)
        e_shentsize = struct.pack('<H', 64)
        e_shnum = struct.pack('<H', 0)
        e_shstrndx = struct.pack('<H', 0)
        
        elf_header = (elf_magic + elf_class + elf_data + elf_version + elf_osabi +
                     elf_abiversion + elf_pad + e_type + e_machine + e_version + e_entry +
                     e_phoff + e_shoff + e_flags + e_ehsize + e_phentsize + e_phnum +
                     e_shentsize + e_shnum + e_shstrndx)
        
        # Program headers (simplified)
        num_segments = 3 if complexity == "low" else 5
        program_headers = b''
        for i in range(num_segments):
            p_type = struct.pack('<L', 1)  # PT_LOAD
            p_flags = struct.pack('<L', 5)  # PF_R | PF_X
            program_headers += p_type + p_flags + b'\x00' * 48  # Simplified
        
        # Pad to desired size
        current_size = len(elf_header + program_headers)
        padding_size = (size_kb * 1024) - current_size
        padding = self._generate_realistic_padding(padding_size, complexity)
        
        return elf_header + program_headers + padding
    
    def _create_macho_structure(self, complexity: str, size_kb: int) -> bytes:
        """Create minimal Mach-O file structure."""
        # Mach-O header
        magic = struct.pack('<L', 0xfeedfacf)  # MH_MAGIC_64
        cputype = struct.pack('<L', 0x01000007)  # CPU_TYPE_X86_64
        cpusubtype = struct.pack('<L', 0x80000003)  # CPU_SUBTYPE_X86_64_ALL
        filetype = struct.pack('<L', 2)  # MH_EXECUTE
        ncmds = struct.pack('<L', 4 if complexity == "low" else 8)
        sizeofcmds = struct.pack('<L', 200)
        flags = struct.pack('<L', 0x00200085)  # MH_NOUNDEFS | MH_DYLDLINK | MH_TWOLEVEL
        reserved = struct.pack('<L', 0)
        
        macho_header = magic + cputype + cpusubtype + filetype + ncmds + sizeofcmds + flags + reserved
        
        # Load commands (simplified)
        load_commands = b'\x00' * 200  # Simplified load commands
        
        # Pad to desired size
        current_size = len(macho_header + load_commands)
        padding_size = (size_kb * 1024) - current_size
        padding = self._generate_realistic_padding(padding_size, complexity)
        
        return macho_header + load_commands + padding
    
    def _generate_realistic_padding(self, size: int, complexity: str) -> bytes:
        """Generate realistic padding data that simulates code/data sections."""
        if size <= 0:
            return b''
        
        padding = b''
        
        # Add some realistic-looking code patterns
        if complexity == "high":
            # More complex patterns for high complexity
            patterns = [
                b'\x48\x89\xe5',  # mov rbp, rsp
                b'\x48\x83\xec\x20',  # sub rsp, 32
                b'\x48\x8b\x45\x08',  # mov rax, [rbp+8]
                b'\x48\x89\x45\xf8',  # mov [rbp-8], rax
                b'\xe8\x00\x00\x00\x00',  # call
                b'\x48\x83\xc4\x20',  # add rsp, 32
                b'\x5d',  # pop rbp
                b'\xc3',  # ret
            ]
        elif complexity == "medium":
            patterns = [
                b'\x55',  # push rbp
                b'\x48\x89\xe5',  # mov rbp, rsp
                b'\x48\x83\xec\x10',  # sub rsp, 16
                b'\xc3',  # ret
                b'\x90',  # nop
            ]
        else:  # low complexity
            patterns = [
                b'\x90',  # nop
                b'\xc3',  # ret
                b'\x00\x00\x00\x00',  # zeros
            ]
        
        # Add some strings
        strings = [
            b'Hello World\x00',
            b'Error occurred\x00',
            b'Configuration\x00',
            b'https://example.com\x00',
            b'/tmp/temp_file\x00',
            b'SUCCESS\x00',
            b'FAILED\x00',
        ]
        
        remaining = size
        while remaining > 0:
            if remaining > 20 and random.random() < 0.3:
                # Add a string
                string = random.choice(strings)
                chunk_size = min(len(string), remaining)
                padding += string[:chunk_size]
                remaining -= chunk_size
            else:
                # Add a code pattern
                pattern = random.choice(patterns)
                chunk_size = min(len(pattern), remaining)
                padding += pattern[:chunk_size]
                remaining -= chunk_size
        
        return padding
    
    def _get_expected_functions(self, complexity: str) -> int:
        """Get expected number of functions based on complexity."""
        return {
            "low": random.randint(5, 15),
            "medium": random.randint(15, 50),
            "high": random.randint(50, 200)
        }.get(complexity, 25)
    
    def _get_expected_imports(self, complexity: str) -> int:
        """Get expected number of imports based on complexity."""
        return {
            "low": random.randint(3, 10),
            "medium": random.randint(10, 30),
            "high": random.randint(30, 100)
        }.get(complexity, 20)
    
    def _get_expected_strings(self, complexity: str) -> int:
        """Get expected number of strings based on complexity."""
        return {
            "low": random.randint(10, 30),
            "medium": random.randint(30, 100),
            "high": random.randint(100, 500)
        }.get(complexity, 50)
    
    def cleanup(self):
        """Remove all generated test files."""
        for file_path in self.generated_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass
        self.generated_files.clear()


# Predefined test scenarios
TEST_SCENARIOS = {
    "simple_pe": {
        "name": "simple.exe",
        "format": "pe",
        "complexity": "low",
        "size_kb": 50,
        "expected_analysis_time": 30,
        "expected_translation_quality": 8.5
    },
    "complex_pe": {
        "name": "complex_app.exe",
        "format": "pe", 
        "complexity": "high",
        "size_kb": 2048,
        "expected_analysis_time": 180,
        "expected_translation_quality": 7.8
    },
    "medium_elf": {
        "name": "network_tool",
        "format": "elf",
        "complexity": "medium", 
        "size_kb": 512,
        "expected_analysis_time": 90,
        "expected_translation_quality": 8.2
    },
    "simple_macho": {
        "name": "utility.app",
        "format": "macho",
        "complexity": "low",
        "size_kb": 256,
        "expected_analysis_time": 45,
        "expected_translation_quality": 8.0
    },
    "obfuscated_pe": {
        "name": "obfuscated.exe", 
        "format": "pe",
        "complexity": "high",
        "size_kb": 1024,
        "expected_analysis_time": 240,
        "expected_translation_quality": 6.5
    }
}

# Error test cases
ERROR_TEST_CASES = {
    "corrupted_header": {
        "description": "Binary with corrupted header",
        "file_data": b'\x00' * 100,
        "expected_error": "Invalid file format"
    },
    "truncated_file": {
        "description": "Truncated binary file",
        "file_data": b'MZ\x00\x00',
        "expected_error": "Truncated or incomplete file"
    },
    "unknown_format": {
        "description": "Unknown file format",
        "file_data": b'UNKNOWN_FORMAT' + b'\x00' * 100,
        "expected_error": "Unsupported file format"
    },
    "zero_byte_file": {
        "description": "Empty file",
        "file_data": b'',
        "expected_error": "Empty file"
    }
}

# Performance test data
PERFORMANCE_BENCHMARKS = {
    "small_file": {
        "size_range": (10, 100),  # KB
        "expected_time_range": (5, 30),  # seconds
        "function_count_range": (5, 25)
    },
    "medium_file": {
        "size_range": (100, 1000),  # KB
        "expected_time_range": (30, 120),  # seconds
        "function_count_range": (25, 100)
    },
    "large_file": {
        "size_range": (1000, 10000),  # KB
        "expected_time_range": (120, 600),  # seconds
        "function_count_range": (100, 1000)
    }
}


def create_test_suite() -> Dict[str, Any]:
    """
    Create a comprehensive test suite with various binary files.
    
    Returns:
        Dictionary containing test files and metadata
    """
    generator = TestBinaryGenerator()
    test_suite = {
        "files": [],
        "scenarios": TEST_SCENARIOS,
        "error_cases": ERROR_TEST_CASES,
        "performance_benchmarks": PERFORMANCE_BENCHMARKS,
        "generator": generator
    }
    
    # Create test files for each scenario
    for scenario_name, scenario_config in TEST_SCENARIOS.items():
        try:
            if scenario_config["format"] == "pe":
                file_path, metadata = generator.create_pe_file(
                    name=scenario_config["name"],
                    complexity=scenario_config["complexity"],
                    size_kb=scenario_config["size_kb"]
                )
            elif scenario_config["format"] == "elf":
                file_path, metadata = generator.create_elf_file(
                    name=scenario_config["name"],
                    complexity=scenario_config["complexity"],
                    size_kb=scenario_config["size_kb"]
                )
            elif scenario_config["format"] == "macho":
                file_path, metadata = generator.create_macho_file(
                    name=scenario_config["name"],
                    complexity=scenario_config["complexity"],
                    size_kb=scenario_config["size_kb"]
                )
            
            test_suite["files"].append({
                "scenario": scenario_name,
                "file_path": file_path,
                "metadata": metadata,
                "config": scenario_config
            })
        except Exception as e:
            print(f"Warning: Failed to create test file for {scenario_name}: {e}")
    
    return test_suite


def validate_decompilation_results(
    results: Dict[str, Any],
    expected_metadata: TestBinaryMetadata
) -> Dict[str, Any]:
    """
    Validate decompilation results against expected values.
    
    Args:
        results: Decompilation results from the engine
        expected_metadata: Expected metadata for validation
        
    Returns:
        Validation results with scores and details
    """
    validation = {
        "overall_score": 0.0,
        "function_count_score": 0.0,
        "import_count_score": 0.0,
        "string_count_score": 0.0,
        "details": {},
        "passed": False
    }
    
    try:
        # Validate function count
        actual_functions = len(results.get("functions", []))
        expected_functions = expected_metadata.expected_functions
        function_ratio = min(actual_functions / max(expected_functions, 1), 2.0)
        validation["function_count_score"] = max(0.0, 1.0 - abs(function_ratio - 1.0))
        
        # Validate import count
        actual_imports = len(results.get("imports", []))
        expected_imports = expected_metadata.expected_imports
        import_ratio = min(actual_imports / max(expected_imports, 1), 2.0)
        validation["import_count_score"] = max(0.0, 1.0 - abs(import_ratio - 1.0))
        
        # Validate string count
        actual_strings = len(results.get("strings", []))
        expected_strings = expected_metadata.expected_strings
        string_ratio = min(actual_strings / max(expected_strings, 1), 2.0)
        validation["string_count_score"] = max(0.0, 1.0 - abs(string_ratio - 1.0))
        
        # Calculate overall score
        scores = [
            validation["function_count_score"],
            validation["import_count_score"], 
            validation["string_count_score"]
        ]
        validation["overall_score"] = sum(scores) / len(scores)
        validation["passed"] = validation["overall_score"] >= 0.7
        
        validation["details"] = {
            "functions": {"actual": actual_functions, "expected": expected_functions},
            "imports": {"actual": actual_imports, "expected": expected_imports},
            "strings": {"actual": actual_strings, "expected": expected_strings}
        }
        
    except Exception as e:
        validation["details"]["error"] = str(e)
    
    return validation