"""
Test fixtures for assembly code samples and expected translations.

Provides realistic assembly code examples for different architectures and 
binary types with expected LLM translation outputs for testing consistency.
"""

from typing import Dict, List, Any, NamedTuple
from dataclasses import dataclass


@dataclass
class AssemblyFunction:
    """Container for assembly function with metadata."""
    name: str
    address: str
    size: int
    disassembly: str
    decompiled_code: str
    architecture: str
    complexity: str
    function_type: str
    expected_translation_keywords: List[str]


@dataclass
class BinaryFile:
    """Container for binary file test data."""
    name: str
    file_format: str
    architecture: str
    platform: str
    size: int
    functions: List[AssemblyFunction]
    imports: List[str]
    strings: List[str]
    expected_summary_keywords: List[str]


# x86-64 Windows PE Examples
WIN_PE_MAIN_FUNCTION = AssemblyFunction(
    name="main",
    address="0x401000",
    size=256,
    disassembly="""
0x401000: push   rbp
0x401001: mov    rbp, rsp
0x401004: sub    rsp, 0x40
0x401008: mov    DWORD PTR [rbp-0x4], edi
0x40100b: mov    QWORD PTR [rbp-0x10], rsi
0x40100f: mov    rax, QWORD PTR fs:0x28
0x401018: mov    QWORD PTR [rbp-0x8], rax
0x40101c: xor    eax, eax
0x40101e: lea    rax, [rip+0x2fd5]
0x401025: mov    rdi, rax
0x401028: call   0x401060 <printf@plt>
0x40102d: mov    eax, 0x0
0x401032: mov    rdx, QWORD PTR [rbp-0x8]
0x401036: xor    rdx, QWORD PTR fs:0x28
0x40103f: je     0x401046
0x401041: call   0x401050 <__stack_chk_fail@plt>
0x401046: leave
0x401047: ret
""",
    decompiled_code="""
int main(int argc, char **argv)
{
    printf("Hello, World!\\n");
    return 0;
}
""",
    architecture="x86_64",
    complexity="low",
    function_type="entry_point",
    expected_translation_keywords=["main", "entry", "printf", "hello world", "stack protection"]
)

WIN_PE_CRYPTO_FUNCTION = AssemblyFunction(
    name="encrypt_data",
    address="0x401200",
    size=512,
    disassembly="""
0x401200: push   rbp
0x401201: mov    rbp, rsp
0x401204: sub    rsp, 0x80
0x40120b: mov    QWORD PTR [rbp-0x78], rdi
0x40120f: mov    DWORD PTR [rbp-0x7c], esi
0x401212: mov    QWORD PTR [rbp-0x88], rdx
0x401219: mov    rax, QWORD PTR fs:0x28
0x401222: mov    QWORD PTR [rbp-0x8], rax
0x401226: xor    eax, eax
0x401228: mov    DWORD PTR [rbp-0x74], 0x0
0x40122f: jmp    0x401271
0x401231: mov    eax, DWORD PTR [rbp-0x74]
0x401234: movsxd rdx, eax
0x401237: mov    rax, QWORD PTR [rbp-0x78]
0x40123b: add    rax, rdx
0x40123e: movzx  eax, BYTE PTR [rax]
0x401241: mov    edx, eax
0x401243: mov    eax, DWORD PTR [rbp-0x74]
0x401246: and    eax, 0xff
0x40124b: xor    eax, edx
0x40124d: mov    edx, eax
0x40124f: mov    eax, DWORD PTR [rbp-0x74]
0x401252: movsxd rcx, eax
0x401255: mov    rax, QWORD PTR [rbp-0x88]
0x401259: add    rax, rcx
0x40125c: mov    BYTE PTR [rax], dl
0x40125e: add    DWORD PTR [rbp-0x74], 0x1
0x401262: mov    eax, DWORD PTR [rbp-0x74]
0x401265: cmp    eax, DWORD PTR [rbp-0x7c]
0x401268: jl     0x401231
0x40126a: mov    eax, 0x0
0x40126f: leave
0x401270: ret
""",
    decompiled_code="""
int encrypt_data(char *input, int len, char *output)
{
    int i;
    for (i = 0; i < len; i++) {
        output[i] = input[i] ^ (i & 0xff);
    }
    return 0;
}
""",
    architecture="x86_64",
    complexity="medium", 
    function_type="utility",
    expected_translation_keywords=["encrypt", "xor", "cipher", "loop", "byte manipulation", "security"]
)

