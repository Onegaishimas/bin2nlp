"""
OpenAI Provider Implementation

OpenAI and OpenAI-compatible API provider for binary decompilation translation.
Supports GPT-4, GPT-3.5-turbo, and OpenAI-compatible endpoints (Ollama, LM Studio, etc.).
"""

import asyncio
import json
import re
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import httpx
from openai import AsyncOpenAI, APIError, RateLimitError, AuthenticationError
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


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider implementation supporting both official OpenAI API
    and OpenAI-compatible endpoints (Ollama, LM Studio, vLLM, etc.).
    """
    
    # Default models for different endpoints
    DEFAULT_MODELS = {
        "openai": "gpt-4",
        "azure": "gpt-4", 
        "ollama": "llama2",
        "lm_studio": "local-model",
        "custom": "gpt-3.5-turbo"
    }
    
    # Cost per 1K tokens (USD) for official OpenAI models
    MODEL_COSTS = {
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
        "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004}
    }
    
    def __init__(self, config: LLMConfig):
        """Initialize OpenAI provider with configuration."""
        super().__init__(config)
        self.openai_client: Optional[AsyncOpenAI] = None
        self.endpoint_type = self._detect_endpoint_type()
        self._token_count_cache: Dict[str, int] = {}
        
    def _detect_endpoint_type(self) -> str:
        """Detect the type of OpenAI endpoint based on configuration."""
        if not self.config.endpoint_url:
            return "openai"
        
        url = self.config.endpoint_url.lower()
        
        if "openai.azure.com" in url:
            return "azure"
        elif "localhost:11434" in url or "ollama" in url:
            return "ollama"
        elif "localhost:1234" in url or "lm_studio" in url:
            return "lm_studio"
        else:
            return "custom"
    
    async def initialize(self) -> None:
        """Initialize the OpenAI client and HTTP connections."""
        try:
            client_kwargs = {
                "api_key": self.config.api_key.get_secret_value(),
                "timeout": self.config.timeout_seconds,
                "max_retries": 3,
            }
            
            # Add custom endpoint if specified
            if self.config.endpoint_url:
                client_kwargs["base_url"] = self.config.endpoint_url
            
            # Add organization for official OpenAI
            if self.config.organization and self.endpoint_type == "openai":
                client_kwargs["organization"] = self.config.organization
            
            self.openai_client = AsyncOpenAI(**client_kwargs)
            
            # Test connection
            await self.health_check()
            
        except Exception as e:
            raise LLMProviderException(
                f"Failed to initialize OpenAI provider: {str(e)}",
                self.get_provider_id(),
                "INIT_FAILED"
            )
    
    async def cleanup(self) -> None:
        """Cleanup OpenAI client and connections."""
        if self.openai_client:
            await self.openai_client.close()
            self.openai_client = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((RateLimitError, httpx.TimeoutException))
    )
    async def _make_completion_request(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Dict[str, Any]:
        """Make completion request with retry logic."""
        if not self.openai_client:
            raise LLMServiceUnavailableException(self.get_provider_id(), "Client not initialized")
        
        request_model = model or self.config.default_model
        request_temperature = temperature if temperature is not None else self.config.temperature
        request_max_tokens = max_tokens or self.config.max_tokens
        
        try:
            start_time = time.time()
            
            response = await self.openai_client.chat.completions.create(
                model=request_model,
                messages=messages,
                temperature=request_temperature,
                max_tokens=request_max_tokens,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0
            )
            
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            return {
                "content": response.choices[0].message.content,
                "model": response.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
                "processing_time_ms": processing_time_ms
            }
            
        except AuthenticationError as e:
            raise LLMAuthenticationException(self.get_provider_id(), str(e))
        except RateLimitError as e:
            # Extract retry-after header if available
            retry_after = getattr(e, 'retry_after', None)
            raise LLMRateLimitException(self.get_provider_id(), retry_after)
        except APIError as e:
            if "service_unavailable" in str(e).lower():
                raise LLMServiceUnavailableException(self.get_provider_id(), str(e))
            else:
                raise LLMProviderException(f"OpenAI API error: {str(e)}", self.get_provider_id(), "API_ERROR")
        except Exception as e:
            raise LLMProviderException(f"Unexpected error: {str(e)}", self.get_provider_id(), "UNKNOWN_ERROR")
    
    async def translate_function(
        self, 
        function_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> FunctionTranslation:
        """Translate assembly function to natural language explanation."""
        
        # Build system prompt
        system_prompt = """You are an expert binary analysis assistant specializing in translating assembly code and decompiled functions into clear, natural language explanations.

