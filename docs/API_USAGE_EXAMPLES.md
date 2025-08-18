# API Usage Examples

This guide provides comprehensive examples for using the bin2nlp API with different LLM providers, request types, and response formats.

## 📋 Quick Reference

### Base URL
```
http://localhost:8000  # Local development
https://api.bin2nlp.com  # Production (example)
```

### Authentication
Currently no authentication required for basic usage. API keys may be required for production deployments.

### Content Types
- **Request**: `multipart/form-data` (file uploads)
- **Response**: `application/json`

## 🚀 Basic Usage

### Simple Decompilation Request

```bash
curl -X POST "http://localhost:8000/api/v1/decompile" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample.exe"
```

### Response Structure
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "created_at": "2025-08-18T10:30:00Z",
  "completed_at": "2025-08-18T10:30:45Z",
  "processing_time": 45.2,
  "decompilation_results": { "..." },
  "translation_results": { "..." }
}
```

## 🧠 Provider-Specific Examples

### OpenAI GPT-4 (Structured Technical Analysis)

```bash
curl -X POST "http://localhost:8000/api/v1/decompile" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@malware_sample.exe" \
  -F "llm_provider=openai" \
  -F "llm_model=gpt-4" \
  -F "translation_detail=comprehensive" \
  -F "decompilation_depth=comprehensive"
```

#### Expected Response
```json
{
  "job_id": "uuid-here",
  "status": "completed",
  "decompilation_results": {
    "metadata": {
      "file_hash": "a1b2c3d4e5f6...",
      "file_format": "pe",
      "architecture": "x86_64",
      "platform": "windows",
      "total_functions": 127,
      "total_imports": 45,
      "total_strings": 203
    },
    "functions": [
      {
        "name": "main",
        "address": "0x401000",
        "size": 256,
        "disassembly": "push rbp; mov rbp, rsp; sub rsp, 0x30; ...",
        "decompiled_code": "int main(int argc, char* argv[]) { ... }"
      }
    ]
  },
  "translation_results": {
    "overall_summary": {
      "program_purpose": "This appears to be a network reconnaissance tool with credential harvesting capabilities. The program establishes encrypted connections to remote servers and implements keylogging functionality through Windows API hooks.",
      "key_behaviors": [
        "Establishes persistent network connections using WinSock APIs",
        "Implements keylogging through SetWindowsHookEx API calls", 
        "Performs process injection using VirtualAllocEx and WriteProcessMemory",
        "Encrypts collected data using a custom XOR-based cipher",
        "Maintains persistence through registry modifications"
      ],
      "security_considerations": "This binary exhibits multiple indicators of malicious behavior including process injection, keylogging, and encrypted data transmission. The combination of persistence mechanisms and credential harvesting capabilities suggests this is likely malware."
    },
    "function_translations": [
      {
        "function_name": "main",
        "function_address": "0x401000", 
        "natural_language": "This is the main entry point that initializes the malware's core functionality. It first performs environment checks to detect analysis environments, then establishes persistence by writing registry keys. After initialization, it spawns worker threads for network communication and keylogging operations.",
        "purpose": "Malware initialization and worker thread spawning",
        "parameters": [
          "argc: Command line argument count - used for debugging mode detection",
          "argv: Command line arguments - may contain configuration parameters"
        ],
        "return_value": "Returns 0 on successful initialization, -1 on environment detection failure"
      }
    ],
    "import_explanations": [
      {
        "library": "kernel32.dll",
        "function": "VirtualAllocEx",
        "purpose": "Allocates memory in target processes for code injection. This is a common technique used by malware to inject malicious code into legitimate processes.",
        "parameters": "Target process handle, memory address, size, allocation type, and memory protection flags",
        "common_usage": "Process injection, DLL injection, shellcode execution"
      }
    ],
    "llm_provider": "openai",
    "llm_model": "gpt-4", 
    "total_tokens_used": 4523,
    "estimated_cost": 0.18,
    "processing_time": 23.4,
    "overall_quality": 9.2
  }
}
```

### Anthropic Claude (Detailed Contextual Analysis)

```bash
curl -X POST "http://localhost:8000/api/v1/decompile" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@legitimate_app.exe" \
  -F "llm_provider=anthropic" \
  -F "llm_model=claude-3-sonnet-20240229" \
  -F "translation_detail=standard"
