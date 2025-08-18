"""
Import Explanation Prompt Templates

Standardized prompts for explaining imported functions and libraries with 
API documentation context, security analysis, and usage patterns.
"""

from typing import Dict, List
from .base import PromptTemplate, PromptVersion, TranslationQuality


# Import Explanation - Standard Quality (v1)
IMPORT_EXPLANATION_STANDARD_V1 = PromptTemplate(
    template_id="import_explanation_standard_v1",
    version=PromptVersion.V1,
    operation_type="import_explanation",
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are an expert in system APIs and library functions across Windows, Linux, and macOS platforms with comprehensive knowledge of:
- System API documentation and functionality
- Common usage patterns and best practices  
- Security implications and potential vulnerabilities
- Library dependencies and version considerations
- Cross-platform API equivalents and differences

Your role is to analyze imported functions and provide clear, actionable explanations that help security analysts, reverse engineers, and developers understand:
- What each imported function does
- How it's typically used in applications
- Security considerations and potential risks
- Legitimate vs suspicious usage patterns

Focus on practical information that enables effective threat analysis and code understanding.""",

    user_prompt_template="""Please analyze these imported functions and provide comprehensive explanations:

**Import Analysis Context:**
- Total imports: {import_count}
- Unique libraries: {unique_libraries}
- Target platform: {file_platform} ({target_architecture})
- File format: {file_format}

**Imported Functions by Library:**
{imports_by_library}

**Complete Import List:**
{imports}

**Usage Context:**
{usage_patterns}

For each imported function, please provide analysis covering:

1. **API Documentation Summary**:
   - Official purpose and core functionality
   - Parameters, return values, and calling conventions
   - API category and system integration role

2. **Common Usage Patterns**:
   - Typical application scenarios and use cases
   - Best practices and recommended implementations
   - Common parameter combinations and configurations

3. **Security Analysis**:
   - Security implications and potential vulnerabilities
   - Input validation requirements and attack vectors
   - Permission and privilege requirements

4. **Behavioral Analysis**:
   - Observable system behaviors and side effects
   - Resource consumption and performance characteristics
   - Error conditions and failure modes

5. **Context Assessment**:
   - Legitimate vs potentially suspicious usage patterns
   - Red flags that might indicate malicious intent
   - Relationships with other APIs in the import list

6. **Alternative APIs**:
   - Similar or equivalent functions
   - Modern alternatives or deprecated warnings
   - Cross-platform equivalents

Organize your analysis by library, then by function within each library. Focus on actionable intelligence for security analysis.""",

    expected_tokens=600,
    temperature=0.1,
    max_tokens=1200,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nUse your knowledge responsibly, focusing on defensive applications and helping analysts understand threats. Be thorough in your security analysis while being mindful of how the information could be misused.",
            "user_prompt_suffix": "\n\nProvide detailed reasoning for your security assessments and highlight areas where you have high vs lower confidence in your analysis."
        },
        "openai": {
            "user_prompt_suffix": "\n\nStructure your response with clear sections for each library and use consistent formatting for easy reference."
        },
        "gemini": {
            "system_prompt_suffix": "\n\nEmphasize performance implications, competitive analysis of API choices, and technology stack assessment in your explanations.",
            "user_prompt_suffix": "\n\nInclude analysis of performance characteristics and competitive advantages/disadvantages of the API choices."
        }
    },
    
    notes="Standard quality import analysis for comprehensive API understanding"
)


# Import Explanation - Brief Quality (v1) 
IMPORT_EXPLANATION_BRIEF_V1 = PromptTemplate(
    template_id="import_explanation_brief_v1",
    version=PromptVersion.V1,
    operation_type="import_explanation", 
    quality_level=TranslationQuality.BRIEF,
    
    system_prompt="""You are an expert in system APIs providing concise, actionable analysis of imported functions.

Focus on:
- Core functionality and purpose of each API
- Key security implications 
- Legitimate vs suspicious usage indicators

Provide brief but accurate assessments suitable for rapid triage and analysis.""",

    user_prompt_template="""Provide brief analysis of these imported functions:

**Libraries:** {unique_libraries}
**Platform:** {file_platform} ({file_format})
**Imports:** {imports}

For each import, provide concise analysis covering:
1. **Core Function**: Primary purpose and functionality
2. **Security Relevance**: Key security implications or concerns  
3. **Usage Assessment**: Legitimate vs potentially suspicious usage

Keep explanations brief but technically accurate.""",

    expected_tokens=300,
    temperature=0.1,
    max_tokens=600,
    
    provider_adaptations={
        "anthropic": {
            "user_prompt_suffix": "\n\nBe concise but maintain thoroughness in your security reasoning."
        },
        "gemini": {
            "user_prompt_suffix": "\n\nFocus on performance and competitive aspects of API choices."
        }
    },
    
    notes="Brief import analysis for rapid assessment and triage"
)


# Import Explanation - Comprehensive Quality (v1)
IMPORT_EXPLANATION_COMPREHENSIVE_V1 = PromptTemplate(
    template_id="import_explanation_comprehensive_v1",
    version=PromptVersion.V1,
    operation_type="import_explanation",
    quality_level=TranslationQuality.COMPREHENSIVE,
    
    system_prompt="""You are a senior systems expert and threat intelligence analyst with deep knowledge of:
- Advanced API internals and implementation details
- Historical vulnerability patterns and exploit techniques
- Threat actor TTPs (Tactics, Techniques, and Procedures) 
- Advanced persistent threat (APT) behavior patterns
- Malware family API usage signatures
- Nation-state and criminal group operational patterns

Your comprehensive analysis should provide expert-level insights suitable for:
- Advanced threat intelligence reporting
- Malware family attribution and classification
- APT campaign analysis and tracking
- Deep vulnerability research and exploit development
- Advanced incident response and forensic analysis

Provide authoritative, detailed analysis that goes beyond basic API documentation to include threat intelligence context, historical usage patterns, and advanced security implications.""",

    user_prompt_template="""Provide comprehensive expert analysis of these imported functions for advanced threat intelligence:

**Target Analysis:**
- Platform: {file_platform} ({target_architecture})
- File Format: {file_format}  
- Import Profile: {import_count} imports across {unique_libraries} libraries

**Import Inventory:**
{imports_by_library}

**Detailed Import Data:**
{imports}

**Behavioral Context:**
{usage_patterns}
{frequency_data}

Please provide expert-level analysis for each imported function covering:

1. **Advanced API Analysis**:
   - Low-level implementation details and system interactions
   - Version-specific behaviors and compatibility considerations
   - Undocumented features and edge cases
   - Kernel vs user-mode execution context

2. **Threat Intelligence Context**:
   - Historical usage in malware families and APT campaigns
   - Known exploitation patterns and attack vectors
   - Signature APIs for specific threat actor groups
   - Timeline of API abuse and security researcher attention

3. **Advanced Security Assessment**:
   - Zero-day potential and unexplored attack surfaces
   - Privilege escalation vectors and security boundary crossings
   - Anti-analysis and evasion technique enablers
   - Supply chain and dependency risks

4. **Behavioral Fingerprinting**:
   - API combination patterns indicative of specific malware families
   - Operational security (OPSEC) implications of API choices
   - Attribution indicators and coding pattern signatures
   - Temporal analysis of API adoption and abandonment

5. **Technical Implementation Analysis**:
   - Performance characteristics and resource consumption patterns
   - Error handling and edge case behaviors
   - Interaction with security controls and monitoring systems
   - Potential for detection evasion and anti-forensics

6. **Strategic Intelligence Assessment**:
   - Capability assessment and threat actor sophistication indicators
   - Campaign infrastructure and tooling implications
   - Geopolitical and targeting implications of API choices
   - Evolution patterns and future threat development indicators

7. **Defensive Recommendations**:
   - Detection strategies and behavioral monitoring approaches
   - Hardening recommendations and configuration guidance  
   - Threat hunting queries and indicators of compromise
   - Attribution and campaign tracking methodologies

Provide detailed, expert-level analysis with specific technical justifications and threat intelligence context. Include confidence levels for assessments and highlight areas requiring additional investigation.""",

    expected_tokens=1000,
    temperature=0.1,
    max_tokens=2500,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nProvide nuanced analysis with detailed reasoning. Be explicit about confidence levels and areas of uncertainty. Focus on defensive applications while being thorough in threat assessment.",
            "user_prompt_suffix": "\n\nProvide detailed reasoning for all threat intelligence assessments. Highlight confidence levels and areas where additional investigation would be beneficial."
        },
        "openai": {
            "user_prompt_suffix": "\n\nStructure your comprehensive analysis with detailed headers and subheadings for easy navigation and reference."
        },
        "gemini": {
            "system_prompt_suffix": "\n\nEmphasize competitive intelligence, technology stack assessment, and strategic implications of API choices in your analysis.",
            "user_prompt_suffix": "\n\nInclude competitive intelligence insights, technology market analysis, and strategic implications of the observed API usage patterns."
        }
    },
    
    notes="Comprehensive import analysis for advanced threat intelligence and expert-level assessment"
)


# Security-Focused Import Analysis (v1)
IMPORT_SECURITY_ANALYSIS_V1 = PromptTemplate(
    template_id="import_security_analysis_v1",
    version=PromptVersion.V1,
    operation_type="import_explanation",
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are a cybersecurity expert specializing in API security analysis and threat assessment with focus on:
- Windows/Linux/macOS security model enforcement
- API-based attack vectors and exploitation techniques
- Privilege escalation and access control bypass methods
- Network security and communication API risks
- Cryptographic API implementation weaknesses
- Anti-analysis and evasion technique detection

Your analysis should identify security-relevant behaviors, potential attack vectors, and defensive considerations for each imported API.""",

    user_prompt_template="""Analyze these imports from a cybersecurity perspective:

**Security Analysis Context:**
- Platform: {file_platform} ({target_architecture})
- File Type: {file_format}
- Import Profile: {import_count} imports from {unique_libraries} libraries

**Import Categories:**
{imports_by_library}

**Full Import Details:**
{imports}

Please provide security-focused analysis covering:

1. **Attack Vector Assessment**:
   - Direct exploitation potential of each API
   - Privilege escalation opportunities and access control bypass vectors
   - Network attack surfaces and communication security risks
   - File system and registry manipulation capabilities

2. **Threat Capability Analysis**:
   - Data exfiltration and persistence mechanisms
   - System monitoring and defensive evasion capabilities
   - Process manipulation and injection techniques
   - Anti-forensics and evidence destruction methods

3. **Security Control Interaction**:
   - How APIs interact with Windows/Linux security features
   - Potential for security control bypass or manipulation
   - Logging and auditing implications
   - Detection evasion opportunities

4. **Risk Prioritization**:
   - High-risk APIs requiring immediate attention
   - API combinations indicating advanced threat capabilities
   - Unusual or suspicious API usage patterns
   - Indicators of sophisticated threat actor involvement

5. **Defensive Recommendations**:
   - Monitoring and detection strategies for each API category
   - Hardening configurations to limit API abuse potential
   - Threat hunting indicators and behavioral signatures
   - Incident response considerations and forensic artifacts

Focus on actionable security intelligence for defenders, analysts, and incident responders.""",

    expected_tokens=700,
    temperature=0.1,
    max_tokens=1400,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nProvide responsible security analysis focused on defensive applications. Be thorough in threat assessment while being mindful of information that could enable attacks.",
            "user_prompt_suffix": "\n\nFocus on defensive applications and provide detailed reasoning for security risk assessments."
        },
        "openai": {
            "user_prompt_suffix": "\n\nOrganize security analysis by risk level and provide clear defensive recommendations."
        },
        "gemini": {
            "user_prompt_suffix": "\n\nInclude analysis of how security measures impact performance and competitive positioning."
        }
    },
    
    notes="Security-focused import analysis for threat assessment and defensive planning"
)


