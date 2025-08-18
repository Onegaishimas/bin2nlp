# Task List: Course Correction - Binary Decompilation + Multi-LLM Translation Service
## Purge Focused Analysis Architecture and Implement Clean Decompilation Service

This task list executes a major course correction from complex binary analysis to focused decompilation + translation service:
- **Goal:** Transform bin2nlp from analysis processor system to decompilation + LLM translation service
- **Scope:** Remove all analysis processors, implement multi-LLM provider support, focus on rich translation output
- **Strategy:** Clean architectural pivot with complete removal of analysis-focused components

**Implementation Strategy:** Document correction → Code cleanup → LLM framework → API simplification → Integration testing

## Relevant Files

### Files to Remove/Major Revision
- `src/analysis/processors/security_scanner.py` - DELETE (analysis processor)
- `src/analysis/processors/function_analyzer.py` - DELETE (analysis processor)  
- `src/analysis/processors/string_extractor.py` - DELETE (analysis processor)
- `src/analysis/processors/format_detector.py` - DELETE/REPLACE (analysis processor)
- `src/analysis/engine.py` - MAJOR REVISION (remove analysis orchestration)
- `tests/unit/analysis/test_security_scanner.py` - DELETE
- `tests/unit/analysis/test_function_analyzer.py` - DELETE
- `tests/unit/analysis/test_string_extractor.py` - DELETE
- `src/models/analysis/results.py` - MAJOR REVISION (remove complex analysis models)

### Files to Create
- `src/llm/base.py` - Abstract LLM provider interface
- `src/llm/providers/openai_provider.py` - OpenAI API integration
- `src/llm/providers/anthropic_provider.py` - Anthropic Claude API integration  
- `src/llm/providers/gemini_provider.py` - Google Gemini API integration
- `src/llm/providers/factory.py` - Provider selection and configuration
- `src/llm/prompts/` - Directory for prompt templates
- `src/models/decompilation/` - New decompilation-focused data models
- `src/decompilation/engine.py` - Renamed and simplified decompilation engine

### Files to Update
- `000_PPRD|bin2nlp.md` - Remove analysis focus, add LLM translation focus
- `001_FPRD|Multi-Platform_Binary_Analysis_Engine.md` - Rename and refocus on decompilation
- `002_FPRD|RESTful_API_Interface.md` - Simplify API to decompilation endpoints
- `000_PADR|bin2nlp.md` - Update architecture for LLM providers
- `requirements.txt` - Remove analysis libs, add LLM provider clients
- `src/api/routes/analysis.py` - Rename to decompilation.py, simplify endpoints
- `src/core/config.py` - Add LLM provider configuration
- `tests/integration/test_analysis_engine.py` - Update for decompilation focus

### Notes

- **Critical Path:** Documents → Code Cleanup → LLM Framework → API → Testing
- **Parallel Work:** Dependencies can be updated parallel with LLM framework development
- **Testing Strategy:** Mock LLM responses for unit tests, real API calls for integration tests
- **Rollback Plan:** Git branches for each phase to enable selective rollback if needed

## Tasks

- [ ] 1.0 Document Architecture Correction (Critical Priority)
  - [x] 1.1 Project PRD Revision
    - [x] 1.1.1 Update `000_PPRD|bin2nlp.md` problem statement to focus on "decompilation + translation service"
    - [x] 1.1.2 Remove all "analysis processor" language and security scanner references
    - [x] 1.1.3 Add multi-LLM provider support as core feature (OpenAI API compatible, Anthropic, Gemini)
    - [x] 1.1.4 Revise success metrics to focus on translation quality and decompilation accuracy
    - [x] 1.1.5 Update feature breakdown to emphasize rich natural language output
  - [ ] 1.2 Feature PRD Corrections
    - [x] 1.2.1 Rename `001_FPRD|Multi-Platform_Binary_Analysis_Engine.md` to `001_FPRD|Binary_Decompilation_Engine.md`
    - [x] 1.2.2 Remove security scanner, function analyzer, string extractor requirements
    - [x] 1.2.3 Add rich assembly-to-language translation requirements with function-by-function detail
    - [x] 1.2.4 Update success criteria to focus on decompilation + translation quality
    - [ ] 1.2.5 Revise `002_FPRD|RESTful_API_Interface.md` to remove analysis endpoints
    - [ ] 1.2.6 Add LLM provider configuration endpoints and parameters
  - [ ] 1.3 ADR Updates
    - [ ] 1.3.1 Update `000_PADR|bin2nlp.md` to remove complex analysis architecture
    - [ ] 1.3.2 Add multi-LLM provider integration standards and patterns
    - [ ] 1.3.3 Simplify data models and API response structures
    - [ ] 1.3.4 Update dependencies section to include OpenAI, Anthropic, Gemini clients