```

#### Expected Response
```json
{
  "translation_results": {
    "overall_summary": {
      "program_purpose": "This appears to be a legitimate system utility application designed for network configuration management. The program provides both command-line and GUI interfaces for managing network adapter settings, with particular focus on IPv4/IPv6 configuration and DNS management.",
      "key_behaviors": [
        "Enumerates network adapters using WMI (Windows Management Instrumentation)",
        "Modifies network configuration through Windows networking APIs",
        "Provides user interface for network settings management",
        "Validates network configurations before applying changes",
        "Implements proper error handling and user feedback mechanisms"
      ],
      "security_considerations": "The application requires elevated privileges to modify network settings, which is appropriate for its functionality. The code demonstrates proper input validation and follows Windows security guidelines for system configuration utilities."
    },
    "function_translations": [
      {
        "function_name": "validate_ip_address",
        "natural_language": "This function implements comprehensive IP address validation for both IPv4 and IPv6 formats. It begins by parsing the input string to determine the IP version, then applies format-specific validation rules. For IPv4, it validates octet ranges (0-255) and checks for valid subnet masks. For IPv6, it validates hexadecimal groups and handles compressed notation. The function also performs additional checks for reserved addresses and ensures the IP is appropriate for the intended network context.",
        "purpose": "Input validation for network configuration",
        "parameters": [
          "ip_string: String representation of the IP address to validate",
          "ip_version: Expected IP version (4 or 6), or 0 for auto-detection"
        ]
      }
    ],
    "llm_provider": "anthropic",
    "llm_model": "claude-3-sonnet-20240229",
    "total_tokens_used": 3847,
    "estimated_cost": 0.12,
    "processing_time": 28.7
  }
}
```

### Google Gemini (Fast, Practical Analysis)

```bash
curl -X POST "http://localhost:8000/api/v1/decompile" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@simple_utility.exe" \
  -F "llm_provider=gemini" \
  -F "llm_model=gemini-pro" \
  -F "translation_detail=brief"
```

#### Expected Response
```json
{
  "translation_results": {
    "overall_summary": {
      "program_purpose": "Simple file processing utility that reads text files, performs basic text transformations, and outputs results to specified destinations.",
      "key_behaviors": [
        "File input/output operations",
        "Text processing and transformation", 
        "Command-line argument parsing",
        "Error handling and logging"
      ]
    },
    "function_translations": [
      {
        "function_name": "process_file",
        "natural_language": "Reads input file, applies text transformations like case conversion and whitespace normalization, then writes output to destination file.",
        "purpose": "Core file processing logic"
      }
    ],
    "llm_provider": "gemini",
    "llm_model": "gemini-pro",
    "total_tokens_used": 1234,
    "estimated_cost": 0.003,
    "processing_time": 8.2
  }
}
```

### Ollama (Local Privacy-Focused Analysis)

```bash
curl -X POST "http://localhost:8000/api/v1/decompile" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@proprietary_binary.exe" \
  -F "llm_provider=ollama" \
  -F "llm_model=huihui_ai/phi4-abliterated" \
  -F "translation_detail=standard"
```

#### Expected Response
```json
{
  "translation_results": {
    "overall_summary": {
      "program_purpose": "Binary analysis indicates a data processing application with encryption capabilities.",
      "key_behaviors": [
        "File encryption/decryption operations",
        "Network communication with authentication",
        "Configuration file management"
      ]
    },
    "function_translations": [
      {
        "function_name": "encrypt_data",
        "natural_language": "Implements AES-256 encryption for data protection. Takes input buffer and encryption key, applies AES encryption, and returns encrypted buffer.",
        "purpose": "Data encryption for secure storage"
      }
    ],
    "llm_provider": "ollama", 
    "llm_model": "huihui_ai/phi4-abliterated",
    "total_tokens_used": 1876,
    "estimated_cost": 0.0,
    "processing_time": 45.6
  }
}
```

## 🔧 Advanced Configuration Examples

### Provider Fallback Chain

```bash
curl -X POST "http://localhost:8000/api/v1/decompile" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@complex_binary.exe" \
  -F "llm_provider=openai" \
  -F "fallback_providers=anthropic,gemini,ollama" \
  -F "max_cost_usd=2.00"
```

### Custom Analysis Parameters

```bash
curl -X POST "http://localhost:8000/api/v1/decompile" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@target_binary.exe" \
  -F "decompilation_depth=comprehensive" \
  -F "translation_detail=comprehensive" \
  -F "include_assembly=true" \
  -F "include_strings=true" \
  -F "include_imports=true" \
  -F "timeout_seconds=1800"
