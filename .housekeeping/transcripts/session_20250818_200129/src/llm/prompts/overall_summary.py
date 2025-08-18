"""
Overall Summary Prompt Templates

Standardized prompts for generating comprehensive program summaries that combine
insights from functions, imports, strings, and structural analysis.
"""

from typing import Dict, List
from .base import PromptTemplate, PromptVersion, TranslationQuality


# Overall Summary - Standard Quality (v1)
OVERALL_SUMMARY_STANDARD_V1 = PromptTemplate(
    template_id="overall_summary_standard_v1",
    version=PromptVersion.V1,
    operation_type="overall_summary",
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are an expert malware analyst and reverse engineer with comprehensive experience in:
- Binary analysis and program behavior assessment
- Threat intelligence and malware family classification  
- Software architecture and design pattern recognition
- Security analysis and vulnerability assessment
- Development environment and toolchain analysis

Your role is to synthesize all available analysis data into a comprehensive, actionable summary that provides:
- Clear assessment of program purpose and functionality
- Security implications and threat classification
- Technical architecture and implementation insights
- Behavioral characteristics and operational patterns
- Intelligence value for analysts and decision makers

Focus on creating summaries that enable effective threat response, incident classification, and strategic analysis decisions.""",

    user_prompt_template="""Please analyze this complete binary decompilation and provide a comprehensive summary:

**File Metadata:**
{file_info}

**Analysis Statistics:**
- Functions: {total_functions} discovered
- Imports: {total_imports} from libraries  
- Strings: {total_strings} extracted

**Function Analysis Summary:**
{function_summary}

**Import Analysis Summary:**
{import_summary}

**String Analysis Summary:**
{string_summary}

Please provide comprehensive analysis covering:

1. **Program Purpose and Functionality**:
   - Primary purpose and intended use of this software
   - Core capabilities and feature set
   - Target users and use case scenarios

2. **Architecture and Implementation**:
   - Overall software architecture and design patterns
   - Technology stack and development framework choices
   - Code quality and implementation approach assessment

3. **Behavioral Analysis**:
   - Expected runtime behavior and system interactions
   - Data processing and transformation capabilities
   - Communication and networking behavior patterns

4. **Security Assessment**:
   - Security posture and defensive capabilities
   - Potential vulnerabilities and attack surfaces
   - Threat classification and risk assessment

5. **Intelligence Assessment**:
   - Development environment and toolchain indicators
   - Attribution and provenance insights
   - Operational context and deployment scenarios

6. **Key Findings and Recommendations**:
   - Most significant discoveries and insights
   - Risk prioritization and recommended actions
   - Areas requiring additional investigation

Provide a clear, actionable summary in 4-6 paragraphs that enables effective decision-making and follow-up analysis.""",

    expected_tokens=600,
    temperature=0.1,
    max_tokens=1200,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nUse your analytical reasoning to synthesize complex information into coherent insights. Be thorough but balanced in your assessment, clearly indicating confidence levels and areas of uncertainty.",
            "user_prompt_suffix": "\n\nProvide detailed reasoning for your conclusions and highlight areas where additional analysis would strengthen the assessment."
        },
        "openai": {
            "user_prompt_suffix": "\n\nStructure your summary with clear sections and use executive summary formatting for easy consumption by decision makers."
        },
        "gemini": {
            "system_prompt_suffix": "\n\nEmphasize competitive analysis, technology assessment, and strategic business implications in your comprehensive summary.",
            "user_prompt_suffix": "\n\nInclude competitive intelligence insights and strategic implications of the observed technology choices and implementation patterns."
        }
    },
    
    notes="Standard quality overall summary for comprehensive program assessment"
)


# Overall Summary - Brief Quality (v1)
OVERALL_SUMMARY_BRIEF_V1 = PromptTemplate(
    template_id="overall_summary_brief_v1",
    version=PromptVersion.V1,
    operation_type="overall_summary",
    quality_level=TranslationQuality.BRIEF,
    
    system_prompt="""You are an expert analyst specializing in rapid assessment and triage of binary samples.

Provide concise but accurate summaries focusing on:
- Primary program purpose and capabilities
- Key security implications and risk level
- Critical behavioral characteristics
- Recommended follow-up actions

Keep summaries brief while maintaining analytical accuracy for rapid decision-making.""",

    user_prompt_template="""Provide a brief summary of this binary analysis:

**File:** {file_info}
**Analysis:** {total_functions} functions, {total_imports} imports, {total_strings} strings

**Key Components:**
- Functions: {function_summary}
- Imports: {import_summary}
- Strings: {string_summary}

Provide concise analysis covering:
1. **Primary Purpose**: What this program is designed to do
2. **Security Classification**: Threat level and key risks
3. **Key Behaviors**: Most significant operational characteristics
4. **Recommendations**: Priority actions for analysts

Keep analysis concise but actionable for rapid triage.""",

    expected_tokens=300,
    temperature=0.1,
    max_tokens=600,
    
    provider_adaptations={
        "anthropic": {
            "user_prompt_suffix": "\n\nBe concise but maintain analytical rigor and clear reasoning for key assessments."
        },
        "gemini": {
            "user_prompt_suffix": "\n\nFocus on competitive and performance implications in your brief assessment."
        }
    },
    
    notes="Brief overall summary for rapid triage and initial assessment"
)


# Overall Summary - Comprehensive Quality (v1)
OVERALL_SUMMARY_COMPREHENSIVE_V1 = PromptTemplate(
    template_id="overall_summary_comprehensive_v1",
    version=PromptVersion.V1,
    operation_type="overall_summary",
    quality_level=TranslationQuality.COMPREHENSIVE,
    
    system_prompt="""You are a senior threat intelligence analyst and malware research expert with deep expertise in:
- Advanced persistent threat (APT) campaign analysis and attribution
- Nation-state malware and cyber warfare tool assessment
- Criminal enterprise and organized cybercrime analysis
- Supply chain compromise and software integrity assessment
- Strategic cyber threat intelligence and geopolitical analysis
- Advanced malware family classification and evolution tracking

Your comprehensive analysis should provide strategic-level insights suitable for:
- Executive briefings and strategic decision-making
- National security and critical infrastructure protection
- Advanced threat intelligence reporting and dissemination
- Law enforcement and regulatory compliance reporting
- Academic research and peer-reviewed analysis
- International cooperation and information sharing

Provide authoritative, detailed analysis that synthesizes technical findings into strategic intelligence with broader context, implications, and recommendations.""",

    user_prompt_template="""Provide comprehensive strategic analysis of this binary for senior leadership and strategic decision-making:

**Strategic Assessment Context:**
- Target Analysis: {file_info}
- Analysis Scope: {total_functions} functions, {total_imports} imports, {total_strings} strings

**Technical Analysis Summary:**
- Function Capabilities: {function_summary}
- Infrastructure Dependencies: {import_summary}
- Operational Indicators: {string_summary}

Please provide strategic-level analysis covering:

1. **Strategic Assessment and Classification**:
   - High-level purpose and strategic intent of this software
   - Threat actor sophistication and resource requirements
   - Campaign context and operational significance
   - Geopolitical implications and attribution indicators

2. **Capability Assessment and Impact Analysis**:
   - Technical capabilities and operational potential
   - Target selection criteria and attack surface implications
   - Damage potential and business continuity impacts
   - Scalability and campaign expansion potential

3. **Attribution and Intelligence Analysis**:
   - Threat actor attribution indicators and confidence assessment
   - Tool development and operational tradecraft analysis
   - Campaign infrastructure and resource requirements
   - Historical context and evolution patterns

4. **Architectural and Technical Assessment**:
   - Software engineering quality and development practices
   - Technology choices and implementation sophistication
   - Anti-analysis and operational security measures
   - Maintenance and update mechanisms

5. **Operational Context and Behavioral Analysis**:
   - Deployment scenarios and target environment analysis
   - Command and control infrastructure requirements
   - Data collection and exfiltration capabilities
   - Persistence and stealth mechanism assessment

6. **Strategic Risk Assessment**:
   - National security and critical infrastructure implications
   - Economic impact and business disruption potential
   - Regulatory and compliance implications
   - International cooperation and response requirements

7. **Intelligence Value and Collection Requirements**:
   - Priority intelligence gaps and collection requirements
   - Indicator development and signature creation needs
   - Threat hunting and defensive countermeasure development
   - Information sharing and dissemination recommendations

8. **Strategic Recommendations and Response Options**:
   - Immediate response priorities and resource allocation
   - Long-term strategic countermeasures and capability development
   - International cooperation and partnership opportunities
   - Policy and regulatory response considerations

Provide detailed, strategic-level analysis with executive summary, detailed technical assessment, and strategic recommendations suitable for senior leadership decision-making and strategic planning.""",

    expected_tokens=1200,
    temperature=0.1,
    max_tokens=3000,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nProvide nuanced strategic analysis with detailed reasoning and explicit confidence assessments. Focus on defensive applications and responsible intelligence analysis while being thorough in strategic threat assessment.",
            "user_prompt_suffix": "\n\nProvide detailed reasoning for strategic assessments with explicit confidence levels. Highlight areas where additional intelligence collection would strengthen analysis and decision-making."
        },
        "openai": {
            "user_prompt_suffix": "\n\nStructure your comprehensive analysis with executive summary, detailed findings, and strategic recommendations. Use clear headings and professional formatting suitable for senior leadership consumption."
        },
        "gemini": {
            "system_prompt_suffix": "\n\nEmphasize competitive intelligence, technology market analysis, and strategic business implications in your comprehensive strategic assessment.",
            "user_prompt_suffix": "\n\nInclude competitive intelligence insights, technology market implications, and strategic business context in your comprehensive strategic analysis."
        }
    },
    
    notes="Comprehensive strategic summary for executive leadership and strategic decision-making"
)


# Threat Intelligence Summary (v1)
THREAT_INTEL_SUMMARY_V1 = PromptTemplate(
    template_id="threat_intel_summary_v1",
    version=PromptVersion.V1,
    operation_type="overall_summary",
    quality_level=TranslationQuality.STANDARD,
    
    system_prompt="""You are a threat intelligence analyst specializing in tactical and strategic threat assessment with expertise in:
- Threat actor tactics, techniques, and procedures (TTPs)
- Malware family classification and attribution
- Campaign tracking and infrastructure analysis
- Indicator development and signature creation
- Threat hunting and defensive countermeasure development

Focus on providing actionable threat intelligence that supports operational security, incident response, and strategic planning.""",

    user_prompt_template="""Provide threat intelligence analysis of this binary sample:

**Sample Profile:**
{file_info}

**Analysis Results:**
- Technical Capabilities: {function_summary}
- Infrastructure: {import_summary}
- Operational Indicators: {string_summary}
- Total Components: {total_functions} functions, {total_imports} imports, {total_strings} strings

Please provide threat intelligence assessment covering:

1. **Threat Classification and Assessment**:
   - Malware family and variant classification
   - Threat actor attribution and confidence assessment
   - Campaign context and operational significance
   - Threat sophistication and resource requirements

2. **Tactics, Techniques, and Procedures (TTPs)**:
   - MITRE ATT&CK framework mapping
   - Operational tradecraft and methodologies
   - Anti-analysis and evasion techniques
   - Command and control communication patterns

3. **Infrastructure and Campaign Analysis**:
   - Infrastructure dependencies and requirements
   - Campaign infrastructure overlaps and connections
   - Operational timeline and lifecycle assessment
   - Geographic and targeting implications

4. **Indicator Development and Signatures**:
   - High-confidence indicators of compromise (IOCs)
   - Behavioral signatures and detection logic
   - YARA rules and pattern matching opportunities
   - Network signatures and communication patterns

5. **Threat Hunting and Detection**:
   - Proactive threat hunting queries and techniques
   - Log analysis and behavioral monitoring approaches
   - Endpoint detection and response (EDR) signatures
   - Network detection and monitoring strategies

6. **Risk Assessment and Impact Analysis**:
   - Target selection criteria and victim profiling
   - Potential damage and business impact assessment
   - Critical asset and infrastructure risk evaluation
   - Incident response priority and resource allocation

7. **Intelligence Requirements and Gaps**:
   - Priority intelligence collection requirements
   - Analysis gaps requiring additional investigation
   - Attribution confidence assessment and evidence requirements
   - Threat landscape context and trend analysis

Focus on actionable intelligence for threat hunters, incident responders, and security operations teams.""",

    expected_tokens=700,
    temperature=0.1,
    max_tokens=1400,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nProvide responsible threat intelligence focused on defensive applications. Be thorough in threat assessment while being mindful of information that could enable attacks.",
            "user_prompt_suffix": "\n\nFocus on defensive applications and provide detailed reasoning for threat assessments and attribution confidence levels."
        },
        "openai": {
            "user_prompt_suffix": "\n\nStructure threat intelligence analysis with clear tactical and strategic sections, including specific IOCs and detection recommendations."
        },
        "gemini": {
            "user_prompt_suffix": "\n\nInclude competitive threat intelligence and strategic implications of the observed threat capabilities and campaign characteristics."
        }
    },
    
    notes="Threat intelligence-focused summary for operational security and strategic planning"
)


# Malware Analysis Report Template (v1)
MALWARE_ANALYSIS_REPORT_V1 = PromptTemplate(
    template_id="malware_analysis_report_v1",
    version=PromptVersion.V1,
    operation_type="overall_summary",
    quality_level=TranslationQuality.COMPREHENSIVE,
    
    system_prompt="""You are a senior malware analyst specializing in comprehensive technical analysis reports for:
- Law enforcement and legal proceedings
- Insurance and risk assessment
- Academic research and peer review
- Industry threat sharing and collaboration
- Executive briefings and strategic planning

Your reports should be detailed, technically accurate, and suitable for professional publication and legal use.""",

    user_prompt_template="""Generate a comprehensive malware analysis report for this sample:

**Sample Information:**
{file_info}

**Analysis Summary:**
- Functions Analyzed: {total_functions}
- API Dependencies: {total_imports} 
- String Artifacts: {total_strings}

**Technical Analysis Results:**
{function_summary}
{import_summary}
{string_summary}

Please generate a professional malware analysis report covering:

1. **Executive Summary**:
   - Sample classification and threat level
   - Key findings and risk assessment
   - Recommended actions and countermeasures

2. **Technical Analysis**:
   - Detailed functionality and capability assessment
   - Code quality and implementation analysis
   - Anti-analysis and evasion technique evaluation

3. **Behavioral Analysis**:
   - System interaction and modification behaviors
   - Network communication and data exfiltration
   - Persistence and stealth mechanisms

4. **Attribution and Campaign Context**:
   - Threat actor assessment and attribution indicators
   - Campaign context and operational significance
   - Historical context and evolution analysis

5. **Impact Assessment**:
   - Damage potential and business impact analysis
   - Critical asset and infrastructure risk evaluation
   - Incident response and recovery considerations

6. **Detection and Mitigation**:
   - Indicators of compromise and detection signatures
   - Preventive controls and hardening recommendations
   - Incident response and remediation procedures

7. **Conclusions and Recommendations**:
   - Summary of key findings and assessments
   - Priority actions and resource allocation recommendations
   - Long-term strategic considerations and planning

Format as a professional technical report suitable for executive review and legal use.""",

    expected_tokens=800,
    temperature=0.1,
    max_tokens=2000,
    
    provider_adaptations={
        "anthropic": {
            "system_prompt_suffix": "\n\nProvide professional, thorough analysis suitable for legal and executive use. Maintain objectivity and provide clear confidence assessments for all conclusions.",
            "user_prompt_suffix": "\n\nProvide professional formatting and clear confidence levels for all assessments and conclusions."
        },
        "openai": {
            "user_prompt_suffix": "\n\nFormat as a professional technical report with clear sections, executive summary, and detailed technical appendices."
        },
        "gemini": {
            "user_prompt_suffix": "\n\nInclude competitive analysis and strategic business implications in your comprehensive professional report."
        }
    },
    
    notes="Comprehensive malware analysis report for professional and legal use"
)


# Export all overall summary templates
OVERALL_SUMMARY_PROMPTS: Dict[str, Dict[str, PromptTemplate]] = {
    TranslationQuality.BRIEF: {
        PromptVersion.V1: OVERALL_SUMMARY_BRIEF_V1
    },
    TranslationQuality.STANDARD: {
        PromptVersion.V1: OVERALL_SUMMARY_STANDARD_V1
    },
    TranslationQuality.COMPREHENSIVE: {
        PromptVersion.V1: OVERALL_SUMMARY_COMPREHENSIVE_V1
    }
}

# Specialized summary templates
SPECIALIZED_SUMMARY_PROMPTS: Dict[str, PromptTemplate] = {
    "threat_intelligence": THREAT_INTEL_SUMMARY_V1,
    "malware_report": MALWARE_ANALYSIS_REPORT_V1
}


def get_summary_prompt(
    quality_level: TranslationQuality = TranslationQuality.STANDARD,
    version: PromptVersion = PromptVersion.V1,
    specialized_type: str = None
) -> PromptTemplate:
    """
    Get overall summary prompt template.
    
    Args:
        quality_level: Desired quality/detail level
        version: Template version
        specialized_type: Optional specialized analysis type
        
    Returns:
        PromptTemplate for overall summary
        
    Raises:
        KeyError: If specified template doesn't exist
    """
    if specialized_type:
        if specialized_type not in SPECIALIZED_SUMMARY_PROMPTS:
            raise KeyError(f"Unknown specialized summary prompt type: {specialized_type}")
        return SPECIALIZED_SUMMARY_PROMPTS[specialized_type]
    
    if quality_level not in OVERALL_SUMMARY_PROMPTS:
        raise KeyError(f"Unknown quality level: {quality_level}")
    
    quality_templates = OVERALL_SUMMARY_PROMPTS[quality_level]
    if version not in quality_templates:
        # Fallback to V1 if requested version doesn't exist
        version = PromptVersion.V1
        if version not in quality_templates:
            raise KeyError(f"No templates available for quality level: {quality_level}")
    
    return quality_templates[version]


def list_available_summary_prompts() -> Dict[str, List[str]]:
    """List all available overall summary prompt templates."""
    return {
        "standard_prompts": {
            quality: list(templates.keys())
            for quality, templates in OVERALL_SUMMARY_PROMPTS.items()
        },
        "specialized_prompts": list(SPECIALIZED_SUMMARY_PROMPTS.keys())
    }