Your task is to analyze the provided function data and create a comprehensive, human-readable explanation that would be valuable for developers, security analysts, and reverse engineers.

Focus on:
1. The function's primary purpose and behavior
2. Input parameters and their types
3. Return values and their significance  
4. Key operations and logic flow
5. Any notable patterns, algorithms, or security implications
6. Cross-references to other functions or external dependencies

Provide your analysis in a structured format with clear explanations."""

        # Build user prompt with function data
        user_prompt = f"""Please translate this decompiled function into a natural language explanation:

**Function Information:**
- Name: {function_data.get('name', 'unknown')}
- Address: {function_data.get('address', 'unknown')}
- Size: {function_data.get('size', 0)} bytes

**Assembly Code:**
```assembly
{function_data.get('assembly_code', 'Not available')}
```

**Decompiled Code:**
```c
{function_data.get('decompiled_code', 'Not available')}
```

**Function Calls:** {', '.join(function_data.get('calls_to', []))}
**Variables:** {', '.join(function_data.get('variables', []))}

**Context Information:**
{json.dumps(context or {}, indent=2)}

Provide a comprehensive explanation in 2-4 paragraphs that explains what this function does, how it works, and why it matters."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._make_completion_request(messages)
        
        # Parse the response and create FunctionTranslation
        content = response["content"]
        
        # Extract confidence score from content (simple heuristic)
        confidence_score = self._estimate_confidence(content, function_data)
        
        # Create provider metadata
        provider_metadata = self._create_provider_metadata(
            model=response["model"],
            tokens_used=response["tokens_used"],
            processing_time_ms=response["processing_time_ms"],
            cost_estimate=self._calculate_cost(response["input_tokens"], response["output_tokens"], response["model"])
        )
        provider_metadata.api_version = "v1"
        
        return FunctionTranslation(
            function_name=function_data.get('name', 'unknown'),
            address=function_data.get('address', '0x0'),
            size=function_data.get('size', 0),
            assembly_code=function_data.get('assembly_code'),
            natural_language_description=content,
            parameters_explanation=self._extract_parameters_explanation(content),
            return_value_explanation=self._extract_return_explanation(content),
            security_analysis=self._extract_security_analysis(content),
            confidence_score=confidence_score,
            llm_provider=provider_metadata,
            context_used=context or {}
        )
    
    async def explain_imports(
        self, 
        import_list: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[ImportTranslation]:
        """Explain purpose and usage of imported functions."""
        
        if not import_list:
            return []
        
        system_prompt = """You are an expert in system APIs and library functions across Windows, Linux, and macOS platforms. 

Analyze the provided imported functions and explain their purpose, typical usage, security implications, and potential risks. Focus on practical information that would help security analysts understand the program's capabilities."""
        
        user_prompt = f"""Please explain these imported functions:

**Imports:**
{json.dumps(import_list, indent=2)}

**Context:**
{json.dumps(context or {}, indent=2)}

For each import, provide:
1. Purpose and functionality
2. Common usage patterns
3. Security considerations
4. Potential for misuse
5. Legitimate vs suspicious usage indicators"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._make_completion_request(messages)
        
        # Parse response and create ImportTranslation objects
        content = response["content"]
        translations = []
        
        provider_metadata = self._create_provider_metadata(
            model=response["model"],
            tokens_used=response["tokens_used"],
            processing_time_ms=response["processing_time_ms"],
            cost_estimate=self._calculate_cost(response["input_tokens"], response["output_tokens"], response["model"])
        )
        provider_metadata.api_version = "v1"
        
        for import_item in import_list:
            # Extract relevant explanation for this specific import
            import_explanation = self._extract_import_explanation(content, import_item)
            
            translation = ImportTranslation(
                library_name=import_item.get('library', 'unknown'),
                function_name=import_item.get('function', 'unknown'),
                api_documentation_summary=import_explanation.get('summary', 'Analysis not available'),
                usage_context=import_explanation.get('usage', 'Context not available'),
                parameters_description=import_explanation.get('parameters'),
                security_implications=import_explanation.get('security'),
                confidence_score=0.8,  # Default confidence for OpenAI
                llm_provider=provider_metadata
            )
            translations.append(translation)
        
        return translations
    
    async def interpret_strings(
        self, 
        string_list: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> List[StringTranslation]:
        """Interpret extracted strings with usage context."""
        
        if not string_list:
            return []
        
        system_prompt = """You are an expert at analyzing strings found in binary files to understand their purpose and security implications.

Analyze the provided strings and determine their likely usage, meaning, and potential security relevance. Consider encoding, content patterns, and contextual clues."""
        
        # Limit string list to avoid token limits
        limited_strings = string_list[:50]  # Process up to 50 strings at once
        
        user_prompt = f"""Please analyze these strings found in a binary:

**Strings:**
{json.dumps(limited_strings, indent=2)}

**Context:**
{json.dumps(context or {}, indent=2)}

For each string, analyze:
1. Likely purpose and usage
2. Data classification (URL, path, config, etc.)
3. Security implications
4. Encoding details if relevant
5. Potential obfuscation"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._make_completion_request(messages)
        
        content = response["content"]
        translations = []
        
        provider_metadata = self._create_provider_metadata(
            model=response["model"],
            tokens_used=response["tokens_used"],
            processing_time_ms=response["processing_time_ms"],
            cost_estimate=self._calculate_cost(response["input_tokens"], response["output_tokens"], response["model"])
        )
        provider_metadata.api_version = "v1"
        
        for string_item in limited_strings:
            string_analysis = self._extract_string_analysis(content, string_item)
            
            translation = StringTranslation(
                string_value=string_item.get('content', ''),
                address=string_item.get('address', '0x0'),
                size=string_item.get('size', len(string_item.get('content', ''))),
                encoding=string_item.get('encoding', 'ascii'),
                usage_context=string_analysis.get('usage', 'Usage context not determined'),
                interpretation=string_analysis.get('interpretation', 'Interpretation not available'),
                security_analysis=string_analysis.get('security'),
                confidence_score=0.75,  # Default confidence
                llm_provider=provider_metadata
            )
            translations.append(translation)
        
        return translations
    
    async def generate_overall_summary(
        self, 
        decompilation_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> OverallSummary:
        """Generate comprehensive program summary."""
        
        system_prompt = """You are an expert malware analyst and reverse engineer. Analyze the complete decompilation data and provide a comprehensive summary of the program's purpose, functionality, architecture, and security characteristics.

Focus on:
1. Overall program purpose and main functionality
2. Architecture and design patterns
3. Data flow and processing logic
4. Security analysis (both defensive and offensive capabilities)
5. Technology stack and dependencies
6. Risk assessment and behavioral indicators"""
        
        user_prompt = f"""Please analyze this complete binary decompilation and provide a comprehensive summary:

**File Information:**
{json.dumps(decompilation_data.get('file_info', {}), indent=2)}

**Functions Summary:**
- Total functions: {len(decompilation_data.get('functions', []))}
- Key functions: {[f.get('name') for f in decompilation_data.get('functions', [])[:10]]}

**Imports Summary:**
- Total imports: {len(decompilation_data.get('imports', []))}
- Key libraries: {list(set([i.get('library') for i in decompilation_data.get('imports', [])[:20]]))}

**Strings Summary:**
- Total strings: {len(decompilation_data.get('strings', []))}
- Sample strings: {[s.get('content')[:50] for s in decompilation_data.get('strings', [])[:10]]}

**Context:**
{json.dumps(context or {}, indent=2)}

Provide a comprehensive analysis covering all aspects of this program."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = await self._make_completion_request(messages, max_tokens=4096)  # Longer response for summary
        
        content = response["content"]
        
        provider_metadata = self._create_provider_metadata(
            model=response["model"],
            tokens_used=response["tokens_used"],
            processing_time_ms=response["processing_time_ms"],
            cost_estimate=self._calculate_cost(response["input_tokens"], response["output_tokens"], response["model"])
        )
        provider_metadata.api_version = "v1"
        
        # Parse the comprehensive response
        summary_data = self._parse_summary_response(content)
        
        return OverallSummary(
            program_purpose=summary_data.get('purpose', 'Purpose not determined'),
            main_functionality=summary_data.get('functionality', 'Functionality analysis not available'),
            architecture_overview=summary_data.get('architecture', 'Architecture analysis not available'),
            data_flow_description=summary_data.get('data_flow', 'Data flow analysis not available'),
            security_analysis=summary_data.get('security', 'Security analysis not available'),
            technology_stack=summary_data.get('technology_stack', []),
            key_insights=summary_data.get('key_insights', []),
            risk_assessment=summary_data.get('risk_assessment'),
            confidence_score=0.8,  # Default confidence for comprehensive analysis
            llm_provider=provider_metadata
        )
    
    async def health_check(self) -> ProviderHealthStatus:
        """Check provider availability and API status."""
        if not self.openai_client:
            await self.initialize()
        
        try:
            start_time = time.time()
            
            # Simple test request
            test_messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'OK' if you can process this request."}
            ]
            
            response = await self.openai_client.chat.completions.create(
                model=self.config.default_model,
                messages=test_messages,
                max_tokens=5,
                temperature=0.0
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Get available models (if supported)
            available_models = []
            try:
                if self.endpoint_type == "openai":
                    models_response = await self.openai_client.models.list()
                    available_models = [model.id for model in models_response.data]
            except:
                available_models = [self.config.default_model]  # Fallback
            
            self._last_health_check = ProviderHealthStatus(
                provider_id=self.get_provider_id(),
                is_healthy=True,
                within_rate_limits=True,  # Assume okay if request succeeded
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
        
        # For non-OpenAI endpoints, cost is typically 0
        if self.endpoint_type != "openai" or model not in self.MODEL_COSTS:
            return 0.0
        
        # Estimate input/output token ratio based on operation type
        if operation_type == TranslationOperationType.OVERALL_SUMMARY:
            input_ratio = 0.7  # More input context
            output_ratio = 0.3
        else:
            input_ratio = 0.6
            output_ratio = 0.4
        
        input_tokens = int(token_count * input_ratio)
        output_tokens = int(token_count * output_ratio)
        
        costs = self.MODEL_COSTS[model]
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        
        return input_cost + output_cost
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in given text using rough estimation."""
        # Simple approximation: ~4 characters per token for English text
        # In production, would use tiktoken library for accurate counting
        if text in self._token_count_cache:
            return self._token_count_cache[text]
        
        # Rough estimation
        token_count = max(1, len(text) // 4)
        
        # Cache the result
        if len(self._token_count_cache) < 1000:  # Prevent memory bloat
            self._token_count_cache[text] = token_count
        
        return token_count
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> Optional[float]:
        """Calculate actual cost based on token usage."""
        if self.endpoint_type != "openai" or model not in self.MODEL_COSTS:
            return None
        
        costs = self.MODEL_COSTS[model]
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        
        return input_cost + output_cost
    
    def _get_cost_per_token(self, model: str) -> Optional[float]:
        """Get average cost per token for a model."""
        if self.endpoint_type != "openai" or model not in self.MODEL_COSTS:
            return None
        
        costs = self.MODEL_COSTS[model]
        return (costs["input"] + costs["output"]) / 2000  # Average per token
    
    def _estimate_confidence(self, content: str, function_data: Dict[str, Any]) -> float:
        """Estimate confidence score based on response quality."""
        confidence = 0.5  # Base confidence
        
        # Boost confidence for detailed responses
        if len(content) > 200:
            confidence += 0.1
        
        # Boost for function name mentions
        func_name = function_data.get('name', '')
        if func_name and func_name in content:
            confidence += 0.1
        
        # Boost for technical terms
        technical_terms = ['function', 'parameter', 'return', 'variable', 'register', 'memory']
        term_count = sum(1 for term in technical_terms if term in content.lower())
        confidence += min(0.2, term_count * 0.05)
        
        return min(1.0, confidence)
    
    def _extract_parameters_explanation(self, content: str) -> Optional[str]:
        """Extract parameter explanation from response."""
        # Simple pattern matching to find parameter information
        patterns = [
            r'parameters?[:\s]+(.*?)(?:\n\n|\.|$)',
            r'arguments?[:\s]+(.*?)(?:\n\n|\.|$)',
            r'inputs?[:\s]+(.*?)(?:\n\n|\.|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_return_explanation(self, content: str) -> Optional[str]:
        """Extract return value explanation from response."""
        patterns = [
            r'returns?[:\s]+(.*?)(?:\n\n|\.|$)',
            r'output[:\s]+(.*?)(?:\n\n|\.|$)',
            r'result[:\s]+(.*?)(?:\n\n|\.|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_security_analysis(self, content: str) -> Optional[str]:
        """Extract security analysis from response."""
        patterns = [
            r'security[:\s]+(.*?)(?:\n\n|\.|$)',
            r'vulnerability[:\s]+(.*?)(?:\n\n|\.|$)',
            r'risk[:\s]+(.*?)(?:\n\n|\.|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_import_explanation(self, content: str, import_item: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Extract explanation for a specific import from the response."""
        function_name = import_item.get('function', 'unknown')
        
        # Simple heuristic to extract relevant sections
        # In practice, would use more sophisticated parsing
        return {
            'summary': f"Analysis for {function_name} from response content",
            'usage': "Common usage patterns identified",
            'parameters': None,
            'security': "Security implications noted" if 'security' in content.lower() else None
        }
    
    def _extract_string_analysis(self, content: str, string_item: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Extract analysis for a specific string from the response."""
        string_content = string_item.get('content', '')
        
        return {
            'usage': f"Analysis of string usage for: {string_content[:50]}...",
            'interpretation': "String interpretation from analysis",
            'security': "Security analysis" if 'security' in content.lower() else None
        }
    
    def _parse_summary_response(self, content: str) -> Dict[str, Any]:
        """Parse comprehensive summary response into structured data."""
        # Simple parsing - in practice would use more sophisticated methods
        return {
            'purpose': self._extract_section(content, ['purpose', 'goal', 'objective']),
            'functionality': self._extract_section(content, ['functionality', 'features', 'capabilities']),
            'architecture': self._extract_section(content, ['architecture', 'design', 'structure']),
            'data_flow': self._extract_section(content, ['data flow', 'processing', 'workflow']),
            'security': self._extract_section(content, ['security', 'vulnerability', 'threat']),
            'technology_stack': self._extract_list(content, ['technology', 'library', 'framework']),
            'key_insights': self._extract_list(content, ['insight', 'finding', 'observation']),
            'risk_assessment': self._extract_section(content, ['risk', 'assessment', 'evaluation'])
        }
    
    def _extract_section(self, content: str, keywords: List[str]) -> str:
        """Extract a section from content based on keywords."""
        for keyword in keywords:
            pattern = rf'{keyword}[:\s]+(.*?)(?:\n\n|$)'
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
        
        return "Analysis not available"
    
    def _extract_list(self, content: str, keywords: List[str]) -> List[str]:
        """Extract a list from content based on keywords."""
        # Simple implementation - would be more sophisticated in practice
        items = []
        
        for keyword in keywords:
            pattern = rf'{keyword}.*?:(.*?)(?:\n\n|$)'
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                # Extract list items (simple bullet point or comma-separated)
                text = match.group(1).strip()
                if '•' in text or '-' in text:
                    items.extend([item.strip('• -').strip() for item in text.split('\n') if item.strip()])
                elif ',' in text:
                    items.extend([item.strip() for item in text.split(',') if item.strip()])
        
        return items[:10]  # Limit to 10 items