```

### Batch Processing

```bash
# Submit multiple files
for file in *.exe; do
  curl -X POST "http://localhost:8000/api/v1/decompile" \
    -H "Content-Type: multipart/form-data" \
    -F "file=@$file" \
    -F "llm_provider=gemini" \
    -F "translation_detail=brief" &
done
wait
```

## 📊 Response Formats

### Job Status Polling

```bash
# Check job status
curl "http://localhost:8000/api/v1/decompile/550e8400-e29b-41d4-a716-446655440000"
```

#### Status Response
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": {
    "current_step": "llm_translation",
    "steps_completed": 2,
    "total_steps": 3,
    "estimated_time_remaining": 30
  },
  "created_at": "2025-08-18T10:30:00Z"
}
```

### Error Responses

#### File Too Large
```json
{
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "File size exceeds maximum limit of 100MB",
    "details": {
      "file_size": 157286400,
      "max_size": 104857600
    }
  }
}
```

#### Provider Unavailable  
```json
{
  "error": {
    "code": "PROVIDER_UNAVAILABLE",
    "message": "OpenAI provider is currently unavailable",
    "details": {
      "provider": "openai",
      "reason": "rate_limit_exceeded",
      "retry_after": 60
    }
  }
}
```

#### Cost Limit Exceeded
```json
{
  "error": {
    "code": "COST_LIMIT_EXCEEDED", 
    "message": "Request would exceed daily spending limit",
    "details": {
      "estimated_cost": 5.50,
      "daily_limit": 10.00,
      "current_spend": 8.75
    }
  }
}
```

## 🐍 Python SDK Examples

### Basic Usage

```python
import requests

def analyze_binary(file_path, provider="openai"):
    with open(file_path, 'rb') as f:
        files = {'file': f}
        data = {
            'llm_provider': provider,
            'translation_detail': 'standard'
        }
        
        response = requests.post(
            'http://localhost:8000/api/v1/decompile',
            files=files,
            data=data
        )
        
        return response.json()

# Usage
result = analyze_binary('malware.exe', provider='anthropic')
print(f"Analysis completed in {result['processing_time']} seconds")
```

### Async Processing with Status Polling

```python
import requests
import time

def submit_analysis(file_path, provider="openai"):
    """Submit file for analysis and return job ID"""
    with open(file_path, 'rb') as f:
        response = requests.post(
            'http://localhost:8000/api/v1/decompile',
            files={'file': f},
            data={'llm_provider': provider}
        )
    return response.json()['job_id']

def poll_status(job_id, interval=10):
    """Poll job status until completion"""
    while True:
        response = requests.get(f'http://localhost:8000/api/v1/decompile/{job_id}')
        result = response.json()
        
        if result['status'] in ['completed', 'failed']:
            return result
            
        print(f"Status: {result['status']} - {result.get('progress', {}).get('current_step', 'processing')}")
        time.sleep(interval)

# Usage
job_id = submit_analysis('large_binary.exe', 'anthropic')
result = poll_status(job_id)
```

### Batch Processing with Cost Management

```python
import requests
from pathlib import Path

class BinaryAnalyzer:
    def __init__(self, base_url="http://localhost:8000", daily_limit=50.0):
        self.base_url = base_url
        self.daily_limit = daily_limit
        self.current_spend = 0.0
        
    def analyze_file(self, file_path, provider="gemini"):
        """Analyze single file with cost tracking"""
        if self.current_spend >= self.daily_limit:
            raise ValueError(f"Daily spending limit of ${self.daily_limit} exceeded")
            
        with open(file_path, 'rb') as f:
            response = requests.post(
                f'{self.base_url}/api/v1/decompile',
                files={'file': f},
                data={'llm_provider': provider}
            )
            
        result = response.json()
        if 'translation_results' in result:
            self.current_spend += result['translation_results'].get('estimated_cost', 0)
            
        return result
    
    def batch_analyze(self, directory_path, pattern="*.exe"):
        """Analyze all files matching pattern"""
        results = []
        directory = Path(directory_path)
        
        for file_path in directory.glob(pattern):
            try:
                result = self.analyze_file(file_path, provider="gemini")  # Cheapest option
                results.append({
                    'file': str(file_path),
                    'result': result
                })
                print(f"✅ Analyzed {file_path.name} - Cost: ${result['translation_results']['estimated_cost']:.3f}")
            except Exception as e:
                print(f"❌ Failed to analyze {file_path.name}: {e}")
                
        return results

# Usage
analyzer = BinaryAnalyzer(daily_limit=25.0)
results = analyzer.batch_analyze('./malware_samples/', '*.exe')
print(f"Total cost: ${analyzer.current_spend:.2f}")
```