- [ ] 2.0 Code Structure Cleanup (High Priority)  
  - [ ] 2.1 Remove Analysis Processors
    - [ ] 2.1.1 Delete `src/analysis/processors/security_scanner.py`
    - [ ] 2.1.2 Delete `src/analysis/processors/function_analyzer.py`
    - [ ] 2.1.3 Delete `src/analysis/processors/string_extractor.py`
    - [ ] 2.1.4 Delete `src/analysis/processors/format_detector.py` (replace with simple detection)
    - [ ] 2.1.5 Remove corresponding test files in `tests/unit/analysis/`
    - [ ] 2.1.6 Clean up imports and references in `src/analysis/engine.py`
  - [ ] 2.2 Simplify Data Models
    - [ ] 2.2.1 Create new `src/models/decompilation/` directory
    - [ ] 2.2.2 Replace `AnalysisResult` with `DecompilationResult` model
    - [ ] 2.2.3 Create `FunctionTranslation`, `ImportTranslation`, `StringTranslation` models
    - [ ] 2.2.4 Create `OverallSummary` model for high-level program analysis
    - [ ] 2.2.5 Remove complex security and analysis result models
    - [ ] 2.2.6 Update `src/models/analysis/` to focus on basic binary metadata only
  - [ ] 2.3 Clean Up Core Engine
    - [ ] 2.3.1 Rename `src/analysis/engine.py` to `src/decompilation/engine.py`
    - [ ] 2.3.2 Remove complex processor orchestration logic (parallel/sequential execution)
    - [ ] 2.3.3 Simplify to: radare2 extraction → LLM translation → structured response
    - [ ] 2.3.4 Remove error recovery systems for analysis processors
    - [ ] 2.3.5 Keep basic file validation and radare2 integration only

- [ ] 3.0 LLM Provider Framework Implementation (High Priority)
  - [ ] 3.1 LLM Provider Foundation
    - [ ] 3.1.1 Create `src/llm/` directory structure (`base.py`, `providers/`, `prompts/`)
    - [ ] 3.1.2 Create `src/llm/base.py` with abstract `LLMProvider` interface
    - [ ] 3.1.3 Define translation and summarization method signatures with async support
    - [ ] 3.1.4 Create `LLMConfig` model for provider configuration and API keys
    - [ ] 3.1.5 Create `LLMResponse` models for structured translation results
  - [ ] 3.2 Provider Implementations
    - [ ] 3.2.1 Create `src/llm/providers/openai_provider.py` with GPT-4 integration
    - [ ] 3.2.2 Create `src/llm/providers/anthropic_provider.py` with Claude integration
    - [ ] 3.2.3 Create `src/llm/providers/gemini_provider.py` with Google AI integration
    - [ ] 3.2.4 Implement unified error handling across providers (rate limits, API errors)
    - [ ] 3.2.5 Create `src/llm/providers/factory.py` for provider selection logic
    - [ ] 3.2.6 Add async HTTP client management and retry logic with exponential backoff
  - [ ] 3.3 Translation Prompt Engineering
    - [ ] 3.3.1 Create `src/llm/prompts/` directory for prompt templates
    - [ ] 3.3.2 Design function translation prompts (assembly → natural language with context)
    - [ ] 3.3.3 Design import/export explanation prompts with API documentation context
    - [ ] 3.3.4 Design string interpretation prompts with usage context analysis
    - [ ] 3.3.5 Design overall summary generation prompts for program purpose and flow
    - [ ] 3.3.6 Add context-aware prompting system (function vs. data vs. overall analysis)

