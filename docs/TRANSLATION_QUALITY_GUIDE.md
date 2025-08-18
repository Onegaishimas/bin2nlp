# Translation Quality & Prompt Tuning Guide

This guide covers translation quality expectations, assessment metrics, and prompt optimization strategies for different LLM providers in bin2nlp.

## 📊 Quality Standards Overview

### Quality Assessment Framework

bin2nlp evaluates translation quality across four dimensions:

1. **Technical Accuracy** (40%): Correct interpretation of assembly instructions and program logic
2. **Completeness** (25%): Coverage of all relevant code elements and behavior patterns  
3. **Clarity & Readability** (25%): Human-readable explanations accessible to target audience
4. **Context Relevance** (10%): Appropriate level of detail for the specific use case

### Quality Score Scale

| Score | Quality Level | Description |
|-------|---------------|-------------|
| 9.0-10.0 | Excellent | Expert-level analysis, comprehensive and accurate |
| 8.0-8.9 | Very Good | High quality with minor gaps or inaccuracies |
| 7.0-7.9 | Good | Solid analysis, suitable for most use cases |
| 6.0-6.9 | Fair | Basic accuracy but missing important details |
| 5.0-5.9 | Poor | Significant inaccuracies or incomplete analysis |
| 0.0-4.9 | Unacceptable | Major errors or failed translation |

## 🎯 Provider-Specific Quality Profiles

### OpenAI GPT-4
**Strengths:**
- **Technical precision**: Excellent understanding of x86/x64 assembly instructions
- **Structured output**: Consistent formatting and organization
- **API familiarity**: Strong knowledge of Windows/Linux/macOS system calls
- **Security analysis**: Good detection of malicious patterns

**Typical Quality Range**: 8.5-9.5 (Very Good to Excellent)

**Best For:**
- Complex malware analysis
- Detailed function-by-function breakdown
- Security-focused explanations
- Professional reports and documentation

**Example Quality Indicators:**
```json
{
  "technical_accuracy": 9.2,
  "completeness": 8.8,
  "clarity_readability": 9.0,
  "context_relevance": 8.5,
  "overall_quality": 8.9
}
```

### Anthropic Claude
**Strengths:**
- **Contextual reasoning**: Superior understanding of program flow and dependencies
- **Comprehensive analysis**: Thorough coverage of complex behaviors
- **Natural language**: Most human-readable explanations
- **Edge case handling**: Better at analyzing unusual or obfuscated code

**Typical Quality Range**: 8.8-9.6 (Very Good to Excellent)

**Best For:**
- Complex business logic analysis
- Educational explanations
- Research and academic use
- Deep technical documentation

**Example Quality Indicators:**
```json
{
  "technical_accuracy": 9.1,
  "completeness": 9.4,
  "clarity_readability": 9.3,
  "context_relevance": 9.2,
  "overall_quality": 9.2
}
```

### Google Gemini
**Strengths:**
- **Processing speed**: Fastest response times
- **Cost efficiency**: Best price-to-quality ratio
- **Practical focus**: Good at identifying main program purposes
- **Balanced detail**: Appropriate depth for most use cases

**Typical Quality Range**: 7.8-8.5 (Good to Very Good)

**Best For:**
- Batch processing of many files
- Quick program classification
- Cost-conscious deployments
- Initial triage and filtering

**Example Quality Indicators:**
```json
{
  "technical_accuracy": 8.2,
  "completeness": 7.9,
  "clarity_readability": 8.4,
  "context_relevance": 8.0,
  "overall_quality": 8.1
}
```

### Ollama (Local)
**Strengths:**
- **Privacy**: No data leaves your infrastructure
- **Cost**: Zero API costs for unlimited usage
- **Customization**: Can fine-tune models for specific domains
- **Availability**: No rate limits or service dependencies

**Typical Quality Range**: 7.2-8.2 (Good to Very Good)

**Best For:**
- Sensitive or proprietary binaries
- Development and testing environments
- High-volume processing without API costs
- Custom model training and experimentation