# ARM64 Linux ELF Examples
ARM64_ELF_NETWORK_FUNCTION = AssemblyFunction(
    name="connect_server",
    address="0x10000400",
    size=384,
    disassembly="""
0x10000400: stp    x29, x30, [sp, #-32]!
0x10000404: mov    x29, sp
0x10000408: str    w0, [sp, #28]
0x1000040c: str    x1, [sp, #16]
0x10000410: mov    w0, #2
0x10000414: mov    w1, #1
0x10000418: mov    w2, #0
0x1000041c: bl     0x10000600 <socket>
0x10000420: str    w0, [sp, #12]
0x10000424: ldr    w0, [sp, #12]
0x10000428: cmn    w0, #1
0x1000042c: b.ne   0x10000438
0x10000430: mov    w0, #-1
0x10000434: b      0x10000478
0x10000438: add    x0, sp, #16
0x1000043c: mov    w1, #0
0x10000440: mov    w2, #16
0x10000444: bl     0x10000620 <memset>
0x10000448: mov    w0, #2
0x1000044c: strh   w0, [sp, #16]
0x10000450: ldr    w0, [sp, #28]
0x10000454: bl     0x10000640 <htons>
0x10000458: strh   w0, [sp, #18]
0x1000045c: ldr    w0, [sp, #12]
0x10000460: add    x1, sp, #16
0x10000464: mov    w2, #16
0x10000468: bl     0x10000660 <connect>
0x1000046c: cmp    w0, #0
0x10000470: b.ge   0x10000478
0x10000474: mov    w0, #-1
0x10000478: ldp    x29, x30, [sp], #32
0x1000047c: ret
""",
    decompiled_code="""
int connect_server(int port, struct sockaddr_in *addr)
{
    int sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd == -1) {
        return -1;
    }
    
    memset(addr, 0, sizeof(struct sockaddr_in));
    addr->sin_family = AF_INET;
    addr->sin_port = htons(port);
    
    if (connect(sockfd, (struct sockaddr*)addr, sizeof(*addr)) < 0) {
        return -1;
    }
    
    return sockfd;
}
""",
    architecture="arm64",
    complexity="medium",
    function_type="network",
    expected_translation_keywords=["socket", "connect", "network", "TCP", "server", "communication"]
)

# x86 32-bit Examples
X86_32_FILE_FUNCTION = AssemblyFunction(
    name="read_config",
    address="0x08048400",
    size=320,
    disassembly="""
0x08048400: push   ebp
0x08048401: mov    ebp, esp
0x08048403: sub    esp, 0x418
0x08048409: mov    eax, DWORD PTR [ebp+0x8]
0x0804840c: mov    DWORD PTR [esp+0x4], eax
0x08048410: mov    DWORD PTR [esp], 0x8048580
0x08048417: call   0x8048330 <fopen@plt>
0x0804841c: mov    DWORD PTR [ebp-0xc], eax
0x0804841f: cmp    DWORD PTR [ebp-0xc], 0x0
0x08048423: jne    0x8048435
0x08048425: mov    DWORD PTR [esp], 0x8048583
0x0804842c: call   0x8048340 <printf@plt>
0x08048431: mov    eax, 0xffffffff
0x08048436: jmp    0x8048490
0x08048438: lea    eax, [ebp-0x408]
0x0804843e: mov    DWORD PTR [esp+0x8], 0x400
0x08048446: mov    DWORD PTR [esp+0x4], eax
0x0804844a: mov    eax, DWORD PTR [ebp-0xc]
0x0804844d: mov    DWORD PTR [esp], eax
0x08048450: call   0x8048350 <fread@plt>
0x08048455: mov    DWORD PTR [ebp-0x10], eax
0x08048458: cmp    DWORD PTR [ebp-0x10], 0x0
0x0804845c: jg     0x8048470
0x0804845e: mov    eax, DWORD PTR [ebp-0xc]
0x08048461: mov    DWORD PTR [esp], eax
0x08048464: call   0x8048360 <fclose@plt>
0x08048469: mov    eax, 0x0
0x0804846e: jmp    0x8048490
0x08048470: mov    eax, DWORD PTR [ebp-0xc]
0x08048473: mov    DWORD PTR [esp], eax
0x08048476: call   0x8048360 <fclose@plt>
0x0804847b: lea    eax, [ebp-0x408]
0x08048481: mov    DWORD PTR [esp], eax
0x08048484: call   0x8048370 <parse_config>
0x08048489: mov    eax, 0x1
0x0804848e: leave
0x0804848f: ret
""",
    decompiled_code="""
int read_config(char *filename)
{
    FILE *file;
    char buffer[1024];
    size_t bytes_read;
    
    file = fopen(filename, "r");
    if (file == NULL) {
        printf("Error opening file\\n");
        return -1;
    }
    
    bytes_read = fread(buffer, 1, 1024, file);
    if (bytes_read <= 0) {
        fclose(file);
        return 0;
    }
    
    fclose(file);
    parse_config(buffer);
    return 1;
}
""",
    architecture="x86",
    complexity="medium",
    function_type="file_io",
    expected_translation_keywords=["file", "config", "read", "parse", "fopen", "fread", "buffer"]
)

