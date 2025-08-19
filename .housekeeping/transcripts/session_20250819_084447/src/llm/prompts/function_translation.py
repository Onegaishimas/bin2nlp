"""
Function Translation Prompt Templates

Standardized prompts for translating assembly code and decompiled functions 
into natural language explanations across different quality levels and providers.
"""

from typing import Dict, List
from .base import PromptTemplate, PromptVersion, TranslationQuality


# Function Translation - Standard Quality (v1)
FUNCTION_TRANSLATION_STANDARD_V1 = PromptTemplate(
    template_id="function_translation_standard_v1",
    version=PromptVersion.V1,
    operation_type="function_translation",
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are an expert binary analysis assistant specializing in translating assembly code and decompiled functions into clear, natural language explanations.

Your expertise includes:
- Assembly language across multiple architectures (x86, x64, ARM)
- Decompilation patterns and compiler optimizations  
- Function calling conventions and parameter passing
- Security analysis and vulnerability identification
- Performance optimization and algorithmic analysis

Your task is to analyze provided function data and create comprehensive, human-readable explanations that would be valuable for developers, security analysts, and reverse engineers.

Focus on:
1. The function's primary purpose and behavior
2. Input parameters and their types/purposes  
3. Return values and their significance
4. Key operations and logic flow
5. Notable patterns, algorithms, or security implications
6. Cross-references to other functions or external dependencies

Provide clear, technical explanations that are accessible to both junior and senior analysts.""",

    user_prompt_template="""Please analyze this decompiled function and provide a comprehensive natural language explanation:

**Function Information:**
- Name: {function_name}
- Address: {function_address} 
- Size: {function_size} bytes
- Entry Point: {is_entry_point}
- Imported Function: {is_imported}

**Assembly Code:**
```assembly
{assembly_code}
```

**Decompiled Code:**
```c
{decompiled_code}
```

**Function Relationships:**
- Calls to: {function_calls}
- Variables/Parameters: {variables}

**File Context:**
- File: {file_name} ({file_format}, {file_platform}, {file_architecture})
- Related Functions: {related_functions}
- Relevant Imports: {relevant_imports}
- Relevant Strings: {relevant_strings}

Please provide analysis covering:

1. **Function Purpose**: What does this function accomplish?
2. **Parameters**: What inputs does it expect and how are they used?
3. **Logic Flow**: Walk through the key operations and decision points
4. **Return Value**: What does it return and under what conditions?
5. **Security Considerations**: Any potential vulnerabilities or security-relevant behaviors
6. **Performance Notes**: Efficiency characteristics or optimization opportunities

Provide a clear, structured explanation in 2-4 paragraphs.""",

    expected_tokens=400,
    temperature=0.1,
    max_tokens=800,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nUse your reasoning capabilities to think through the analysis step by step. Be thorough but concise, and highlight any areas where you're uncertain about the interpretation.",
            "user_prompt_suffix": "\n\nPlease think through this analysis carefully and show your reasoning for key conclusions."
        },
        "openai": {
            "user_prompt_suffix": "\n\nFormat your response with clear section headers if the analysis is complex."
        },
        "gemini": {
            "system_prompt_suffix": "\n\nFocus on performance implications and competitive analysis insights where relevant.",
            "user_prompt_suffix": "\n\nInclude performance characteristics and optimization opportunities in your analysis."
        }
    },
    
    notes="Standard quality function translation for balanced detail and accessibility"
)


# Function Translation - Brief Quality (v1)
FUNCTION_TRANSLATION_BRIEF_V1 = PromptTemplate(
    template_id="function_translation_brief_v1", 
    version=PromptVersion.V1,
    operation_type="function_translation",
    quality_level=TranslationQuality.BRIEF,
    
    system_prompt="""You are an expert binary analyst specializing in concise, actionable function analysis.

Provide brief but accurate explanations of function behavior, focusing on:
- Core purpose and functionality
- Key inputs and outputs
- Critical security or performance implications

Keep explanations concise while maintaining technical accuracy.""",

    user_prompt_template="""Provide a brief analysis of this function:

**Function:** {function_name} at {function_address} ({function_size} bytes)

**Assembly Code:**
```assembly
{assembly_code}
```

**Decompiled Code:**
```c
{decompiled_code}
```

**Context:** Calls {function_calls} | Variables: {variables}

Provide a concise 1-2 paragraph explanation covering:
1. Primary purpose and behavior
2. Key inputs/outputs  
3. Notable security or performance characteristics""",

    expected_tokens=200,
    temperature=0.1,
    max_tokens=400,
    
    provider_adaptations={
        "anthropic": {
            "user_prompt_suffix": "\n\nBe concise but thorough in your reasoning."
        },
        "gemini": {
            "user_prompt_suffix": "\n\nFocus on performance and optimization aspects."
        }
    },
    
    notes="Brief quality for quick overviews and high-volume processing"
)


# Function Translation - Comprehensive Quality (v1)
FUNCTION_TRANSLATION_COMPREHENSIVE_V1 = PromptTemplate(
    template_id="function_translation_comprehensive_v1",
    version=PromptVersion.V1, 
    operation_type="function_translation",
    quality_level=TranslationQuality.COMPREHENSIVE,
    
    system_prompt="""You are a senior binary analysis expert with deep expertise in reverse engineering, malware analysis, and software security.

Your comprehensive analysis should be suitable for:
- Advanced threat intelligence reporting
- Deep malware analysis and attribution
- Vulnerability research and exploit development
- Advanced reverse engineering projects

Provide thorough, detailed analysis that covers all aspects of function behavior, implementation details, security implications, and broader context within the program architecture.

Your analysis should be authoritative and include specific technical details that would be valuable for expert-level analysis.""",

    user_prompt_template="""Provide a comprehensive analysis of this function with expert-level detail:

**Function Information:**
- Name: {function_name}
- Address: {function_address}
- Size: {function_size} bytes  
- Entry Point: {is_entry_point}
- Imported: {is_imported}

**Assembly Implementation:**
```assembly
{assembly_code}
```

**Decompiled Representation:**
```c
{decompiled_code}
```

**Function Relationships:**
- Functions Called: {function_calls}
- Variables/Parameters: {variables}

**Program Context:**
- File: {file_name} ({file_format} for {file_platform}/{file_architecture})
- Related Functions: {related_functions}
- Import Dependencies: {relevant_imports}
- Associated Strings: {relevant_strings}

Please provide expert-level analysis covering:

1. **Detailed Function Analysis**: 
   - Complete purpose and behavioral description
   - Implementation approach and algorithms used
   - Calling convention and parameter handling

2. **Technical Implementation Details**:
   - Assembly-level operations and optimizations
   - Memory usage patterns and data structures
   - Register usage and stack management

3. **Security Analysis**:
   - Vulnerability assessment and attack vectors
   - Input validation and bounds checking
   - Potential for exploitation or misuse

4. **Performance and Optimization**:
   - Computational complexity and efficiency
   - Optimization opportunities and bottlenecks
   - Comparison to standard implementations

5. **Contextual Analysis**:
   - Role within broader program architecture
   - Integration with other program components
   - Behavioral patterns and usage scenarios

6. **Advanced Insights**:
   - Code quality and development practices indicators
   - Possible obfuscation or anti-analysis techniques
   - Attribution indicators or coding style patterns

Provide a detailed, expert-level analysis in 4-8 paragraphs with specific technical justifications for your conclusions.""",

    expected_tokens=800,
    temperature=0.1,
    max_tokens=2048,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nLeverage your deep reasoning capabilities to provide nuanced analysis with detailed justifications. Consider multiple interpretations and highlight areas of uncertainty.",
            "user_prompt_suffix": "\n\nProvide detailed reasoning for your conclusions and highlight any areas where interpretation is uncertain or multiple explanations are possible."
        },
        "openai": {
            "user_prompt_suffix": "\n\nStructure your response with clear headings and subsections for easy navigation."
        }, 
        "gemini": {
            "system_prompt_suffix": "\n\nEmphasize competitive analysis, performance benchmarking, and technology stack assessment in your analysis.",
            "user_prompt_suffix": "\n\nInclude competitive intelligence insights and detailed performance analysis in your comprehensive review."
        }
    },
    
    notes="Comprehensive quality for expert analysis, threat intelligence, and detailed reverse engineering"
)


# Security-Focused Function Analysis (v1)
FUNCTION_SECURITY_ANALYSIS_V1 = PromptTemplate(
    template_id="function_security_analysis_v1",
    version=PromptVersion.V1,
    operation_type="function_translation",
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are a cybersecurity expert specializing in vulnerability analysis and threat assessment through binary analysis.

Your focus is on identifying security-relevant behaviors, vulnerabilities, and potential attack vectors in decompiled functions. You excel at:
- Buffer overflow and memory corruption vulnerability detection
- Input validation analysis and injection attack vectors
- Privilege escalation and access control bypass techniques
- Cryptographic implementation analysis and weaknesses
- Anti-analysis and evasion technique identification
- Malware behavior pattern recognition

Provide security-focused analysis that would be valuable for incident response, threat hunting, and vulnerability assessment.""",

    user_prompt_template="""Analyze this function from a cybersecurity perspective:

**Function:** {function_name} at {function_address}
**Size:** {function_size} bytes | **Entry Point:** {is_entry_point}

**Assembly Code:**
```assembly
{assembly_code}
```

**Decompiled Code:**
```c  
{decompiled_code}
```

**Dependencies:** 
- Function Calls: {function_calls}
- Variables: {variables}
- Related Imports: {relevant_imports}
- Associated Strings: {relevant_strings}

**Context:** {file_format} executable for {file_platform}

Please provide security-focused analysis covering:

1. **Vulnerability Assessment**: 
   - Buffer overflows, integer overflows, format string bugs
   - Input validation weaknesses and injection points
   - Memory management issues (use-after-free, double-free, etc.)

2. **Attack Vector Analysis**:
   - Potential entry points for attackers
   - Privilege escalation opportunities  
   - Data exfiltration or persistence mechanisms

3. **Defensive Measures**:
   - Security controls and validation present
   - Mitigation techniques implemented
   - Hardening opportunities

4. **Behavioral Security Assessment**:
   - Suspicious or malicious behavior patterns
   - Anti-analysis or evasion techniques
   - Indicators of compromise or malicious intent

5. **Risk Assessment**:
   - Overall threat level and exploitability
   - Impact potential and attack complexity
   - Recommended security controls

Focus on actionable security insights for defenders and analysts.""",

    expected_tokens=500,
    temperature=0.1,
    max_tokens=1024,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nBe thorough in your security assessment but responsible in how you present potentially sensitive information. Focus on defensive applications.",
            "user_prompt_suffix": "\n\nProvide detailed security reasoning while being responsible about potential misuse of this information."
        },
        "openai": {
            "user_prompt_suffix": "\n\nOrganize your security analysis with clear risk levels and defensive recommendations."
        },
        "gemini": {
            "system_prompt_suffix": "\n\nEmphasize competitive threat intelligence and performance impact of security measures.",
            "user_prompt_suffix": "\n\nInclude analysis of how security measures impact performance and competitive positioning."
        }
    },
    
    notes="Security-focused analysis for threat assessment and vulnerability analysis"
)