**Example Quality Indicators:**
```json
{
  "technical_accuracy": 7.8,
  "completeness": 7.5,
  "clarity_readability": 8.0,
  "context_relevance": 7.9,
  "overall_quality": 7.8
}
```

## 🔧 Prompt Engineering Strategies

### Base Prompt Structure

All providers use a standardized prompt template:

```
SYSTEM: You are an expert binary analysis assistant specializing in translating assembly code and decompiled functions into clear, natural language explanations.

Your task is to analyze the provided function data and create a comprehensive, human-readable explanation that would be valuable for [audience].

Focus on:
1. The function's primary purpose and behavior
2. Input parameters and their types
3. Return values and their significance
4. Key operations and logic flow
5. Any notable patterns, algorithms, or security implications
6. Cross-references to other functions or external dependencies

USER: Please translate this decompiled function into a natural language explanation:

**Function Information:**
- Name: {function_name}
- Address: {function_address}
- Size: {function_size} bytes

**Decompiled Code:**
```c
{decompiled_code}
```

**Assembly Context:**
```assembly
{assembly_sample}
```

**Function Calls:** {function_calls}
**Variables:** {variables}

Provide a comprehensive explanation in 2-4 paragraphs that explains what this function does, how it works, and why it matters.
```

### Provider-Specific Optimizations

#### OpenAI GPT-4 Optimization
```python
OPENAI_OPTIMIZATIONS = {
    "temperature": 0.1,  # Low for consistency
    "system_prompt_additions": [
        "Be precise with technical terminology.",
        "Structure your response with clear sections.",
        "Include security implications when relevant.",
        "Reference specific assembly instructions when explaining behavior."
    ],
    "user_prompt_additions": [
        "Format your response with clear section headers if the explanation is complex."
    ],
    "max_tokens": 4096,
    "stop_sequences": ["```", "---"]
}
```

#### Anthropic Claude Optimization  
```python
ANTHROPIC_OPTIMIZATIONS = {
    "temperature": 0.1,
    "system_prompt_additions": [
        "Be thorough but concise. Focus on technical accuracy while remaining accessible.",
        "Explain the reasoning behind your analysis.",
        "Consider the broader context of how this function fits into the overall program."
    ],
    "max_tokens": 4096,
    "top_p": 0.95
}
```

#### Google Gemini Optimization
```python
GEMINI_OPTIMIZATIONS = {
    "temperature": 0.2,
    "system_prompt_additions": [
        "Provide practical, actionable explanations.",
        "Focus on the most important aspects first.",
        "Be concise but comprehensive."
    ],
    "max_tokens": 2048,
    "candidate_count": 1
}
```

#### Ollama Optimization
```python
OLLAMA_OPTIMIZATIONS = {
    "temperature": 0.1,
    "system_prompt_additions": [
        "Focus on clear, straightforward explanations.",
        "Emphasize the practical purpose and behavior.",
        "Keep technical jargon to a minimum unless necessary."
    ],
    "max_tokens": 2048,
    "repeat_penalty": 1.1
}
```

### Context-Aware Prompting

#### For Different Binary Types

**Malware Analysis Prompts:**
```
Additional Context: This binary has been flagged by security tools as potentially malicious. Pay special attention to:
- Obfuscation techniques or anti-analysis measures
- Network communication and data exfiltration
- Persistence mechanisms and system modifications
- Privilege escalation attempts
- Payload delivery or execution methods
```

**Legitimate Software Analysis:**
```
Additional Context: This appears to be legitimate business software. Focus on:
- Core business logic and application functionality
- User interface and interaction patterns
- Data processing and storage mechanisms
- Integration with system services
- Performance and optimization characteristics
```

**System Utility Analysis:**
```
Additional Context: This is a system utility or administrative tool. Emphasize:
- System interactions and administrative functions
- Permission requirements and security considerations
- Configuration and deployment aspects
- Integration with existing system infrastructure
```

#### For Different Audiences

**Security Analyst Prompt:**
```
Target Audience: Security analysts and incident responders who need to understand potential threats and attack vectors.