## 🔧 JavaScript/Node.js Examples

### Basic Node.js Usage

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

async function analyzeBinary(filePath, provider = 'openai') {
    const form = new FormData();
    form.append('file', fs.createReadStream(filePath));
    form.append('llm_provider', provider);
    form.append('translation_detail', 'standard');
    
    try {
        const response = await axios.post(
            'http://localhost:8000/api/v1/decompile',
            form,
            { headers: form.getHeaders() }
        );
        
        return response.data;
    } catch (error) {
        console.error('Analysis failed:', error.response?.data || error.message);
        throw error;
    }
}

// Usage
analyzeBinary('./sample.exe', 'anthropic')
    .then(result => {
        console.log(`Analysis completed in ${result.processing_time} seconds`);
        console.log('Program purpose:', result.translation_results.overall_summary.program_purpose);
    });
```

### Browser JavaScript with Drag & Drop

```html
<!DOCTYPE html>
<html>
<head>
    <title>bin2nlp Binary Analyzer</title>
</head>
<body>
    <div id="dropzone" style="border: 2px dashed #ccc; padding: 20px;">
        Drop binary files here or click to select
    </div>
    
    <script>
    async function analyzeBinary(file, provider = 'gemini') {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('llm_provider', provider);
        formData.append('translation_detail', 'brief');
        
        const response = await fetch('http://localhost:8000/api/v1/decompile', {
            method: 'POST',
            body: formData
        });
        
        return await response.json();
    }
    
    const dropzone = document.getElementById('dropzone');
    
    dropzone.addEventListener('drop', async (e) => {
        e.preventDefault();
        const file = e.dataTransfer.files[0];
        
        if (file) {
            console.log(`Analyzing ${file.name}...`);
            try {
                const result = await analyzeBinary(file);
                console.log('Analysis result:', result);
            } catch (error) {
                console.error('Analysis failed:', error);
            }
        }
    });
    
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
    });
    </script>
</body>
</html>
```

## 🛡️ Security Best Practices

### API Key Protection

```bash
# ❌ Wrong - API key in URL
curl "http://localhost:8000/api/v1/decompile?api_key=secret123"

# ✅ Correct - API key in header
curl -H "Authorization: Bearer your-api-key" \
  "http://localhost:8000/api/v1/decompile"
```

### File Validation

```python
import hashlib