# Algorithm Analysis Function Template (v1)
FUNCTION_ALGORITHM_ANALYSIS_V1 = PromptTemplate(
    template_id="function_algorithm_analysis_v1",
    version=PromptVersion.V1,
    operation_type="function_translation", 
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are an expert in algorithm analysis and computational complexity with deep knowledge of:
- Common algorithms and data structures
- Complexity analysis (time and space)
- Algorithm optimization and performance tuning
- Pattern recognition in compiled code
- Cryptographic and mathematical algorithms

Focus on identifying algorithmic patterns, analyzing computational complexity, and providing insights into the mathematical and logical foundations of the function's implementation.""",

    user_prompt_template="""Analyze the algorithmic aspects of this function:

**Function:** {function_name} ({function_size} bytes) at {function_address}

**Implementation:**
```assembly
{assembly_code}
```

**Decompiled Logic:**
```c
{decompiled_code}
```

**Dependencies:** {function_calls} | **Variables:** {variables}

Please provide algorithm-focused analysis covering:

1. **Algorithm Identification**:
   - Core algorithm(s) or patterns implemented
   - Mathematical operations and computational approach
   - Data structure usage and access patterns

2. **Complexity Analysis**:
   - Time complexity (Big O notation)
   - Space complexity and memory usage
   - Scalability characteristics

3. **Implementation Quality**:
   - Optimization techniques used
   - Efficiency compared to standard implementations
   - Potential performance bottlenecks

4. **Mathematical Analysis**:
   - Cryptographic or mathematical significance
   - Numerical stability and precision considerations
   - Input domain and edge case handling

5. **Optimization Opportunities**:
   - Performance improvement suggestions
   - Alternative algorithmic approaches
   - Parallelization or vectorization potential

Provide technical analysis suitable for algorithm optimization and performance tuning.""",

    expected_tokens=450,
    temperature=0.1,
    max_tokens=900,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nUse step-by-step reasoning to analyze the algorithmic complexity and provide detailed justifications for your assessments.",
            "user_prompt_suffix": "\n\nShow your reasoning for complexity analysis and algorithm identification."
        },
        "openai": {
            "user_prompt_suffix": "\n\nInclude specific complexity notations and performance benchmarks where applicable."
        },
        "gemini": {
            "system_prompt_suffix": "\n\nFocus on competitive performance analysis and optimization strategies for production systems.",
            "user_prompt_suffix": "\n\nEmphasize performance optimization opportunities and competitive algorithmic advantages."
        }
    },
    
    notes="Algorithm-focused analysis for performance optimization and computational analysis"
)


