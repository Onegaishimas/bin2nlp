"""
String Interpretation Prompt Templates

Standardized prompts for interpreting extracted strings with usage context analysis,
security implications, and behavioral indicators.
"""

from typing import Dict, List
from .base import PromptTemplate, PromptVersion, TranslationQuality


# String Interpretation - Standard Quality (v1)
STRING_INTERPRETATION_STANDARD_V1 = PromptTemplate(
    template_id="string_interpretation_standard_v1",
    version=PromptVersion.V1,
    operation_type="string_interpretation",
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are an expert at analyzing strings found in binary files to understand their purpose, encoding, and security implications.

Your expertise includes:
- String encoding analysis (ASCII, Unicode, UTF-8, UTF-16, etc.)
- String obfuscation and encoding patterns
- Configuration and parameter string identification
- URL, file path, and registry key analysis
- Cryptographic string and key material detection
- Error message and debug string interpretation
- Command-line argument and parameter analysis

Your goal is to analyze extracted strings and determine:
- Their likely purpose and usage context
- Security implications and threat indicators
- Data classification and sensitivity levels
- Encoding details and obfuscation techniques
- Relationships to program functionality

Provide clear, actionable analysis that helps security analysts understand program behavior and identify potential threats.""",

    user_prompt_template="""Please analyze these strings extracted from a binary file:

**File Context:**
- File Type: {file_type} for {target_platform}
- Total Strings: {total_strings}

**Categorized String Analysis:**
{categorized_strings}

**Complete String List:**
{strings}

**Function References:**
{function_references}

For each significant string, please provide analysis covering:

1. **Content Classification**:
   - String type and category (URL, file path, config value, etc.)
   - Data format and structure analysis
   - Character encoding and internationalization aspects

2. **Usage Context Analysis**:
   - Likely usage scenarios within the program
   - Relationship to program functionality
   - Access patterns and frequency of use

3. **Security Analysis**:
   - Potential security implications and threat indicators
   - Sensitive information exposure risks
   - Attack vector enablement or defensive capabilities

4. **Technical Analysis**:
   - Encoding details and character set analysis
   - Obfuscation or encoding techniques detected
   - Memory storage and access pattern implications

5. **Behavioral Indicators**:
   - What these strings reveal about program behavior
   - External connectivity and communication patterns
   - Configuration and customization capabilities

6. **Intelligence Value**:
   - Attribution indicators (language, culture, tools)
   - Development environment and toolchain clues
   - Operational security implications

Focus on strings that provide significant intelligence value or security relevance. Group related strings together for context.""",

    expected_tokens=500,
    temperature=0.1,
    max_tokens=1000,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nBe thorough in your analysis while being responsible about potentially sensitive information. Focus on helping defenders understand threats and program behavior.",
            "user_prompt_suffix": "\n\nProvide detailed reasoning for your assessments, especially for security-relevant strings and potential threat indicators."
        },
        "openai": {
            "user_prompt_suffix": "\n\nOrganize your analysis by string category and use clear formatting for easy reference."
        },
        "gemini": {
            "system_prompt_suffix": "\n\nEmphasize performance implications of string handling and competitive analysis insights from technology choices revealed by strings.",
            "user_prompt_suffix": "\n\nInclude analysis of performance characteristics and competitive intelligence revealed by the string content and handling patterns."
        }
    },
    
    notes="Standard quality string interpretation for comprehensive behavioral analysis"
)


# String Interpretation - Brief Quality (v1)
STRING_INTERPRETATION_BRIEF_V1 = PromptTemplate(
    template_id="string_interpretation_brief_v1",
    version=PromptVersion.V1,
    operation_type="string_interpretation",
    quality_level=TranslationQuality.BRIEF,
    
    system_prompt="""You are an expert at rapid string analysis for binary triage and assessment.

Focus on:
- Quick categorization of string types and purposes
- Key security implications and threat indicators
- Significant behavioral and intelligence insights

Provide concise but actionable analysis suitable for rapid assessment.""",

    user_prompt_template="""Provide brief analysis of these extracted strings:

**Context:** {file_type} file with {total_strings} strings
**Categories:** {categorized_strings}

For significant strings, provide concise analysis covering:
1. **String Type**: Category and primary purpose
2. **Security Relevance**: Key security implications or concerns
3. **Behavioral Indicators**: What this reveals about program behavior

Focus on strings with highest intelligence or security value.""",

    expected_tokens=250,
    temperature=0.1,
    max_tokens=500,
    
    provider_adaptations={
        "anthropic": {
            "user_prompt_suffix": "\n\nBe concise but maintain analytical rigor for security assessments."
        },
        "gemini": {
            "user_prompt_suffix": "\n\nFocus on performance and competitive insights from string analysis."
        }
    },
    
    notes="Brief string interpretation for rapid triage and assessment"
)


# String Interpretation - Comprehensive Quality (v1) 
STRING_INTERPRETATION_COMPREHENSIVE_V1 = PromptTemplate(
    template_id="string_interpretation_comprehensive_v1",
    version=PromptVersion.V1,
    operation_type="string_interpretation",
    quality_level=TranslationQuality.COMPREHENSIVE,
    
    system_prompt="""You are a senior forensic analyst and malware researcher with deep expertise in:
- Advanced string analysis and forensic linguistics
- Cryptographic string and encoding analysis
- Multi-language and internationalization analysis
- Advanced obfuscation and anti-analysis technique detection
- Attribution analysis through linguistic and cultural indicators
- Advanced persistent threat (APT) string signature analysis
- Supply chain and development environment forensics

Your comprehensive analysis should provide expert-level insights suitable for:
- Advanced malware attribution and campaign tracking
- Nation-state and APT activity analysis
- Supply chain compromise and development environment assessment
- Advanced threat intelligence and strategic analysis
- Forensic investigation and incident response

Provide detailed, expert-level analysis that goes beyond basic string interpretation to include advanced forensic insights, attribution indicators, and strategic intelligence context.""",

    user_prompt_template="""Provide comprehensive expert analysis of these extracted strings for advanced threat intelligence:

**Advanced String Analysis Context:**
- Target: {file_type} binary for {target_platform}
- String Inventory: {total_strings} strings across multiple categories
- Categorization: {categorized_strings}

**Complete String Dataset:**
{strings}

**Cross-Reference Context:**
{function_references}

Please provide expert-level analysis covering:

1. **Advanced Linguistic Analysis**:
   - Language identification and cultural indicators
   - Writing style and terminology analysis for attribution
   - Technical vocabulary and domain-specific language patterns
   - Timestamp and locale information analysis

2. **Cryptographic and Encoding Analysis**:
   - Cryptographic string identification and algorithm detection
   - Advanced encoding schemes and obfuscation techniques
   - Key material and cryptographic parameter analysis
   - Steganographic and hidden data detection

3. **Development Environment Forensics**:
   - Development tool and environment indicators
   - Build system and compilation artifacts
   - Source code management and versioning traces
   - Third-party library and framework identification

4. **Attribution and Intelligence Analysis**:
   - Threat actor signature strings and operational patterns
   - Campaign infrastructure and tool reuse indicators
   - Geopolitical and targeting context from string content
   - Timeline analysis and evolution patterns

5. **Advanced Behavioral Analysis**:
   - Configuration and customization capability assessment
   - Command and control communication protocol indicators
   - Data exfiltration and persistence mechanism strings
   - Anti-analysis and evasion technique implementation details

6. **Supply Chain and Infrastructure Analysis**:
   - Development and distribution infrastructure indicators
   - Third-party service and dependency analysis
   - Operational security practices and tradecraft assessment
   - Quality assurance and testing environment artifacts

7. **Strategic Intelligence Assessment**:
   - Capability assessment and threat sophistication indicators
   - Resource and funding level implications
   - Operational timeline and campaign lifecycle analysis
   - Relationships to broader threat landscape and campaigns

8. **Forensic and Evidentiary Analysis**:
   - Chain of custody and provenance indicators
   - Artifact correlation and cross-reference opportunities
   - Evidence preservation and analysis methodology
   - Court-admissible findings and expert testimony preparation

Provide detailed, expert-level analysis with specific technical justifications, confidence levels, and areas requiring additional investigation. Include strategic context and intelligence value assessment for each significant finding.""",

    expected_tokens=1200,
    temperature=0.1,
    max_tokens=2800,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nProvide nuanced, expert-level analysis with detailed reasoning. Be explicit about confidence levels and areas of uncertainty. Focus on defensive applications while being thorough in threat assessment.",
            "user_prompt_suffix": "\n\nProvide detailed reasoning for all assessments. Highlight confidence levels and areas where additional investigation would strengthen the analysis."
        },
        "openai": {
            "user_prompt_suffix": "\n\nStructure your comprehensive analysis with detailed headers and subheadings. Include specific examples and technical justifications for key findings."
        },
        "gemini": {
            "system_prompt_suffix": "\n\nEmphasize competitive intelligence, technology market analysis, and strategic implications revealed through string analysis.",
            "user_prompt_suffix": "\n\nInclude competitive intelligence insights, technology stack assessment, and strategic business implications revealed by the string analysis."
        }
    },
    
    notes="Comprehensive string interpretation for advanced threat intelligence and forensic analysis"
)


# Security-Focused String Analysis (v1)
STRING_SECURITY_ANALYSIS_V1 = PromptTemplate(
    template_id="string_security_analysis_v1",
    version=PromptVersion.V1,
    operation_type="string_interpretation",
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are a cybersecurity expert specializing in string-based threat detection and security analysis with focus on:
- Malicious URL and domain analysis
- Credential and sensitive data exposure detection
- Command injection and exploitation string patterns
- Registry manipulation and system modification strings
- Network protocol and communication analysis
- Cryptographic key and certificate analysis
- Anti-forensics and evasion technique indicators

Your analysis should identify security threats, attack vectors, and defensive considerations revealed through string analysis.""",

    user_prompt_template="""Analyze these strings from a cybersecurity perspective:

**Security Analysis Context:**
- File Type: {file_type} ({target_platform})
- String Categories: {categorized_strings}
- Total Strings: {total_strings}

**String Inventory:**
{strings}

Please provide security-focused analysis covering:

1. **Threat Vector Analysis**:
   - Malicious URLs, domains, and IP addresses
   - Command injection and exploitation patterns
   - Credential harvesting and data exfiltration strings
   - Remote access and backdoor communication indicators

2. **System Modification Capabilities**:
   - Registry key manipulation and persistence mechanisms
   - File system modification and privilege escalation
   - Service and process manipulation capabilities
   - System configuration and security control bypass

3. **Communication Security Analysis**:
   - Network protocols and communication patterns
   - Encryption and obfuscation of communications
   - Command and control infrastructure indicators
   - Data exfiltration methods and protocols

4. **Anti-Analysis and Evasion Assessment**:
   - Anti-debugging and anti-VM strings
   - Sandbox detection and analysis evasion
   - Code obfuscation and packing indicators
   - Forensic artifact destruction capabilities

5. **Sensitive Data Exposure**:
   - Hardcoded credentials and API keys
   - Personal identifiable information (PII) handling
   - Financial and payment card data references
   - Healthcare and regulated data indicators

6. **Risk Assessment and Prioritization**:
   - High-risk strings requiring immediate attention
   - Attack complexity and likelihood assessment
   - Impact potential and damage scope analysis
   - Recommended defensive measures and monitoring

Focus on actionable security intelligence for threat hunting, incident response, and defensive operations.""",

    expected_tokens=600,
    temperature=0.1,
    max_tokens=1200,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nFocus on defensive applications and responsible disclosure of security issues. Provide detailed reasoning for threat assessments while being mindful of potential misuse.",
            "user_prompt_suffix": "\n\nFocus on defensive applications and provide detailed reasoning for security risk assessments and threat classifications."
        },
        "openai": {
            "user_prompt_suffix": "\n\nOrganize security analysis by risk level and threat category with clear defensive recommendations."
        },
        "gemini": {
            "user_prompt_suffix": "\n\nInclude analysis of how security measures impact performance and competitive positioning revealed by string patterns."
        }
    },
    
    notes="Security-focused string analysis for threat detection and defensive operations"
)