Focus your explanation on:
- Security implications and potential risks
- Indicators of compromise (IoCs)
- Attack techniques and methodologies
- Defensive recommendations
```

**Developer Prompt:**
```
Target Audience: Software developers who need to understand code structure and implementation patterns.

Focus your explanation on:
- Programming patterns and algorithms used
- Code quality and maintainability aspects
- Performance characteristics
- Integration points and dependencies
```

**Technical Writer Prompt:**
```
Target Audience: Technical writers creating documentation for end users.

Focus your explanation on:
- High-level functionality and user benefits
- Key features and capabilities
- Usage scenarios and workflows
- Important limitations or considerations
```

## 📈 Quality Optimization Techniques

### 1. Multi-Shot Prompting

For complex binaries, use multi-shot prompting with examples:

```python
def create_few_shot_prompt(function_data):
    examples = [
        {
            "input": "Simple main function with printf",
            "output": "This is a standard C program entry point that prints a greeting message to the console and exits successfully."
        },
        {
            "input": "Network socket creation function",
            "output": "This function establishes a TCP network connection by creating a socket, configuring connection parameters, and attempting to connect to a remote server."
        }
    ]
    
    prompt = "Here are examples of good function translations:\n\n"
    for i, example in enumerate(examples, 1):
        prompt += f"Example {i}:\n"
        prompt += f"Input: {example['input']}\n"
        prompt += f"Output: {example['output']}\n\n"
    
    prompt += f"Now translate this function:\n{function_data}"
    return prompt
```

### 2. Chain-of-Thought Reasoning

Encourage step-by-step analysis for complex functions:

```
Break down your analysis into these steps:
1. First, identify the function's primary purpose from its name and initial operations
2. Analyze the input parameters and their validation
3. Trace through the main logic flow and key operations
4. Identify the return value and what it represents
5. Note any side effects or external interactions
6. Summarize the overall behavior and significance
```

### 3. Iterative Refinement

For critical analyses, use multi-pass refinement:

```python
def iterative_analysis(function_data, provider="anthropic"):
    # Pass 1: Basic analysis
    initial_analysis = analyze_function(function_data, provider, detail="brief")
    
    # Pass 2: Detailed analysis with initial context
    detailed_prompt = f"""
    Previous analysis: {initial_analysis}
    
    Now provide a more detailed analysis, correcting any errors in the initial assessment and adding deeper insights.
    """
    
    refined_analysis = analyze_function_with_prompt(function_data, detailed_prompt, provider)
    
    return refined_analysis
```

### 4. Quality Validation

Implement automated quality checks:

```python
def validate_translation_quality(translation, function_data):
    quality_checks = {
        "mentions_function_name": function_data["name"].lower() in translation.lower(),
        "explains_parameters": "parameter" in translation.lower() or "argument" in translation.lower(),
        "describes_behavior": any(verb in translation.lower() for verb in ["performs", "executes", "processes", "handles"]),
        "appropriate_length": 100 <= len(translation) <= 1000,
        "technical_depth": any(term in translation.lower() for term in ["api", "system", "memory", "register"])
    }
    
    quality_score = sum(quality_checks.values()) / len(quality_checks)
    
    return {
        "quality_score": quality_score,
        "checks": quality_checks,
        "issues": [check for check, passed in quality_checks.items() if not passed]
    }