- [ ] 4.0 Dependencies & Configuration Updates (Medium Priority)
  - [ ] 4.1 Update Dependencies
    - [ ] 4.1.1 Remove security analysis libraries from `requirements.txt`
    - [ ] 4.1.2 Add `openai>=1.0.0` for OpenAI API integration
    - [ ] 4.1.3 Add `anthropic>=0.18.0` for Claude API integration
    - [ ] 4.1.4 Add `google-generativeai>=0.3.0` for Gemini integration
    - [ ] 4.1.5 Remove unused analysis processor dependencies (complex analysis libs)
    - [ ] 4.1.6 Update `requirements-dev.txt` for LLM testing utilities and mocks
  - [ ] 4.2 Configuration Updates
    - [ ] 4.2.1 Add LLM provider configuration to `src/core/config.py`
    - [ ] 4.2.2 Add environment variables for API keys and custom endpoints
    - [ ] 4.2.3 Create LLM provider validation and fallback logic
    - [ ] 4.2.4 Update Docker configuration for new dependencies and environment
    - [ ] 4.2.5 Add LLM provider health checks to system monitoring endpoints

- [ ] 5.0 API Interface Revision (Medium Priority)
  - [ ] 5.1 Endpoint Restructuring  
    - [ ] 5.1.1 Remove specialized analysis endpoints from `src/api/routes/analysis.py`
    - [ ] 5.1.2 Rename to `src/api/routes/decompilation.py` with simplified focus
    - [ ] 5.1.3 Simplify to: `/api/v1/decompile` (POST) and `/api/v1/decompile/{job_id}` (GET)
    - [ ] 5.1.4 Add LLM provider selection parameters to API request models
    - [ ] 5.1.5 Update response models to match new `DecompilationResult` structure
  - [ ] 5.2 API Documentation Updates
    - [ ] 5.2.1 Update OpenAPI schemas for simplified decompilation endpoints
    - [ ] 5.2.2 Add LLM provider configuration examples and parameter documentation
    - [ ] 5.2.3 Update API documentation to reflect decompilation + translation focus
    - [ ] 5.2.4 Add LLM provider comparison guide and selection criteria
    - [ ] 5.2.5 Remove security analysis endpoint documentation and examples

- [ ] 6.0 Radare2 Integration Refactoring (Medium Priority)
  - [ ] 6.1 Simplify R2 Integration
    - [ ] 6.1.1 Update `src/analysis/engines/r2_integration.py` for decompilation focus
    - [ ] 6.1.2 Remove complex analysis command sequences (security, advanced analysis)  
    - [ ] 6.1.3 Focus commands on: function extraction, import/export lists, string extraction
    - [ ] 6.1.4 Add assembly code extraction with context preservation and formatting
    - [ ] 6.1.5 Simplify error handling for basic decompilation operations only
  - [ ] 6.2 Assembly Data Extraction
    - [ ] 6.2.1 Create structured assembly extraction for individual functions with metadata
    - [ ] 6.2.2 Extract import/export tables with library context and function signatures  
    - [ ] 6.2.3 Extract strings with location, usage context, and cross-references
    - [ ] 6.2.4 Add assembly code formatting optimized for LLM consumption
    - [ ] 6.2.5 Maintain assembly-to-address mapping for debugging and reference