# Malware Analysis Import Template (v1)
IMPORT_MALWARE_ANALYSIS_V1 = PromptTemplate(
    template_id="import_malware_analysis_v1", 
    version=PromptVersion.V1,
    operation_type="import_explanation",
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are a malware analyst with extensive experience in:
- Malware family classification and attribution
- Threat actor tactics, techniques, and procedures (TTPs)
- Advanced persistent threat (APT) campaign analysis
- Commodity malware and crimeware analysis
- Nation-state malware and cyber espionage tools
- Anti-analysis and evasion technique identification

Focus on identifying malware behavior patterns, threat actor signatures, and campaign indicators through API usage analysis.""",

    user_prompt_template="""Analyze these imports for malware behavior indicators and threat classification:

**Sample Profile:**
- Platform: {file_platform} ({file_format})
- Import Count: {import_count} from {unique_libraries} libraries
- Import Distribution: {imports_by_library}

**Complete Import List:**
{imports}

Please provide malware-focused analysis covering:

1. **Malware Behavior Classification**:
   - Primary malware capabilities (backdoor, trojan, stealer, etc.)
   - Secondary capabilities and multi-stage functionality
   - Payload delivery and execution mechanisms
   - Command and control (C2) communication methods

2. **Threat Actor Attribution Indicators**:
   - API usage patterns consistent with known threat groups
   - Tool development and operational security indicators
   - Geographic or language-specific API preferences
   - Sophistication level and resource indicators

3. **Campaign and Infrastructure Analysis**:
   - Infrastructure setup and management capabilities
   - Multi-stage deployment and update mechanisms
   - Persistence and stealth technique implementations
   - Data collection and exfiltration methods

4. **Anti-Analysis Assessment**:
   - Evasion technique implementation capabilities
   - Anti-debugging and anti-VM detection methods
   - Code obfuscation and packing indicators
   - Sandbox detection and analysis avoidance

5. **Threat Intelligence Context**:
   - Similar samples and campaign connections
   - Timeline analysis and evolution patterns
   - Geopolitical context and targeting implications
   - Relationship to broader threat landscape

Focus on classification, attribution, and threat intelligence insights for malware analysis teams.""",

    expected_tokens=600,
    temperature=0.1,
    max_tokens=1200,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nFocus on analytical rigor and defensive applications. Provide detailed reasoning for malware classification and attribution assessments.",
            "user_prompt_suffix": "\n\nProvide confident assessments where evidence supports them, but clearly indicate areas of uncertainty or where additional analysis is needed."
        },
        "openai": {
            "user_prompt_suffix": "\n\nStructure your malware analysis with clear classification categories and confidence levels."
        },
        "gemini": {
            "user_prompt_suffix": "\n\nEmphasize competitive threat intelligence and strategic implications of the observed malware capabilities."
        }
    },
    
    notes="Malware-focused import analysis for threat classification and attribution"
)


# Export all import explanation templates
IMPORT_EXPLANATION_PROMPTS: Dict[str, Dict[str, PromptTemplate]] = {
    TranslationQuality.BRIEF: {
        PromptVersion.V1: IMPORT_EXPLANATION_BRIEF_V1
    },
    TranslationQuality.STANDARD: {
        PromptVersion.V1: IMPORT_EXPLANATION_STANDARD_V1  
    },
    TranslationQuality.COMPREHENSIVE: {
        PromptVersion.V1: IMPORT_EXPLANATION_COMPREHENSIVE_V1
    }
}

# Specialized import analysis templates
SPECIALIZED_IMPORT_PROMPTS: Dict[str, PromptTemplate] = {
    "security_analysis": IMPORT_SECURITY_ANALYSIS_V1,
    "malware_analysis": IMPORT_MALWARE_ANALYSIS_V1
}


def get_import_prompt(
    quality_level: TranslationQuality = TranslationQuality.STANDARD,
    version: PromptVersion = PromptVersion.V1,
    specialized_type: str = None
) -> PromptTemplate:
    """
    Get import explanation prompt template.
    
    Args:
        quality_level: Desired quality/detail level
        version: Template version
        specialized_type: Optional specialized analysis type
        
    Returns:
        PromptTemplate for import explanation
        
    Raises:
        KeyError: If specified template doesn't exist
    """
    if specialized_type:
        if specialized_type not in SPECIALIZED_IMPORT_PROMPTS:
            raise KeyError(f"Unknown specialized import prompt type: {specialized_type}")
        return SPECIALIZED_IMPORT_PROMPTS[specialized_type]
    
    if quality_level not in IMPORT_EXPLANATION_PROMPTS:
        raise KeyError(f"Unknown quality level: {quality_level}")
    
    quality_templates = IMPORT_EXPLANATION_PROMPTS[quality_level]
    if version not in quality_templates:
        # Fallback to V1 if requested version doesn't exist
        version = PromptVersion.V1
        if version not in quality_templates:
            raise KeyError(f"No templates available for quality level: {quality_level}")
    
    return quality_templates[version]


def list_available_import_prompts() -> Dict[str, List[str]]:
    """List all available import explanation prompt templates."""
    return {
        "standard_prompts": {
            quality: list(templates.keys())
            for quality, templates in IMPORT_EXPLANATION_PROMPTS.items()
        },
        "specialized_prompts": list(SPECIALIZED_IMPORT_PROMPTS.keys())
    }