```

## 🔍 Quality Monitoring and Improvement

### Automated Quality Assessment

```python
class QualityAssessor:
    def __init__(self):
        self.technical_keywords = ["function", "parameter", "return", "memory", "register", "api", "system"]
        self.behavior_verbs = ["performs", "executes", "processes", "handles", "manages", "implements"]
        
    def assess_technical_accuracy(self, translation, function_data):
        """Assess technical accuracy based on keyword presence and context"""
        score = 0.0
        
        # Check for function name mention
        if function_data["name"].lower() in translation.lower():
            score += 0.3
            
        # Check for technical terminology
        tech_count = sum(1 for keyword in self.technical_keywords if keyword in translation.lower())
        score += min(tech_count / len(self.technical_keywords), 0.3)
        
        # Check for behavioral description
        behavior_count = sum(1 for verb in self.behavior_verbs if verb in translation.lower())
        score += min(behavior_count / 3, 0.2)
        
        # Check assembly reference integration
        if any(addr in translation for addr in function_data.get("addresses", [])):
            score += 0.2
            
        return min(score, 1.0)
    
    def assess_completeness(self, translation, function_data):
        """Assess completeness of the analysis"""
        elements = {
            "purpose": any(word in translation.lower() for word in ["purpose", "function", "role"]),
            "parameters": "parameter" in translation.lower() or "argument" in translation.lower(),
            "behavior": any(verb in translation.lower() for verb in self.behavior_verbs),
            "return_value": "return" in translation.lower(),
            "context": any(word in translation.lower() for word in ["program", "application", "system"])
        }
        
        return sum(elements.values()) / len(elements)
    
    def assess_clarity(self, translation):
        """Assess readability and clarity"""
        sentences = translation.split('.')
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
        
        # Ideal sentence length: 15-25 words
        length_score = 1.0 - abs(avg_sentence_length - 20) / 20 if avg_sentence_length > 0 else 0
        
        # Check for appropriate paragraph structure
        paragraphs = translation.split('\n\n')
        structure_score = min(len(paragraphs) / 3, 1.0)  # Ideal: 2-3 paragraphs
        
        # Avoid excessive technical jargon density
        words = translation.lower().split()
        jargon_density = sum(1 for word in words if word in self.technical_keywords) / len(words) if words else 0
        jargon_score = 1.0 if jargon_density < 0.15 else max(0, 1.0 - (jargon_density - 0.15) * 2)
        
        return (length_score + structure_score + jargon_score) / 3
```

### Quality Improvement Strategies

#### 1. Provider Selection Based on Content

```python
def select_optimal_provider(function_data):
    """Select best provider based on function characteristics"""
    
    # Complex functions -> Anthropic
    if function_data.get("complexity_score", 0) > 8:
        return "anthropic"
    
    # Security-related functions -> OpenAI
    security_keywords = ["encrypt", "decrypt", "auth", "security", "hash"]
    if any(keyword in function_data["name"].lower() for keyword in security_keywords):
        return "openai"
    
    # Simple utility functions -> Gemini
    if function_data.get("line_count", 0) < 50:
        return "gemini"
    
    # Default to OpenAI
    return "openai"
```

#### 2. Dynamic Prompt Adjustment

```python
def adjust_prompt_for_quality(function_data, previous_attempts=[]):
    """Adjust prompt based on previous quality issues"""
    
    base_prompt = get_base_translation_prompt(function_data)
    
    # If previous attempts lacked technical detail
    if any("low_technical_accuracy" in attempt.get("issues", []) for attempt in previous_attempts):
        base_prompt += "\nEmphasize technical details and precise terminology."
    
    # If previous attempts were too brief
    if any("insufficient_detail" in attempt.get("issues", []) for attempt in previous_attempts):
        base_prompt += "\nProvide comprehensive explanations with examples where appropriate."
    
    # If previous attempts missed security implications
    security_indicators = ["encrypt", "network", "memory", "privilege"]
    if (any(indicator in function_data["name"].lower() for indicator in security_indicators) and
        any("missed_security_implications" in attempt.get("issues", []) for attempt in previous_attempts)):
        base_prompt += "\nPay special attention to security implications and potential risks."
    
    return base_prompt