# Binary File Test Data
SAMPLE_PE_FILE = BinaryFile(
    name="sample_app.exe",
    file_format="pe",
    architecture="x86_64",
    platform="windows",
    size=2048576,  # 2MB
    functions=[WIN_PE_MAIN_FUNCTION, WIN_PE_CRYPTO_FUNCTION],
    imports=[
        "kernel32.dll!CreateFileW",
        "kernel32.dll!ReadFile", 
        "kernel32.dll!WriteFile",
        "kernel32.dll!CloseHandle",
        "ntdll.dll!RtlSecureZeroMemory",
        "user32.dll!MessageBoxW"
    ],
    strings=[
        "Hello, World!",
        "Error: Cannot open file",
        "Configuration loaded successfully",
        "https://api.example.com/update",
        "SOFTWARE\\\\MyApp\\\\Config"
    ],
    expected_summary_keywords=["application", "file operations", "encryption", "configuration", "windows"]
)

SAMPLE_ELF_FILE = BinaryFile(
    name="network_tool",
    file_format="elf",
    architecture="arm64", 
    platform="linux",
    size=1024768,  # 1MB
    functions=[ARM64_ELF_NETWORK_FUNCTION],
    imports=[
        "libc.so.6!socket",
        "libc.so.6!connect",
        "libc.so.6!send",
        "libc.so.6!recv",
        "libc.so.6!close",
        "libc.so.6!memset"
    ],
    strings=[
        "/etc/network_tool.conf",
        "Connection established",
        "Failed to connect to server",
        "127.0.0.1",
        "Usage: network_tool [options]"
    ],
    expected_summary_keywords=["network", "client", "communication", "TCP", "linux", "tool"]
)

SAMPLE_MACHO_FILE = BinaryFile(
    name="crypto_util",
    file_format="macho",
    architecture="x86_64",
    platform="macos",
    size=512000,  # 512KB
    functions=[],  # Simplified for this example
    imports=[
        "libSystem.B.dylib!malloc",
        "libSystem.B.dylib!free",
        "libSystem.B.dylib!memcpy",
        "Security.framework!SecRandomCopyBytes"
    ],
    strings=[
        "Encryption key generated",
        "Invalid key length",
        "/Users/*/Library/Application Support/",
        "com.example.cryptoutil"
    ],
    expected_summary_keywords=["cryptography", "utility", "security", "macos", "keychain"]
)

# Complex Assembly Pattern Examples
OBFUSCATED_FUNCTION = AssemblyFunction(
    name="obfuscated_check",
    address="0x401500",
    size=768,
    disassembly="""
0x401500: push   rbp
0x401501: mov    rbp, rsp
0x401504: sub    rsp, 0x30
0x401508: mov    QWORD PTR [rbp-0x28], rdi
0x40150c: mov    rax, 0x5851f42d4c957f2d
0x401516: mov    QWORD PTR [rbp-0x8], rax
0x40151a: mov    rax, 0x4b87d6e728d7c829
0x401524: mov    QWORD PTR [rbp-0x10], rax
0x401528: mov    DWORD PTR [rbp-0x14], 0x0
0x40152f: jmp    0x401590
0x401531: mov    eax, DWORD PTR [rbp-0x14]
0x401534: movsxd rdx, eax
0x401537: mov    rax, QWORD PTR [rbp-0x28]
0x40153b: add    rax, rdx
0x40153e: movzx  eax, BYTE PTR [rax]
0x401541: movsx  eax, al
0x401544: mov    edx, eax
0x401546: mov    eax, DWORD PTR [rbp-0x14]
0x401549: and    eax, 0x7
0x40154c: mov    ecx, eax
0x40154e: mov    rax, QWORD PTR [rbp-0x8]
0x401552: sar    rax, cl
0x401555: and    eax, 0xff
0x40155a: xor    eax, edx
0x40155c: mov    edx, eax
0x40155e: mov    eax, DWORD PTR [rbp-0x14]
0x401561: and    eax, 0x7
0x401564: mov    ecx, eax
0x401566: mov    rax, QWORD PTR [rbp-0x10]
0x40156a: sar    rax, cl
0x40156d: and    eax, 0xff
0x401572: xor    eax, edx
0x401574: test   al, al
0x401576: je     0x40158c
0x401578: mov    eax, 0x0
0x40157d: jmp    0x40159c
0x40157f: nop
0x401580: nop
0x401581: nop
0x401582: nop
0x401583: nop
0x401584: jmp    0x401590
0x401586: add    DWORD PTR [rbp-0x14], 0x1
0x40158a: jmp    0x401590
0x40158c: add    DWORD PTR [rbp-0x14], 0x1
0x401590: cmp    DWORD PTR [rbp-0x14], 0x1f
0x401594: jle    0x401531
0x401596: mov    eax, 0x1
0x40159b: leave
0x40159c: ret
""",
    decompiled_code="""
int obfuscated_check(char *input)
{
    uint64_t key1 = 0x5851f42d4c957f2d;
    uint64_t key2 = 0x4b87d6e728d7c829;
    int i;
    
    for (i = 0; i <= 31; i++) {
        int char_val = (int)input[i];
        int shift = i & 0x7;
        int xor_val1 = ((key1 >> shift) & 0xff) ^ char_val;
        int xor_val2 = ((key2 >> shift) & 0xff) ^ xor_val1;
        
        if (xor_val2 != 0) {
            return 0;  // Validation failed
        }
    }
    return 1;  // Validation passed
}
""",
    architecture="x86_64",
    complexity="high",
    function_type="security",
    expected_translation_keywords=["obfuscated", "validation", "cryptographic", "key", "xor", "anti-tampering"]
)

