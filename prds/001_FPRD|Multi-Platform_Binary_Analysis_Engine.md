# Feature PRD: Multi-Platform Binary Analysis Engine

## Feature Overview

### Feature Name and Description
**Multi-Platform Binary Analysis Engine (BAE)** - A comprehensive binary analysis engine that provides cross-platform support for analyzing executable files, libraries, and mobile applications using radare2 as the core reverse engineering tool. This engine serves as the foundational component for all analysis capabilities in the bin2nlp system.

### Problem Statement
Current binary analysis tools require specialized expertise and manual operation, creating barriers for developers and security professionals who need to understand binary functionality. The lack of a standardized, automated analysis engine prevents efficient integration into development workflows and limits accessibility for non-expert users.

### Feature Goals and User Value Proposition
- **Automated Analysis**: Transform manual binary reverse engineering into automated, repeatable processes
- **Cross-Platform Support**: Handle Windows, Linux, macOS, and mobile binary formats consistently
- **Structured Output**: Provide machine-readable analysis results suitable for further processing
- **Error Resilience**: Robust handling of corrupted, packed, or unusual binary files
- **Performance Optimization**: Efficient analysis suitable for integration into development workflows

### Connection to Overall Project Objectives
This engine directly supports the primary project goal of democratizing binary analysis by providing the core technical foundation that enables:
- Automated reverse engineering workflows (Primary Goal #1)
- 90% time reduction vs manual analysis (Primary Goal #2) 
- High-quality analysis insights (Primary Goal #3)
- Scalable architecture for future SaaS deployment (Primary Goal #4)

## User Stories & Scenarios

### Primary User Stories

**Story 1: Legacy System Developer**
```
As a developer inheriting undocumented legacy systems,
I want to automatically analyze binary files to understand their functionality,
So that I can make informed decisions about modification and integration.

Acceptance Criteria:
- Binary file is processed and analyzed within time limits
- Function-level breakdown with entry points identified
- Import/export analysis showing external dependencies
- Basic security assessment highlighting potential risks
- Clear error messages for unsupported or corrupted files
```

**Story 2: Security Analyst**
```
As a security professional conducting software audits,
I want to scan binary files for suspicious behaviors and security risks,
So that I can assess compliance and identify potential threats.

Acceptance Criteria:
- Network communication patterns identified and categorized
- File system operations (read/write/execute) catalogued
- Registry modifications and system calls documented
- Suspicious patterns flagged with risk levels
- Comprehensive security report generated
```

### Secondary User Scenarios

**Story 3: Development Team Integration**
```
As a development team evaluating third-party dependencies,
I want to batch-analyze multiple binary files efficiently,
So that I can make informed decisions about library adoption.

Acceptance Criteria:
- Multiple file formats processed in single analysis session
- Comparative analysis results highlighting differences
- Performance metrics for analysis speed and accuracy
- Export capabilities for integration with existing tools
```

### Edge Cases and Error Scenarios

**Edge Case 1: Corrupted Binary Files**
- **Scenario**: User uploads partially corrupted or truncated binary file
- **Expected Behavior**: Early detection and rejection with clear error message
- **Recovery**: Suggest file validation and re-upload with intact binary

**Edge Case 2: Packed/Obfuscated Binaries**
- **Scenario**: User submits packed or heavily obfuscated executable
- **Expected Behavior**: Best-effort analysis with identification of packing method
- **Recovery**: Document limitations and suggest unpacking tools when possible

**Edge Case 3: Unsupported File Formats**
- **Scenario**: User attempts to analyze file format not yet supported
- **Expected Behavior**: Clear rejection with list of supported formats
- **Recovery**: Provide roadmap for format support and suggest alternatives

### User Journey Flows

**Flow 1: Standard Analysis Workflow**
1. Binary file submitted to analysis engine
2. File format validation and type detection
3. radare2 analysis initialization and execution
4. Structured data extraction and processing
5. Security pattern detection and risk assessment
6. Analysis results compilation and return

**Flow 2: Error Handling Workflow**
1. Binary file validation fails initial checks
2. Error categorization (format, corruption, size, etc.)
3. Detailed error message generation with suggested remediation
4. Analysis attempt termination with resource cleanup
5. Error logging for system monitoring and improvement

## Functional Requirements

### Core Analysis Capabilities

1. **File Format Detection and Validation**
   - Automatically detect binary file types (Windows PE, Linux ELF, macOS Mach-O, mobile formats)
   - Validate file integrity and structure before processing
   - Support file size limits up to 100MB as specified in Project PRD
   - Reject unsupported formats with clear error messages

2. **Cross-Platform Binary Processing**
   - Process Windows executables (.exe) and dynamic libraries (.dll)
   - Analyze Linux executables (.elf) and shared objects (.so)
   - Handle macOS applications (.app) and dynamic libraries (.dylib)
   - Basic support for mobile application formats (APK, IPA)

3. **radare2 Integration and Analysis**
   - Initialize radare2 analysis sessions using r2pipe Python library
   - Execute comprehensive analysis including function detection, string extraction, and import/export identification
   - Handle radare2 errors and timeouts gracefully
   - Extract structured data from radare2 analysis results

4. **Function-Level Analysis**
   - Identify all functions within the binary with entry points and size information
   - Extract function signatures and calling conventions where possible
   - Detect function relationships and call graphs
   - Identify imported and exported functions with library dependencies

5. **String and Data Extraction**
   - Extract readable strings with context and location information
   - Identify embedded URLs, file paths, and configuration data
   - Detect hardcoded credentials or sensitive information patterns
   - Categorize strings by type and potential significance

6. **Security Pattern Detection**
   - Identify network communication patterns (socket creation, HTTP requests, etc.)
   - Detect file system operations (file creation, modification, deletion)
   - Catalog registry access and system configuration changes (Windows)
   - Flag potentially suspicious behaviors (code injection, process manipulation)

7. **Comprehensive Error Handling**
   - Validate file format and structure before analysis
   - Implement timeout mechanisms for long-running analysis operations
   - Provide detailed error messages with recommended remediation steps
   - Log errors for monitoring and analysis improvement

8. **Analysis Result Structuring**
   - Generate machine-readable analysis results in JSON format
   - Include metadata about analysis process (time, radare2 version, engine version)
   - Provide confidence scores for various analysis components
   - Structure results for easy consumption by LLM translation layer

### Input and Output Specifications

**Input Requirements:**
- Binary file path or file object
- Analysis configuration parameters (depth, timeout, specific focus areas)
- Optional metadata (source, intended platform, known file type)

**Output Structure:**
```json
{
  "analysis_id": "unique_identifier",
  "metadata": {
    "file_info": { "name", "size", "format", "platform" },
    "analysis_info": { "timestamp", "duration", "engine_version", "radare2_version" },
    "configuration": { "analysis_depth", "timeout_used", "focus_areas" }
  },
  "file_analysis": {
    "format_detection": { "detected_format", "confidence", "validation_results" },
    "basic_info": { "architecture", "entry_point", "sections", "segments" },
    "functions": [ { "name", "address", "size", "type", "calls_to", "calls_from" } ],
    "strings": [ { "content", "address", "type", "context" } ],
    "imports": [ { "library", "function", "address", "type" } ],
    "exports": [ { "function", "address", "ordinal" } ]
  },
  "security_analysis": {
    "risk_score": "numeric_assessment",
    "network_behavior": [ "detected_patterns" ],
    "file_operations": [ "operations_detected" ],
    "system_calls": [ "system_interactions" ],
    "suspicious_patterns": [ "flagged_behaviors" ]
  },
  "errors": [ "any_errors_or_warnings" ],
  "success": "boolean_status"
}
```

### Business Logic and Validation Rules

**File Validation Rules:**
- Maximum file size: 100MB (enforced before processing)
- Supported formats: PE, ELF, Mach-O, basic mobile formats
- File integrity checks using header validation
- Rejection of obviously malformed or truncated files

**Analysis Processing Rules:**
- Maximum analysis time: 20 minutes for largest files (with configurable timeouts)
- Minimum confidence threshold for function detection: 70%
- String extraction limited to readable ASCII/Unicode content > 4 characters
- Security pattern detection using predefined rule sets

**Result Quality Rules:**
- All analysis results must include confidence scores
- Partial results acceptable if core analysis succeeds
- Error conditions must be clearly documented in results
- Analysis metadata required for all successful operations

### Integration Requirements

**Internal Integration:**
- Clean interface for LLM translation layer consumption
- Cache-compatible output format for Redis storage
- Event hooks for analysis progress monitoring
- Logging integration for debugging and performance monitoring

**External Integration:**
- radare2 dependency management and version compatibility
- File system integration for temporary file handling
- Resource monitoring for memory and CPU usage tracking
- Container environment compatibility for Docker deployment

## User Experience Requirements

### Performance and Feedback

**Analysis Progress Indication:**
- Clear logging of analysis phases for debugging
- Progress hooks for long-running operations
- Timeout warnings before analysis termination
- Resource usage monitoring and reporting

**Error Communication:**
- Human-readable error messages with specific remediation suggestions
- Error categorization (user error vs. system error vs. file issue)
- Recovery suggestions for common error scenarios
- Contact information for unsupported file types

### Development Integration

**API Compatibility:**
- Synchronous analysis method for small files (< 10MB)
- Asynchronous analysis support for larger files with progress callbacks
- Batch analysis capabilities for multiple files
- Configuration options for analysis depth and focus areas

**Debugging and Development:**
- Verbose logging modes for development and troubleshooting
- Analysis result validation and schema checking
- Test mode with sample binary files for development
- Performance profiling hooks for optimization

## Data Requirements

### Data Models and Relationships

**BinaryFile Model:**
```python
@dataclass
class BinaryFile:
    file_path: str
    file_size: int
    file_hash: str
    detected_format: BinaryFormat
    platform: Platform
    architecture: Architecture
```

**AnalysisConfig Model:**
```python
@dataclass
class AnalysisConfig:
    analysis_depth: AnalysisDepth  # QUICK, STANDARD, COMPREHENSIVE
    timeout_seconds: int
    focus_areas: List[AnalysisFocus]  # SECURITY, FUNCTIONS, STRINGS, etc.
    enable_security_scan: bool
    max_functions: Optional[int]
```

**AnalysisResult Model:**
```python
@dataclass
class AnalysisResult:
    analysis_id: str
    metadata: AnalysisMetadata
    file_analysis: FileAnalysis
    security_analysis: SecurityAnalysis
    errors: List[AnalysisError]
    success: bool
    confidence_score: float
```

### Data Validation and Constraints

**File Constraints:**
- File size: 1KB minimum, 100MB maximum
- Supported formats: Validated against known binary headers
- File integrity: Basic corruption detection via header/footer validation

**Analysis Constraints:**
- Function count: Maximum 10,000 functions per binary to prevent memory issues
- String extraction: Maximum 50,000 strings with length limits
- Analysis timeout: Configurable with maximum 20-minute limit
- Memory usage: Maximum 2GB per analysis operation

### Data Persistence and Retrieval

**Temporary Storage:**
- Analysis results cached in Redis with configurable TTL (1-24 hours)
- Temporary file handling with automatic cleanup
- Progress state storage for long-running analysis operations

**No Persistent Storage:**
- Binary files deleted immediately after analysis (security requirement)
- No long-term storage of analysis results (privacy requirement)
- Audit logs only contain metadata, no file content

## Technical Constraints

### Architecture Decision Record Compliance

**Technology Stack Requirements:**
- Implementation in Python 3.11+ following FastAPI project standards
- radare2 integration via r2pipe Python library as specified in ADR
- Async/await patterns for I/O operations per development standards
- Container compatibility for Docker multi-container deployment

**Code Organization Standards:**
- Located in `src/analysis/` module following modular monolith structure
- Follows snake_case naming conventions and type hint requirements
- Implements custom exception hierarchy based on `BinaryAnalysisException`
- Includes comprehensive unit and integration tests

**Performance Requirements:**
- Resource limits: Maximum 2GB RAM, 2 CPU cores per analysis worker
- Processing targets: Small files (≤10MB) in 30 seconds, medium files (≤30MB) in 5 minutes
- Concurrent processing: Support multiple simultaneous analysis operations
- Memory efficiency: Streaming file processing for large binaries

### Security and Safety Requirements

**Sandboxed Execution:**
- All binary analysis runs in isolated container environment
- No network access for analysis containers
- File system access limited to analysis workspace
- Resource limits prevent denial-of-service attacks

**Input Validation:**
- Comprehensive file format validation before radare2 processing
- Size limits enforced at engine level
- Malicious file detection and safe handling
- Input sanitization for all configuration parameters

## API/Integration Specifications

### Internal API Design

**Primary Analysis Interface:**
```python
class BinaryAnalysisEngine:
    async def analyze_binary(
        self, 
        file_path: str, 
        config: AnalysisConfig
    ) -> AnalysisResult:
        """Perform comprehensive binary analysis."""
        
    async def validate_binary(
        self, 
        file_path: str
    ) -> ValidationResult:
        """Validate binary file before analysis."""
        
    def get_supported_formats(self) -> List[BinaryFormat]:
        """Return list of supported binary formats."""
```

**Analysis Configuration Interface:**
```python
class AnalysisConfigBuilder:
    def set_depth(self, depth: AnalysisDepth) -> 'AnalysisConfigBuilder'
    def set_timeout(self, seconds: int) -> 'AnalysisConfigBuilder'
    def add_focus_area(self, area: AnalysisFocus) -> 'AnalysisConfigBuilder'
    def enable_security_scan(self, enabled: bool = True) -> 'AnalysisConfigBuilder'
    def build(self) -> AnalysisConfig
```

### External Integration Requirements

**radare2 Integration:**
- r2pipe library for Python integration
- Error handling for radare2 crashes or timeouts
- Version compatibility checking (minimum r2 version requirements)
- Command validation and injection prevention

**Container Integration:**
- Docker container with radare2 pre-installed
- Volume mounting for temporary file access
- Resource limit enforcement via container constraints
- Health check endpoints for container monitoring

## Non-Functional Requirements

### Performance Expectations

**Processing Performance:**
- Small files (≤10MB): 95% complete within 30 seconds
- Medium files (≤30MB): 90% complete within 5 minutes
- Large files (≤100MB): 85% complete within 20 minutes
- Concurrent processing: Support 4 simultaneous analysis operations

**Resource Efficiency:**
- Memory usage: Maximum 2GB per analysis operation
- CPU utilization: Efficient use of allocated CPU cores
- I/O optimization: Streaming file processing where possible
- Cleanup: Automatic resource cleanup after analysis completion

### Scalability Requirements

**Horizontal Scaling:**
- Stateless design enabling multiple engine instances
- Shared-nothing architecture for parallel processing
- Resource isolation between concurrent analysis operations
- Container-based deployment for elastic scaling

**Vertical Scaling:**
- Efficient memory usage with large binary files
- CPU optimization for analysis-intensive operations
- I/O optimization for file processing
- Configurable resource limits per analysis

### Reliability and Availability

**Error Recovery:**
- Graceful handling of radare2 crashes or errors
- Timeout mechanisms for hung analysis operations
- Partial result recovery when possible
- Comprehensive error logging and monitoring

**System Stability:**
- Memory leak prevention in long-running operations
- Resource limit enforcement to prevent system overload
- Proper cleanup of temporary files and resources
- Container restart capability for recovery

## Feature Boundaries (Non-Goals)

### Explicit Exclusions

**Advanced Unpacking:**
- Automatic unpacking of compressed or encrypted binaries
- Dynamic analysis or runtime behavior monitoring
- Emulation-based analysis techniques
- Advanced anti-analysis bypass capabilities

**Malware Classification:**
- Specific malware family identification
- Threat intelligence integration
- Signature-based detection systems
- Behavioral analysis beyond basic pattern detection

**Interactive Analysis:**
- Manual analysis workflow support
- Interactive debugging capabilities
- Real-time analysis modification
- User-guided analysis path selection

### Future Enhancements (Out of Scope)

**Advanced Analysis Techniques:**
- Control flow graph generation and analysis
- Data flow analysis and tracking
- Advanced decompilation capabilities
- Symbolic execution or formal verification

**Enterprise Features:**
- Analysis result versioning and comparison
- Collaborative analysis workflows
- Advanced reporting and visualization
- Integration with enterprise security tools

### Technical Limitations

**Analysis Depth:**
- Limited to static analysis only (no dynamic execution)
- Basic security pattern detection (not comprehensive threat hunting)
- Standard disassembly without advanced optimization
- English-language output only initially

**Platform Support:**
- Core platforms only (Windows, Linux, macOS, basic mobile)
- Standard binary formats (no proprietary or niche formats)
- Common architectures (x86, x64, ARM basics)

## Dependencies

### External Dependencies

**radare2 Integration:**
- radare2 installed in container environment (latest stable release - floating version)
- r2pipe Python library (latest stable version)
- Compatible radare2 plugins for format support
- Regular updates for security and compatibility

**Python Libraries:**
- r2pipe for radare2 integration
- structlog for logging
- pydantic for data validation
- asyncio for async operations
- pytest for testing framework

### Internal Dependencies

**Core Infrastructure:**
- Container environment with security restrictions
- Temporary file system with automatic cleanup
- Redis cache for result storage (provided by infrastructure)
- Logging and monitoring system integration

**Project Components:**
- Core exception handling framework
- Configuration management system
- File validation utilities
- Security pattern rule definitions

### Data Dependencies

**Binary Format Specifications:**
- PE format specification for Windows binaries
- ELF format specification for Linux binaries
- Mach-O format specification for macOS binaries
- Basic understanding of mobile app packaging formats

**Analysis Rule Sets:**
- Security pattern definitions and rules
- Function signature databases
- String pattern recognition rules
- Suspicious behavior detection criteria

## Success Criteria

### Quantitative Success Metrics

**Performance Benchmarks:**
- 95% of small files (≤10MB) analyzed within 30 seconds
- 90% of medium files (≤30MB) analyzed within 5 minutes
- 85% of large files (≤100MB) analyzed within 20 minutes
- 99% system uptime during analysis operations

**Analysis Quality:**
- 90% accuracy in file format detection
- 85% success rate in function identification for standard binaries
- 80% accuracy in security pattern detection
- 95% successful completion rate for supported file formats

**Resource Efficiency:**
- Average memory usage below 1GB for typical analysis operations
- CPU utilization optimized for concurrent operations
- Zero memory leaks in 24-hour continuous operation testing
- Successful cleanup of temporary resources in 100% of operations

### User Satisfaction Indicators

**Developer Experience:**
- Clear API interface with comprehensive documentation
- Helpful error messages with actionable remediation steps
- Predictable performance within specified time limits
- Easy integration with existing development workflows

**Analysis Usefulness:**
- Generated results provide actionable insights for developers
- Security findings help identify real risks and concerns
- Function analysis assists in understanding binary structure
- String extraction reveals useful configuration and behavior information

### Completion and Acceptance Criteria

**Feature Completeness:**
- All primary user stories implemented with acceptance criteria met
- Comprehensive error handling for all edge cases
- Full test coverage including unit, integration, and performance tests
- Documentation complete including API reference and usage examples

**Integration Readiness:**
- Successfully integrates with FastAPI application framework
- Compatible with Redis caching layer
- Works within Docker container environment
- Ready for LLM translation layer integration

## Testing Requirements

### Unit Testing Expectations

**Core Function Testing:**
- Test all public methods of BinaryAnalysisEngine class
- Mock radare2 integration for isolated unit testing
- Validate error handling for all exception scenarios
- Test configuration validation and parameter handling
- Achieve 90% code coverage for analysis engine code

**Data Model Testing:**
- Validate all data model serialization and deserialization
- Test constraint enforcement and validation rules
- Verify error message generation and formatting
- Test analysis result structure and schema compliance

### Integration Testing Scenarios

**radare2 Integration Testing:**
- Test analysis with sample binaries of each supported format
- Verify timeout handling with long-running analysis operations
- Test error recovery from radare2 crashes or failures
- Validate output parsing and data extraction accuracy

**End-to-End Analysis Testing:**
- Process complete analysis workflow with real binary files
- Test concurrent analysis operations and resource isolation
- Verify temporary file cleanup and resource management
- Test analysis result caching and retrieval

### Performance Testing Requirements

**Load Testing:**
- Concurrent analysis of multiple files with performance monitoring
- Memory usage tracking during large file analysis
- CPU utilization measurement under typical workloads
- Resource cleanup verification after high-load scenarios

**Benchmark Testing:**
- Analysis time measurement for files of various sizes
- Comparison with manual analysis time estimates
- Performance regression testing with version updates
- Resource usage optimization validation

### User Acceptance Testing Criteria

**Functional Acceptance:**
- All primary user stories can be executed successfully
- Error scenarios handled gracefully with helpful feedback
- Analysis results provide useful and actionable information
- Integration with other system components works as expected

**Performance Acceptance:**
- Analysis times meet specified performance targets
- System remains responsive during analysis operations
- Resource usage stays within specified limits
- Concurrent operations do not interfere with each other

## Implementation Considerations

### Complexity Assessment and Risk Factors

**High Complexity Areas:**
- radare2 integration stability and error handling (Risk: Medium-High)
- Large file processing with memory efficiency (Risk: Medium)
- Concurrent analysis operation management (Risk: Medium)
- Security pattern detection accuracy (Risk: Medium)

**Medium Complexity Areas:**
- File format validation and detection (Risk: Low-Medium)
- Analysis result structuring and serialization (Risk: Low)
- Configuration management and validation (Risk: Low)
- Basic error handling and logging (Risk: Low)

### Recommended Implementation Approach

**Phase 1: Core Foundation (Week 1)**
1. File format detection and validation system
2. Basic radare2 integration with simple analysis
3. Core data models and result structures
4. Basic error handling and logging

**Phase 2: Analysis Engine (Week 2)**
1. Comprehensive radare2 analysis integration
2. Function detection and analysis processing
3. String extraction and categorization
4. Analysis result compilation and formatting

**Phase 3: Security and Optimization (Week 3)**
1. Security pattern detection implementation
2. Performance optimization and resource management
3. Concurrent analysis support
4. Comprehensive error handling and edge cases

### Potential Technical Challenges

**radare2 Integration Challenges:**
- Version compatibility and dependency management
- Error handling for unstable or crashing radare2 operations
- Performance optimization for large binary analysis
- Output parsing reliability across different binary types

**Performance Challenges:**
- Memory management for large binary file processing
- CPU optimization for concurrent analysis operations
- I/O efficiency for file processing and temporary storage
- Resource cleanup and garbage collection optimization

**Container Integration Challenges:**
- Security restrictions and sandboxing requirements
- Resource limit enforcement and monitoring
- Inter-container communication for distributed processing
- Container health monitoring and recovery

### Resource and Timeline Estimates

**Development Timeline:**
- Week 1: Core foundation and basic integration (40 hours)
- Week 2: Full analysis engine implementation (40 hours)
- Week 3: Security features and optimization (30 hours)
- Week 4: Testing, documentation, and refinement (20 hours)
- **Total Estimate: 130 hours over 4 weeks**

**Resource Requirements:**
- 1 senior developer for radare2 integration and core engine
- Access to diverse binary file samples for testing
- Development environment with Docker and radare2 setup
- Performance testing infrastructure for benchmarking

**Risk Mitigation Timeline:**
- Week 1: Early radare2 integration testing to identify stability issues
- Week 2: Performance baseline establishment and optimization planning
- Week 3: Concurrent processing testing and resource limit validation
- Week 4: Comprehensive integration testing and edge case validation

## Open Questions

### Technical Decisions Requiring Research

**radare2 Version Management:** ✅ **RESOLVED**
- **Strategy**: Use latest stable radare2 release (floating version)
- **Rationale**: Prioritize latest features and security fixes for prototype phase
- **Update Approach**: Automatic updates with container rebuild and testing
- **Fallback**: Previous stable version as backup container image

**Performance Optimization:**
- Should analysis be parallelized within radare2 or at the engine level?
- What caching strategies would be most effective for repeated analysis?
- How should memory usage be optimized for very large binary files?

### Business Decisions Pending Input

**Analysis Depth Configuration:**
- What specific configuration options should be exposed to users?
- How should analysis depth affect processing time and resource usage?
- What default settings provide the best balance of speed and completeness?

**Error Handling Policies:**
- How aggressive should early file rejection be for edge cases?
- What level of partial results should be returned when analysis fails?
- How should analysis timeouts be communicated and handled?

### Design Decisions Requiring Validation

**Security Pattern Detection:**
- What specific security patterns should be prioritized for detection?
- How should confidence scores be calculated and calibrated?
- What false positive rates are acceptable for different pattern types?

**Output Format Design:**
- How detailed should function analysis results be by default?
- What metadata is most valuable for downstream LLM processing?
- How should analysis results be versioned for compatibility?

---

**Document Status:** ✅ Complete - Ready for Technical Design Document (TDD) creation  
**Next Document:** `001_FTDD|Multi-Platform_Binary_Analysis_Engine.md` using `@instruct/004_create-tdd.md`  
**Related Documents:** `000_PPRD|bin2nlp.md` (Project PRD), `000_PADR|bin2nlp.md` (ADR)  
**Last Updated:** 2025-08-15  
**Document Version:** 1.0