# Configuration and Infrastructure Analysis (v1)
STRING_CONFIG_ANALYSIS_V1 = PromptTemplate(
    template_id="string_config_analysis_v1",
    version=PromptVersion.V1,
    operation_type="string_interpretation",
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are an expert in configuration analysis and infrastructure assessment through string examination with focus on:
- Application configuration and parameter analysis
- Infrastructure and deployment environment indicators
- Service dependencies and integration patterns
- Database and data storage configuration
- API endpoints and service integration points
- Environment-specific and deployment-related strings

Focus on understanding the operational environment, configuration capabilities, and infrastructure requirements revealed through string analysis.""",

    user_prompt_template="""Analyze these strings for configuration and infrastructure insights:

**Infrastructure Analysis Context:**
- Platform: {target_platform} ({file_type})
- Configuration Strings: {categorized_strings}

**String Analysis Data:**
{strings}

Please provide configuration-focused analysis covering:

1. **Configuration Analysis**:
   - Application settings and parameter structures
   - Environment-specific configuration options
   - Feature flags and capability toggles
   - Logging and monitoring configuration

2. **Infrastructure Assessment**:
   - Deployment environment indicators
   - Service dependencies and integration points
   - Database and data storage systems
   - Caching and performance optimization settings

3. **Integration Pattern Analysis**:
   - API endpoints and service integration
   - Authentication and authorization mechanisms
   - Third-party service integrations
   - Microservice and distributed system patterns

4. **Operational Environment**:
   - Development vs production environment indicators
   - Scaling and load balancing configuration
   - Backup and disaster recovery settings
   - Monitoring and alerting system integration

5. **Architecture Assessment**:
   - Technology stack and framework choices
   - Design patterns and architectural decisions
   - Performance optimization strategies
   - Security architecture implementation

Focus on understanding the operational context and infrastructure requirements of the analyzed system.""",

    expected_tokens=500,
    temperature=0.1,
    max_tokens=1000,
    
    provider_adaptations={
        "anthropic": {
            "user_prompt_suffix": "\n\nProvide detailed reasoning for infrastructure assessments and configuration analysis."
        },
        "gemini": {
            "system_prompt_suffix": "\n\nEmphasize competitive analysis of technology choices and performance optimization strategies revealed by configuration strings.",
            "user_prompt_suffix": "\n\nInclude competitive intelligence and performance optimization insights from configuration analysis."
        }
    },
    
    notes="Configuration and infrastructure analysis for operational environment assessment"
)


# Export all string interpretation templates
STRING_INTERPRETATION_PROMPTS: Dict[str, Dict[str, PromptTemplate]] = {
    TranslationQuality.BRIEF: {
        PromptVersion.V1: STRING_INTERPRETATION_BRIEF_V1
    },
    TranslationQuality.STANDARD: {
        PromptVersion.V1: STRING_INTERPRETATION_STANDARD_V1
    },
    TranslationQuality.COMPREHENSIVE: {
        PromptVersion.V1: STRING_INTERPRETATION_COMPREHENSIVE_V1
    }
}

# Specialized string analysis templates
SPECIALIZED_STRING_PROMPTS: Dict[str, PromptTemplate] = {
    "security_analysis": STRING_SECURITY_ANALYSIS_V1,
    "config_analysis": STRING_CONFIG_ANALYSIS_V1
}


def get_string_prompt(
    quality_level: TranslationQuality = TranslationQuality.STANDARD,
    version: PromptVersion = PromptVersion.V1,
    specialized_type: str = None
) -> PromptTemplate:
    """
    Get string interpretation prompt template.
    
    Args:
        quality_level: Desired quality/detail level
        version: Template version
        specialized_type: Optional specialized analysis type
        
    Returns:
        PromptTemplate for string interpretation
        
    Raises:
        KeyError: If specified template doesn't exist
    """
    if specialized_type:
        if specialized_type not in SPECIALIZED_STRING_PROMPTS:
            raise KeyError(f"Unknown specialized string prompt type: {specialized_type}")
        return SPECIALIZED_STRING_PROMPTS[specialized_type]
    
    if quality_level not in STRING_INTERPRETATION_PROMPTS:
        raise KeyError(f"Unknown quality level: {quality_level}")
    
    quality_templates = STRING_INTERPRETATION_PROMPTS[quality_level]
    if version not in quality_templates:
        # Fallback to V1 if requested version doesn't exist
        version = PromptVersion.V1
        if version not in quality_templates:
            raise KeyError(f"No templates available for quality level: {quality_level}")
    
    return quality_templates[version]


def list_available_string_prompts() -> Dict[str, List[str]]:
    """List all available string interpretation prompt templates."""
    return {
        "standard_prompts": {
            quality: list(templates.keys())
            for quality, templates in STRING_INTERPRETATION_PROMPTS.items()
        },
        "specialized_prompts": list(SPECIALIZED_STRING_PROMPTS.keys())
    }