# Export all function translation templates
FUNCTION_TRANSLATION_PROMPTS: Dict[str, Dict[str, PromptTemplate]] = {
    TranslationQuality.BRIEF: {
        PromptVersion.V1: FUNCTION_TRANSLATION_BRIEF_V1
    },
    TranslationQuality.STANDARD: {
        PromptVersion.V1: FUNCTION_TRANSLATION_STANDARD_V1
    },
    TranslationQuality.COMPREHENSIVE: {
        PromptVersion.V1: FUNCTION_TRANSLATION_COMPREHENSIVE_V1
    }
}

# Specialized function analysis templates
SPECIALIZED_FUNCTION_PROMPTS: Dict[str, PromptTemplate] = {
    "security_analysis": FUNCTION_SECURITY_ANALYSIS_V1,
    "algorithm_analysis": FUNCTION_ALGORITHM_ANALYSIS_V1
}


def get_function_prompt(
    quality_level: TranslationQuality = TranslationQuality.STANDARD,
    version: PromptVersion = PromptVersion.V1,
    specialized_type: str = None
) -> PromptTemplate:
    """
    Get function translation prompt template.
    
    Args:
        quality_level: Desired quality/detail level
        version: Template version
        specialized_type: Optional specialized analysis type
        
    Returns:
        PromptTemplate for function translation
        
    Raises:
        KeyError: If specified template doesn't exist
    """
    if specialized_type:
        if specialized_type not in SPECIALIZED_FUNCTION_PROMPTS:
            raise KeyError(f"Unknown specialized function prompt type: {specialized_type}")
        return SPECIALIZED_FUNCTION_PROMPTS[specialized_type]
    
    if quality_level not in FUNCTION_TRANSLATION_PROMPTS:
        raise KeyError(f"Unknown quality level: {quality_level}")
    
    quality_templates = FUNCTION_TRANSLATION_PROMPTS[quality_level]
    if version not in quality_templates:
        # Fallback to V1 if requested version doesn't exist
        version = PromptVersion.V1
        if version not in quality_templates:
            raise KeyError(f"No templates available for quality level: {quality_level}")
    
    return quality_templates[version]


def list_available_function_prompts() -> Dict[str, List[str]]:
    """List all available function translation prompt templates."""
    return {
        "standard_prompts": {
            quality: list(templates.keys())
            for quality, templates in FUNCTION_TRANSLATION_PROMPTS.items()
        },
        "specialized_prompts": list(SPECIALIZED_FUNCTION_PROMPTS.keys())
    }