def validate_file_before_upload(file_path):
    """Validate file before uploading"""
    # Check file size
    file_size = os.path.getsize(file_path)
    if file_size > 100 * 1024 * 1024:  # 100MB
        raise ValueError("File too large")
    
    # Calculate hash for deduplication
    with open(file_path, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    
    # Check file type
    with open(file_path, 'rb') as f:
        header = f.read(4)
        if not header.startswith((b'MZ', b'\x7fELF')):  # PE or ELF
            raise ValueError("Unsupported file format")
    
    return file_hash
```

## 📊 Performance Optimization

### Concurrent Processing

```python
import asyncio
import aiohttp

async def analyze_binary_async(session, file_path, provider):
    """Async binary analysis"""
    with open(file_path, 'rb') as f:
        data = aiohttp.FormData()
        data.add_field('file', f)
        data.add_field('llm_provider', provider)
        
        async with session.post(
            'http://localhost:8000/api/v1/decompile',
            data=data
        ) as response:
            return await response.json()

async def batch_analyze_concurrent(file_paths, max_concurrent=5):
    """Analyze multiple files concurrently"""
    connector = aiohttp.TCPConnector(limit=max_concurrent)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            analyze_binary_async(session, path, 'gemini') 
            for path in file_paths
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
    return results

# Usage
file_paths = ['file1.exe', 'file2.exe', 'file3.exe']
results = asyncio.run(batch_analyze_concurrent(file_paths))
```

### Caching Results

```python
import redis
import json
import hashlib

class CachedAnalyzer:
    def __init__(self, redis_url="redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        
    def get_file_hash(self, file_path):
        """Get SHA256 hash of file"""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    
    def analyze_with_cache(self, file_path, provider="gemini"):
        """Analyze with result caching"""
        file_hash = self.get_file_hash(file_path)
        cache_key = f"analysis:{file_hash}:{provider}"
        
        # Check cache first
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        # Perform analysis
        result = analyze_binary(file_path, provider)
        
        # Cache result for 1 hour
        self.redis.setex(cache_key, 3600, json.dumps(result))
        
        return result
```

## 🎯 Use Case Examples

### Security Analysis Pipeline

```python
def security_analysis_pipeline(binary_path):
    """Comprehensive security analysis"""
    
    # Stage 1: Quick scan with Gemini for initial classification
    quick_result = analyze_binary(binary_path, provider="gemini")
    
    # Stage 2: Detailed analysis if suspicious
    if "malware" in quick_result['translation_results']['overall_summary']['program_purpose'].lower():
        detailed_result = analyze_binary(binary_path, provider="anthropic")
        return {
            'classification': 'suspicious',
            'quick_analysis': quick_result,
            'detailed_analysis': detailed_result
        }
    
    return {
        'classification': 'benign',
        'analysis': quick_result
    }
```

### Documentation Generation

```python
def generate_binary_documentation(binary_path):
    """Generate technical documentation for binary"""
    
    result = analyze_binary(binary_path, provider="openai")
    
    doc = f"""# Binary Analysis Report
    
## File Information
- **Hash**: {result['decompilation_results']['metadata']['file_hash']}
- **Format**: {result['decompilation_results']['metadata']['file_format'].upper()}
- **Architecture**: {result['decompilation_results']['metadata']['architecture']}

## Program Overview
{result['translation_results']['overall_summary']['program_purpose']}

## Key Functions
"""
    
    for func in result['translation_results']['function_translations']:
        doc += f"""
### {func['function_name']} ({func['function_address']})
**Purpose**: {func['purpose']}

{func['natural_language']}
"""
    
    return doc
```

### Code Quality Assessment

```python
def assess_code_quality(binary_path):
    """Assess code quality and provide recommendations"""
    
    result = analyze_binary(binary_path, provider="anthropic")
    
    quality_indicators = {
        'error_handling': 0,
        'input_validation': 0,
        'security_practices': 0,
        'code_organization': 0
    }
    
    # Analyze function descriptions for quality indicators
    for func in result['translation_results']['function_translations']:
        description = func['natural_language'].lower()
        
        if 'error' in description and 'handling' in description:
            quality_indicators['error_handling'] += 1
        if 'validation' in description or 'validate' in description:
            quality_indicators['input_validation'] += 1
        if 'security' in description or 'encrypt' in description:
            quality_indicators['security_practices'] += 1
    
    return {
        'quality_score': sum(quality_indicators.values()) / len(quality_indicators),
        'indicators': quality_indicators,
        'recommendations': [
            "Implement proper input validation" if quality_indicators['input_validation'] < 2 else None,
            "Add comprehensive error handling" if quality_indicators['error_handling'] < 2 else None,
            "Enhance security measures" if quality_indicators['security_practices'] < 1 else None
        ]
    }
```

## 🔍 Monitoring and Debugging

### Request Logging

```bash
# Enable detailed request logging
curl -X POST "http://localhost:8000/api/v1/decompile" \
  -H "X-Debug: true" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@debug_sample.exe" \
  -F "llm_provider=openai"
```

### Performance Monitoring

```python
import time

def monitored_analysis(file_path, provider="openai"):
    """Analysis with performance monitoring"""
    start_time = time.time()
    
    try:
        result = analyze_binary(file_path, provider)
        
        # Log successful analysis
        print(f"✅ Analysis successful")
        print(f"   Provider: {provider}")
        print(f"   Total time: {time.time() - start_time:.2f}s")
        print(f"   Tokens used: {result['translation_results']['total_tokens_used']}")
        print(f"   Cost: ${result['translation_results']['estimated_cost']:.3f}")
        
        return result
        
    except Exception as e:
        print(f"❌ Analysis failed after {time.time() - start_time:.2f}s")
        print(f"   Error: {e}")
        raise
```

---

## 📚 Additional Resources

- **OpenAPI Documentation**: http://localhost:8000/docs
- **Provider Comparison**: [LLM_PROVIDER_GUIDE.md](./LLM_PROVIDER_GUIDE.md)
- **Performance Benchmarks**: [BENCHMARKS.md](./BENCHMARKS.md)
- **Troubleshooting Guide**: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

For more examples and community contributions, visit our [GitHub Examples Repository](https://github.com/your-org/bin2nlp-examples).

*Last updated: 2025-08-18*