# Test data collections
ALL_FUNCTIONS = [
    WIN_PE_MAIN_FUNCTION,
    WIN_PE_CRYPTO_FUNCTION,
    ARM64_ELF_NETWORK_FUNCTION,
    X86_32_FILE_FUNCTION,
    OBFUSCATED_FUNCTION
]

ALL_BINARY_FILES = [
    SAMPLE_PE_FILE,
    SAMPLE_ELF_FILE, 
    SAMPLE_MACHO_FILE
]

# Function type categorization
FUNCTION_CATEGORIES = {
    "entry_point": [WIN_PE_MAIN_FUNCTION],
    "utility": [WIN_PE_CRYPTO_FUNCTION],
    "network": [ARM64_ELF_NETWORK_FUNCTION],
    "file_io": [X86_32_FILE_FUNCTION],
    "security": [OBFUSCATED_FUNCTION]
}

COMPLEXITY_LEVELS = {
    "low": [WIN_PE_MAIN_FUNCTION],
    "medium": [WIN_PE_CRYPTO_FUNCTION, ARM64_ELF_NETWORK_FUNCTION, X86_32_FILE_FUNCTION],
    "high": [OBFUSCATED_FUNCTION]
}

ARCHITECTURES = {
    "x86_64": [WIN_PE_MAIN_FUNCTION, WIN_PE_CRYPTO_FUNCTION, OBFUSCATED_FUNCTION],
    "arm64": [ARM64_ELF_NETWORK_FUNCTION],
    "x86": [X86_32_FILE_FUNCTION]
}


def get_functions_by_criteria(
    architecture: str = None,
    complexity: str = None,
    function_type: str = None
) -> List[AssemblyFunction]:
    """
    Get functions matching specified criteria.
    
    Args:
        architecture: Filter by architecture (x86, x86_64, arm64)
        complexity: Filter by complexity (low, medium, high)
        function_type: Filter by type (entry_point, utility, network, etc.)
        
    Returns:
        List of matching AssemblyFunction objects
    """
    functions = ALL_FUNCTIONS[:]
    
    if architecture:
        functions = [f for f in functions if f.architecture == architecture]
    
    if complexity:
        functions = [f for f in functions if f.complexity == complexity]
        
    if function_type:
        functions = [f for f in functions if f.function_type == function_type]
    
    return functions


def get_binary_by_format(file_format: str) -> BinaryFile:
    """Get sample binary file by format."""
    format_map = {
        "pe": SAMPLE_PE_FILE,
        "elf": SAMPLE_ELF_FILE,
        "macho": SAMPLE_MACHO_FILE
    }
    return format_map.get(file_format.lower())


def get_expected_translation_quality(function: AssemblyFunction, provider: str) -> float:
    """
    Get expected translation quality score based on function complexity and provider.
    
    Args:
        function: AssemblyFunction to evaluate
        provider: LLM provider name
        
    Returns:
        Expected quality score (0.0-10.0)
    """
    base_scores = {
        "openai": 8.5,
        "anthropic": 9.0,
        "gemini": 8.0,
        "ollama": 7.5
    }
    
    complexity_modifiers = {
        "low": 1.2,
        "medium": 1.0,
        "high": 0.8
    }
    
    base_score = base_scores.get(provider, 7.0)
    modifier = complexity_modifiers.get(function.complexity, 1.0)
    
    return min(10.0, base_score * modifier)