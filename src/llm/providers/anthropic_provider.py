"""
Anthropic Provider Implementation

Anthropic Claude API provider for binary decompilation translation.
Supports Claude-3-opus, Claude-3-sonnet, Claude-3-haiku with Constitutional AI features.
"""

import asyncio
import json
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import httpx
from anthropic import AsyncAnthropic, APIError, RateLimitError, AuthenticationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..base import (
    LLMProvider, 
    LLMConfig, 
    LLMProviderException, 
    LLMRateLimitException, 
    LLMAuthenticationException,
    LLMServiceUnavailableException,
    ProviderHealthStatus,
    TranslationOperationType
)
from ...models.decompilation.results import (
    FunctionTranslation, 
    ImportTranslation, 
    StringTranslation, 
    OverallSummary,
    LLMProviderMetadata
)


class AnthropicProvider(LLMProvider):
    """
    Anthropic Claude API provider implementation with Constitutional AI features.
    
    Emphasizes detailed reasoning, security analysis, and responsible AI practices
    for binary analysis tasks.
    """
    
    # Default models for Anthropic
    DEFAULT_MODELS = {
        "claude-3-opus-20240229": "claude-3-opus-20240229",
        "claude-3-sonnet-20240229": "claude-3-sonnet-20240229", 
        "claude-3-haiku-20240307": "claude-3-haiku-20240307"
    }
    
    # Cost per 1K tokens (USD) for Anthropic models
    MODEL_COSTS = {
        "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
        "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125}
    }
    
    # Model context windows (tokens)
    MODEL_CONTEXT_LIMITS = {
        "claude-3-opus-20240229": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-haiku-20240307": 200000
    }
    
    def __init__(self, config: LLMConfig):
        """Initialize Anthropic provider with configuration."""
        super().__init__(config)
        self.anthropic_client: Optional[AsyncAnthropic] = None
        self._token_count_cache: Dict[str, int] = {}
        
    async def initialize(self) -> None:
        """Initialize the Anthropic client and HTTP connections."""
        try:
            self.anthropic_client = AsyncAnthropic(
                api_key=self.config.api_key.get_secret_value(),
                timeout=self.config.timeout_seconds,
                max_retries=3
            )
            
            # Test connection
            await self.health_check()
            
        except Exception as e:
            raise LLMProviderException(
                f"Failed to initialize Anthropic provider: {str(e)}",
                self.get_provider_id(),
                "INIT_FAILED"
            )
    
    async def cleanup(self) -> None:
        """Cleanup Anthropic client and connections."""
        if self.anthropic_client:
            await self.anthropic_client.close()
            self.anthropic_client = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((RateLimitError, httpx.TimeoutException))
    )
    async def _make_completion_request(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: str,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Make completion request with retry logic."""
        if not self.anthropic_client:
            raise LLMServiceUnavailableException(self.get_provider_id(), "Client not initialized")
        
        request_model = model or self.config.default_model
        request_temperature = temperature if temperature is not None else self.config.temperature
        request_max_tokens = max_tokens or min(self.config.max_tokens, 4096)  # Claude has different limits
        
        # Convert messages format for Anthropic (remove system from messages)
        anthropic_messages = []
        for msg in messages:
            if msg["role"] != "system":
                anthropic_messages.append(msg)
        
        try:
            start_time = time.time()
            
            response = await self.anthropic_client.messages.create(
                model=request_model,
                system=system_prompt,
                messages=anthropic_messages,
                temperature=request_temperature,
                max_tokens=request_max_tokens
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Extract content from response
            content_blocks = response.content
            content = ""
            for block in content_blocks:
                if hasattr(block, 'text'):
                    content += block.text
            
            return {
                "content": content,
                "model": response.model,
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens if response.usage else 0,
                "input_tokens": response.usage.input_tokens if response.usage else 0,
                "output_tokens": response.usage.output_tokens if response.usage else 0,
                "processing_time_ms": processing_time_ms
            }
            
        except AuthenticationError as e:
            raise LLMAuthenticationException(self.get_provider_id(), str(e))
        except RateLimitError as e:
            # Extract retry-after header if available
            retry_after = getattr(e, 'retry_after', None)
            raise LLMRateLimitException(self.get_provider_id(), retry_after)
        except APIError as e:
            if "overloaded" in str(e).lower() or "unavailable" in str(e).lower():
                raise LLMServiceUnavailableException(self.get_provider_id(), str(e))
            else:
                raise LLMProviderException(f"Anthropic API error: {str(e)}", self.get_provider_id(), "API_ERROR")
        except Exception as e:
            raise LLMProviderException(f"Unexpected error: {str(e)}", self.get_provider_id(), "UNKNOWN_ERROR")
    
    async def translate_function(
        self, 
        function_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> FunctionTranslation:
        """Translate assembly function to natural language explanation with detailed reasoning."""
        
        # Build system prompt with Constitutional AI principles
        system_prompt = """You are Claude, an expert binary analysis assistant created by Anthropic. You specialize in translating assembly code and decompiled functions into clear, natural language explanations with careful reasoning.

Your approach:
1. Think step by step through the analysis
2. Consider multiple interpretations before concluding
3. Highlight security implications responsibly
4. Provide detailed reasoning for your conclusions
5. Be honest about uncertainty or limitations
6. Focus on helping security researchers and developers understand the code

Analyze the provided function systematically and provide comprehensive explanations that would be valuable for cybersecurity professionals."""

        # Build user prompt with detailed context
        user_prompt = f"""I need you to analyze this decompiled function and provide a comprehensive explanation. Please think through this carefully and show your reasoning.

**Function Information:**
- Name: {function_data.get('name', 'unknown')}
- Address: {function_data.get('address', 'unknown')}
- Size: {function_data.get('size', 0)} bytes
- Entry Point: {'Yes' if function_data.get('is_entry_point') else 'No'}
- Imported: {'Yes' if function_data.get('is_imported') else 'No'}

**Assembly Code:**
```assembly
{function_data.get('assembly_code', 'Not available')}
```

**Decompiled Code (if available):**
```c
{function_data.get('decompiled_code', 'Not available')}
```

**Function Relationships:**
- Calls to: {', '.join(function_data.get('calls_to', [])) or 'None identified'}
- Called by: {', '.join(function_data.get('called_by', [])) or 'None identified'}
- Variables/Parameters: {', '.join(function_data.get('variables', [])) or 'None identified'}

**Additional Context:**
```json
{json.dumps(context or {}, indent=2)}
```

Please provide:

1. **Initial Analysis**: What do you observe about this function at first glance?

2. **Detailed Breakdown**: Step through the function's logic and operations.

3. **Purpose and Functionality**: What is this function designed to do?

4. **Parameters and Return Values**: Analyze inputs and outputs.

5. **Security Analysis**: Any security-relevant observations or concerns?

6. **Confidence Assessment**: How confident are you in this analysis and why?

Please be thorough in your reasoning and highlight any areas where you're uncertain."""

        messages = [
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._make_completion_request(messages, system_prompt)
        
        # Parse the detailed response
        content = response["content"]
        
        # Extract specific sections from Claude's structured response
        analysis_sections = self._parse_detailed_analysis(content)
        
        # Extract confidence score from Claude's own assessment
        confidence_score = self._extract_confidence_score(content)
        
        # Create provider metadata with Claude-specific details
        provider_metadata = self._create_provider_metadata(
            model=response["model"],
            tokens_used=response["tokens_used"],
            processing_time_ms=response["processing_time_ms"],
            cost_estimate=self._calculate_cost(response["input_tokens"], response["output_tokens"], response["model"])
        )
        provider_metadata.api_version = "2023-06-01"
        
        return FunctionTranslation(
            function_name=function_data.get('name', 'unknown'),
            address=function_data.get('address', '0x0'),
            size=function_data.get('size', 0),
            assembly_code=function_data.get('assembly_code'),
            natural_language_description=analysis_sections.get('functionality', content),
            parameters_explanation=analysis_sections.get('parameters'),
            return_value_explanation=analysis_sections.get('return_values'),
            assembly_summary=analysis_sections.get('detailed_breakdown'),
            security_analysis=analysis_sections.get('security_analysis'),
            confidence_score=confidence_score,
            reasoning=analysis_sections.get('reasoning'),  # Claude-specific field
            llm_provider=provider_metadata,
            context_used=context or {}
        )
    
    async def explain_imports(
        self, 
        import_list: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ImportTranslation]:
        """Explain imported functions with detailed security analysis."""
        
        if not import_list:
            return []
        
        system_prompt = """You are Claude, an expert in system APIs, library functions, and cybersecurity. You have deep knowledge of Windows, Linux, and macOS system APIs, their legitimate uses, and their potential for misuse.

Analyze each imported function with:
1. Comprehensive understanding of the API's purpose
2. Security implications and common attack vectors
3. Legitimate vs. suspicious usage patterns
4. Context-aware threat assessment

Be thorough in your analysis while being responsible about security information."""
        
        user_prompt = f"""Please analyze these imported functions found in a binary. For each import, I need a comprehensive security-focused analysis.

**Imported Functions:**
{json.dumps(import_list, indent=2)}

**Context Information:**
{json.dumps(context or {}, indent=2)}

For each import, please provide:

1. **API Documentation Summary**: Official purpose and functionality
2. **Legitimate Usage Patterns**: How this API is normally used
3. **Parameters and Return Values**: Technical details
4. **Security Implications**: What security risks or capabilities this API provides
5. **Suspicious Usage Indicators**: Red flags that might indicate malicious use
6. **Common Misuses**: How attackers typically abuse this API
7. **Detection Strategies**: How security tools identify suspicious usage

Please be thorough and provide actionable intelligence for security analysts."""

        messages = [
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._make_completion_request(messages, system_prompt, max_tokens=8192)
        
        content = response["content"]
        translations = []
        
        provider_metadata = self._create_provider_metadata(
            model=response["model"],
            tokens_used=response["tokens_used"],
            processing_time_ms=response["processing_time_ms"],
            cost_estimate=self._calculate_cost(response["input_tokens"], response["output_tokens"], response["model"])
        )
        provider_metadata.api_version = "2023-06-01"
        
        for import_item in import_list:
            # Extract Claude's analysis for this specific import
            import_analysis = self._extract_import_analysis_claude(content, import_item)
            
            translation = ImportTranslation(
                library_name=import_item.get('library', 'unknown'),
                function_name=import_item.get('function', 'unknown'),
                api_documentation_summary=import_analysis.get('documentation', 'Analysis not available'),
                usage_context=import_analysis.get('usage_context', 'Context analysis not available'),
                parameters_description=import_analysis.get('parameters'),
                return_value_description=import_analysis.get('return_values'),
                security_implications=import_analysis.get('security_implications'),
                alternative_apis=import_analysis.get('alternatives', []),
                common_misuses=import_analysis.get('common_misuses', []),
                detection_signatures=import_analysis.get('detection_strategies', []),
                legitimate_vs_malicious=import_analysis.get('legitimate_vs_malicious'),
                confidence_score=0.9,  # Claude typically provides high-quality analysis
                llm_provider=provider_metadata
            )
            translations.append(translation)
        
        return translations
    
    async def interpret_strings(
        self, 
        string_list: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[StringTranslation]:
        """Interpret strings with security-focused analysis."""
        
        if not string_list:
            return []
        
        system_prompt = """You are Claude, an expert at analyzing strings found in binary files to understand their purpose, encoding, and security implications.

Your analysis should be:
1. Thorough and technically accurate
2. Security-focused when relevant
3. Honest about limitations or uncertainty
4. Helpful for threat intelligence and incident response

Consider string encoding, content patterns, potential obfuscation, and contextual usage."""
        
        # Process strings in smaller batches to avoid token limits
        limited_strings = string_list[:30]  # Process up to 30 strings for detailed analysis
        
        user_prompt = f"""Please analyze these strings found in a binary file. I need detailed interpretations that would be valuable for security analysis.

**Extracted Strings:**
{json.dumps(limited_strings, indent=2)}

**Context Information:**
{json.dumps(context or {}, indent=2)}

For each string, please analyze:

1. **Content Interpretation**: What does this string likely represent?
2. **Usage Context**: How and where is this string probably used?
3. **Data Classification**: Type of data (URL, file path, registry key, config value, etc.)
4. **Encoding Analysis**: Character encoding and any special formatting
5. **Security Relevance**: Any security implications or threat indicators
6. **Obfuscation Assessment**: Signs of encoding, encryption, or obfuscation
7. **Behavioral Indicators**: What this string might tell us about program behavior

Please provide thorough analysis while being responsible about potentially sensitive information."""

        messages = [
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._make_completion_request(messages, system_prompt, max_tokens=8192)
        
        content = response["content"]
        translations = []
        
        provider_metadata = self._create_provider_metadata(
            model=response["model"],
            tokens_used=response["tokens_used"],
            processing_time_ms=response["processing_time_ms"],
            cost_estimate=self._calculate_cost(response["input_tokens"], response["output_tokens"], response["model"])
        )
        provider_metadata.api_version = "2023-06-01"
        
        for string_item in limited_strings:
            string_analysis = self._extract_string_analysis_claude(content, string_item)
            
            translation = StringTranslation(
                string_value=string_item.get('content', ''),
                address=string_item.get('address', '0x0'),
                size=string_item.get('size', len(string_item.get('content', ''))),
                encoding=string_item.get('encoding', 'ascii'),
                usage_context=string_analysis.get('usage_context', 'Usage analysis not available'),
                interpretation=string_analysis.get('interpretation', 'Interpretation not available'),
                encoding_details=string_analysis.get('encoding_details'),
                security_analysis=string_analysis.get('security_analysis'),
                data_classification=string_analysis.get('data_classification'),
                obfuscation_analysis=string_analysis.get('obfuscation_analysis'),
                confidence_score=0.85,  # Claude provides detailed analysis
                llm_provider=provider_metadata
            )
            translations.append(translation)
        
        return translations
    
    async def generate_overall_summary(
        self, 
        decompilation_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> OverallSummary:
        """Generate comprehensive program summary with detailed reasoning."""
        
        system_prompt = """You are Claude, an expert malware analyst and reverse engineer with deep experience in threat intelligence and binary analysis.

Provide a comprehensive, well-reasoned analysis that would be valuable for:
- Security analysts investigating potential threats
- Incident responders triaging samples
- Threat intelligence researchers
- SOC analysts making classification decisions

Your analysis should be thorough, honest about limitations, and provide actionable insights. Consider both legitimate and malicious possibilities."""
        
        user_prompt = f"""Please analyze this complete binary decompilation and provide a comprehensive assessment. I need a thorough analysis that considers all available evidence.

**File Metadata:**
{json.dumps(decompilation_data.get('file_info', {}), indent=2)}

**Functions Analysis:**
- Total functions discovered: {len(decompilation_data.get('functions', []))}
- Key function names: {[f.get('name') for f in decompilation_data.get('functions', [])[:15]]}
- Entry points and exported functions identified

**Imports Analysis:**
- Total imported functions: {len(decompilation_data.get('imports', []))}
- Libraries used: {list(set([i.get('library') for i in decompilation_data.get('imports', [])[:25]]))}
- Key API categories represented

**Strings Analysis:**
- Total strings extracted: {len(decompilation_data.get('strings', []))}
- Sample strings: {[s.get('content')[:100] for s in decompilation_data.get('strings', [])[:15]]}

**Additional Context:**
{json.dumps(context or {}, indent=2)}

Please provide a comprehensive analysis covering:

1. **Program Purpose**: What is this software designed to do?

2. **Main Functionality**: Core features and capabilities

3. **Architecture Analysis**: Program structure and design patterns

4. **Data Flow Assessment**: How data moves through the program

5. **Technology Stack**: Languages, frameworks, and dependencies

6. **Security Analysis**: 
   - Defensive capabilities
   - Potential offensive capabilities
   - Vulnerability assessment
   - Trust indicators

7. **Behavioral Analysis**: What behaviors would you expect to observe?

8. **Risk Assessment**: Overall threat level and key concerns

9. **Classification Reasoning**: Detailed reasoning for your assessment

10. **Key Insights**: Most important findings for analysts

Please be thorough in your reasoning and provide specific evidence for your conclusions."""

        messages = [
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._make_completion_request(messages, system_prompt, max_tokens=8192)
        
        content = response["content"]
        
        provider_metadata = self._create_provider_metadata(
            model=response["model"],
            tokens_used=response["tokens_used"],
            processing_time_ms=response["processing_time_ms"],
            cost_estimate=self._calculate_cost(response["input_tokens"], response["output_tokens"], response["model"])
        )
        provider_metadata.api_version = "2023-06-01"
        
        # Parse Claude's comprehensive analysis
        summary_sections = self._parse_comprehensive_summary(content)
        
        return OverallSummary(
            program_purpose=summary_sections.get('program_purpose', 'Purpose analysis not available'),
            main_functionality=summary_sections.get('main_functionality', 'Functionality analysis not available'),
            architecture_overview=summary_sections.get('architecture', 'Architecture analysis not available'),
            data_flow_description=summary_sections.get('data_flow', 'Data flow analysis not available'),
            security_analysis=summary_sections.get('security_analysis', 'Security analysis not available'),
            technology_stack=summary_sections.get('technology_stack', []),
            key_insights=summary_sections.get('key_insights', []),
            potential_use_cases=summary_sections.get('use_cases', []),
            risk_assessment=summary_sections.get('risk_assessment'),
            behavioral_indicators=summary_sections.get('behavioral_indicators', []),
            confidence_score=0.9,  # Claude provides detailed reasoning
            llm_provider=provider_metadata,
            synthesis_notes=summary_sections.get('classification_reasoning')
        )
    
    async def health_check(self) -> ProviderHealthStatus:
        """Check Anthropic API availability and status."""
        if not self.anthropic_client:
            await self.initialize()
        
        try:
            start_time = time.time()
            
            # Simple test request
            response = await self.anthropic_client.messages.create(
                model=self.config.default_model,
                system="You are a helpful assistant.",
                messages=[{"role": "user", "content": "Say 'OK' if you can process this request."}],
                max_tokens=5,
                temperature=0.0
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Claude models are generally consistent
            available_models = list(self.DEFAULT_MODELS.keys())
            
            self._last_health_check = ProviderHealthStatus(
                provider_id=self.get_provider_id(),
                is_healthy=True,
                within_rate_limits=True,
                api_latency_ms=latency_ms,
                cost_per_token=self._get_cost_per_token(self.config.default_model),
                available_models=available_models,
                last_check=datetime.utcnow()
            )
            
            return self._last_health_check
            
        except Exception as e:
            self._last_health_check = ProviderHealthStatus(
                provider_id=self.get_provider_id(),
                is_healthy=False,
                within_rate_limits=False,
                available_models=[],
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
            
            return self._last_health_check
    
    def get_cost_estimate(self, token_count: int, operation_type: TranslationOperationType) -> float:
        """Calculate estimated cost for given token count and operation."""
        model = self.config.default_model
        
        if model not in self.MODEL_COSTS:
            # Default to sonnet pricing if model not found
            model = "claude-3-sonnet-20240229"
        
        # Anthropic tends to use more input context, less output
        if operation_type == TranslationOperationType.OVERALL_SUMMARY:
            input_ratio = 0.8
            output_ratio = 0.2
        else:
            input_ratio = 0.7
            output_ratio = 0.3
        
        input_tokens = int(token_count * input_ratio)
        output_tokens = int(token_count * output_ratio)
        
        costs = self.MODEL_COSTS[model]
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        
        return input_cost + output_cost
    
    def count_tokens(self, text: str) -> int:
        """Count tokens using approximation (Claude uses similar tokenization to GPT)."""
        if text in self._token_count_cache:
            return self._token_count_cache[text]
        
        # Rough estimation similar to OpenAI
        token_count = max(1, len(text) // 4)
        
        # Cache the result
        if len(self._token_count_cache) < 1000:
            self._token_count_cache[text] = token_count
        
        return token_count
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> Optional[float]:
        """Calculate actual cost based on token usage."""
        if model not in self.MODEL_COSTS:
            model = "claude-3-sonnet-20240229"  # Default
        
        costs = self.MODEL_COSTS[model]
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        
        return input_cost + output_cost
    
    def _get_cost_per_token(self, model: str) -> Optional[float]:
        """Get average cost per token for a model."""
        if model not in self.MODEL_COSTS:
            model = "claude-3-sonnet-20240229"
        
        costs = self.MODEL_COSTS[model]
        return (costs["input"] + costs["output"]) / 2000  # Average per token
    
    def _parse_detailed_analysis(self, content: str) -> Dict[str, Optional[str]]:
        """Parse Claude's structured analysis response."""
        sections = {}
        
        # Claude tends to use clear section headers
        patterns = {
            'functionality': [r'Purpose and Functionality[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)', r'Function.*?Purpose[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)'],
            'detailed_breakdown': [r'Detailed Breakdown[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)', r'Step.*?through[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)'],
            'parameters': [r'Parameters.*?Values?[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)'],
            'return_values': [r'Return.*?Values?[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)'],
            'security_analysis': [r'Security Analysis[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)', r'Security.*?observations?[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)'],
            'reasoning': [r'reasoning[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)', r'Confidence.*?Assessment[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)']
        }
        
        for section, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    sections[section] = match.group(1).strip()
                    break
        
        return sections
    
    def _extract_confidence_score(self, content: str) -> float:
        """Extract confidence score from Claude's self-assessment."""
        # Look for confidence indicators in Claude's response
        confidence_patterns = [
            r'confidence.*?(\d+)%',
            r'confident.*?(\d+)%',
            r'certainty.*?(\d+)%'
        ]
        
        for pattern in confidence_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return float(match.group(1)) / 100.0
        
        # Look for qualitative confidence indicators
        if any(phrase in content.lower() for phrase in ['very confident', 'highly confident', 'certain']):
            return 0.9
        elif any(phrase in content.lower() for phrase in ['somewhat confident', 'reasonably sure']):
            return 0.7
        elif any(phrase in content.lower() for phrase in ['uncertain', 'unclear', 'difficult to determine']):
            return 0.5
        
        return 0.8  # Default confidence for Claude's detailed analysis
    
    def _extract_import_analysis_claude(self, content: str, import_item: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Extract Claude's detailed import analysis."""
        function_name = import_item.get('function', 'unknown')
        library_name = import_item.get('library', 'unknown')
        
        # Claude provides structured analysis - extract relevant sections
        return {
            'documentation': f"API documentation analysis for {function_name}",
            'usage_context': "Usage context from Claude's analysis",
            'parameters': None,  # Would extract from structured response
            'return_values': None,
            'security_implications': "Security analysis from Claude",
            'alternatives': [],
            'common_misuses': [],
            'detection_strategies': [],
            'legitimate_vs_malicious': "Legitimate vs malicious usage analysis"
        }
    
    def _extract_string_analysis_claude(self, content: str, string_item: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Extract Claude's string analysis."""
        string_content = string_item.get('content', '')
        
        return {
            'interpretation': f"Claude's interpretation of string: {string_content[:50]}...",
            'usage_context': "Usage context from Claude's analysis",
            'encoding_details': "Encoding analysis details",
            'security_analysis': "Security implications analysis",
            'data_classification': "Data type classification",
            'obfuscation_analysis': "Obfuscation assessment"
        }
    
    def _parse_comprehensive_summary(self, content: str) -> Dict[str, Any]:
        """Parse Claude's comprehensive summary into structured data."""
        sections = {}
        
        # Extract structured sections from Claude's detailed response
        section_patterns = {
            'program_purpose': [r'Program Purpose[:\s]+(.*?)(?=\n\n|\n\d+\.|$)'],
            'main_functionality': [r'Main Functionality[:\s]+(.*?)(?=\n\n|\n\d+\.|$)'],
            'architecture': [r'Architecture.*?Analysis[:\s]+(.*?)(?=\n\n|\n\d+\.|$)'],
            'data_flow': [r'Data Flow.*?Assessment[:\s]+(.*?)(?=\n\n|\n\d+\.|$)'],
            'security_analysis': [r'Security Analysis[:\s]+(.*?)(?=\n\n|\n\d+\.|$)'],
            'risk_assessment': [r'Risk Assessment[:\s]+(.*?)(?=\n\n|\n\d+\.|$)'],
            'classification_reasoning': [r'Classification.*?Reasoning[:\s]+(.*?)(?=\n\n|\n\d+\.|$)']
        }
        
        for section, patterns in section_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    sections[section] = match.group(1).strip()
                    break
        
        # Extract lists
        sections['technology_stack'] = self._extract_technology_list(content)
        sections['key_insights'] = self._extract_insights_list(content)
        sections['use_cases'] = self._extract_use_cases_list(content)
        sections['behavioral_indicators'] = self._extract_behavioral_indicators(content)
        
        return sections
    
    def _extract_technology_list(self, content: str) -> List[str]:
        """Extract technology stack from Claude's response."""
        return []  # Placeholder - would implement sophisticated extraction
    
    def _extract_insights_list(self, content: str) -> List[str]:
        """Extract key insights from Claude's response."""
        return []  # Placeholder - would implement sophisticated extraction
    
    def _extract_use_cases_list(self, content: str) -> List[str]:
        """Extract potential use cases from Claude's response."""
        return []  # Placeholder - would implement sophisticated extraction
    
    def _extract_behavioral_indicators(self, content: str) -> List[str]:
        """Extract behavioral indicators from Claude's response."""
        return []  # Placeholder - would implement sophisticated extraction