```

#### 3. Quality Feedback Loop

```python
class QualityFeedbackSystem:
    def __init__(self):
        self.quality_history = []
        
    def record_quality_metrics(self, provider, function_type, quality_scores):
        """Record quality metrics for continuous improvement"""
        self.quality_history.append({
            "timestamp": datetime.now(),
            "provider": provider,
            "function_type": function_type,
            "quality_scores": quality_scores
        })
        
    def get_provider_performance_trend(self, provider, days=30):
        """Analyze provider performance trends"""
        cutoff_date = datetime.now() - timedelta(days=days)
        recent_scores = [
            entry["quality_scores"]["overall_quality"]
            for entry in self.quality_history
            if entry["provider"] == provider and entry["timestamp"] > cutoff_date
        ]
        
        if not recent_scores:
            return None
            
        return {
            "average_quality": statistics.mean(recent_scores),
            "quality_trend": self._calculate_trend(recent_scores),
            "consistency": 1.0 - statistics.stdev(recent_scores) if len(recent_scores) > 1 else 1.0
        }
        
    def recommend_provider_for_function_type(self, function_type):
        """Recommend best provider based on historical performance"""
        type_performance = {}
        
        for provider in ["openai", "anthropic", "gemini", "ollama"]:
            scores = [
                entry["quality_scores"]["overall_quality"]
                for entry in self.quality_history
                if entry["provider"] == provider and entry["function_type"] == function_type
            ]
            
            if scores:
                type_performance[provider] = statistics.mean(scores)
        
        if not type_performance:
            return "openai"  # Default
            
        return max(type_performance, key=type_performance.get)
```

## 📚 Best Practices Summary

### Do's ✅

1. **Use appropriate detail levels** for your audience
2. **Select providers** based on content complexity and requirements
3. **Implement quality monitoring** for continuous improvement
4. **Use context-aware prompting** for different binary types
5. **Validate translation quality** with automated checks
6. **Monitor costs** while maintaining quality standards
7. **Implement fallback chains** for reliability

### Don'ts ❌

1. **Don't use the same prompt** for all providers without optimization
2. **Don't ignore quality scores** - they indicate translation reliability  
3. **Don't over-optimize for cost** at the expense of critical accuracy
4. **Don't skip validation** for security-critical analyses
5. **Don't rely on single providers** for important analyses
6. **Don't ignore provider-specific strengths** and weaknesses

### Quality Optimization Checklist

- [ ] Prompt templates optimized for each provider
- [ ] Quality assessment metrics implemented
- [ ] Provider selection logic based on content type
- [ ] Automated quality validation in place
- [ ] Fallback chains configured for reliability
- [ ] Cost vs. quality monitoring active
- [ ] Regular quality trend analysis performed
- [ ] Feedback loop for continuous improvement

## 🔧 Configuration Examples

### High-Quality Configuration (Research/Security)

```python
RESEARCH_CONFIG = {
    "preferred_providers": ["anthropic", "openai"],
    "quality_threshold": 8.5,
    "translation_detail": "comprehensive",
    "enable_multi_pass_analysis": True,
    "enable_quality_validation": True,
    "cost_limit_per_analysis": 10.0
}
```

### Balanced Configuration (Production)

```python
PRODUCTION_CONFIG = {
    "preferred_providers": ["openai", "gemini", "ollama"],
    "quality_threshold": 7.5,
    "translation_detail": "standard", 
    "enable_fallback_chain": True,
    "cost_limit_per_analysis": 2.0,
    "cache_results": True
}
```

### Cost-Optimized Configuration (Batch Processing)

```python
BATCH_CONFIG = {
    "preferred_providers": ["gemini", "ollama"],
    "quality_threshold": 7.0,
    "translation_detail": "brief",
    "enable_caching": True,
    "cost_limit_per_analysis": 0.50,
    "parallel_processing": True
}
```

---

For more detailed information on specific providers and advanced optimization techniques, see:
- [LLM Provider Guide](./LLM_PROVIDER_GUIDE.md)
- [API Usage Examples](./API_USAGE_EXAMPLES.md)  
- [Performance Benchmarks](./BENCHMARKS.md)

*Last updated: 2025-08-18*