- [ ] 7.0 Testing Framework Updates (Low-Medium Priority)
  - [ ] 7.1 Unit Test Updates
    - [ ] 7.1.1 Remove analysis processor test files (security, function, string analyzers)
    - [ ] 7.1.2 Create LLM provider unit tests with mocked API responses for all providers
    - [ ] 7.1.3 Test decompilation engine with simplified workflow and mocked LLM calls
    - [ ] 7.1.4 Update data model tests for new decompilation-focused structures
    - [ ] 7.1.5 Add LLM provider factory and selection logic tests
  - [ ] 7.2 Integration Test Revision
    - [ ] 7.2.1 Update `tests/integration/test_analysis_engine.py` for decompilation focus
    - [ ] 7.2.2 Add LLM provider integration tests with real API calls (require API keys)
    - [ ] 7.2.3 Test complete decompilation + translation workflow end-to-end
    - [ ] 7.2.4 Add tests for different binary formats with multiple LLM providers
    - [ ] 7.2.5 Remove security scanner and complex analysis test expectations
  - [ ] 7.3 Mock LLM Response Framework
    - [ ] 7.3.1 Create realistic mock responses for each LLM provider with varied styles
    - [ ] 7.3.2 Add test fixtures for assembly code translation examples
    - [ ] 7.3.3 Create test data for different binary types and complexity levels
    - [ ] 7.3.4 Add performance testing framework for LLM response times
    - [ ] 7.3.5 Test error handling for LLM API failures, rate limits, and timeouts

- [ ] 8.0 Documentation & Final Cleanup (Low Priority)
  - [ ] 8.1 Code Documentation Updates
    - [ ] 8.1.1 Update README.md to reflect new decompilation + translation architecture
    - [ ] 8.1.2 Create LLM provider setup and configuration guide with API key instructions
    - [ ] 8.1.3 Add comprehensive API usage examples with different LLM providers
    - [ ] 8.1.4 Document translation quality expectations and prompt tuning guidance  
    - [ ] 8.1.5 Update Docker deployment instructions for new dependencies
  - [ ] 8.2 Final Cleanup and Validation
    - [ ] 8.2.1 Remove all unused files, directories, and legacy analysis components
    - [ ] 8.2.2 Update import statements throughout codebase for new structure
    - [ ] 8.2.3 Run comprehensive linting (black, isort) and type checking (mypy)
    - [ ] 8.2.4 Update CLAUDE.md with new architecture status and current work
    - [ ] 8.2.5 Verify all tests pass with new simplified structure

- [ ] 9.0 End-to-End Validation & Integration (Critical Priority)
  - [ ] 9.1 Complete Workflow Validation
    - [ ] 9.1.1 Test with real binary files using all three LLM providers (OpenAI, Anthropic, Gemini)
    - [ ] 9.1.2 Validate translation quality, accuracy, and consistency across providers
    - [ ] 9.1.3 Verify API response structure matches updated documentation
    - [ ] 9.1.4 Test comprehensive error handling for each LLM provider failure mode
    - [ ] 9.1.5 Validate performance meets updated Project PRD requirements
  - [ ] 9.2 Production Readiness Testing
    - [ ] 9.2.1 Run complete test suite with new decompilation-focused architecture
    - [ ] 9.2.2 Verify Docker deployment works end-to-end with LLM provider integration
    - [ ] 9.2.3 Test with sample external analysis tools consuming structured output
    - [ ] 9.2.4 Validate Redis cache behavior with new decompilation data structures
    - [ ] 9.2.5 Final integration commit with updated task completion status and documentation

### Implementation Notes

- **Execution Strategy:** Critical path is Documents (1.0) → Cleanup (2.0) → LLM Framework (3.0) → API Updates (5.0) → Final Validation (9.0)
- **Parallel Execution:** Phase 4.0 (Dependencies) can run parallel with Phase 3.0 (LLM Framework)
- **Testing Approach:** Mock LLM responses for unit tests, real API integration for validation
- **Rollback Strategy:** Each phase committed separately to enable selective rollback if needed
- **Time Estimate:** 52-73 hours total, spread across phases with critical path prioritization