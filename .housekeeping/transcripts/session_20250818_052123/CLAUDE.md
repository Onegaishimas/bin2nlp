# Project: bin2nlpccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccx

## Current Status
- **Phase:** Context cleared and preserved
- **Last Session:** 2025-08-18 00:11 - Intelligent context clear (Session 20250818_001126)
- **Next Steps:** ** Task 3.5 Create string extraction and categorization processor (4 sub-tasks)
- **Active Document:** Resume from @.housekeeping/resume_20250818_001126.md
- **Context Health:** Cleared and archived

## Housekeeping Status
- **Last Checkpoint:** 2025-08-18T00:11:26.488039 - Session 20250818_001126
- **Last Transcript Save:** @.housekeeping/transcript_20250818_001126.md
- **Context Health:** Cleared and ready for fresh start
- **Quick Resume:** @.housekeeping/QUICK_RESUME.md

## Quick Resume Commands
```bash
# Standard session start sequence
/compact
@CLAUDE.md
ls -la */

# Load project context (after Project PRD exists)
@prds/000_PPRD|[project-name].md
@adrs/000_PADR|[project-name].md

# Load current work area based on phase
@prds/      # For PRD work
@tdds/      # For TDD work  
@tids/      # For TID work
@tasks/     # For task execution
```

## Housekeeping Commands
```bash
# 🧠 INTELLIGENT CONTEXT CLEAR & RESUME (RECOMMENDED)
./scripts/clear_resume
# Auto-detects current work, captures context, provides instant resume commands
# Use this before /clear in Claude Code!

# Quick housekeeping (preserves context, creates transcript)
./scripts/hk

# Specific housekeeping scenarios  
./scripts/hk --summary "Completed logging system" --next-steps "Begin testing phase"
./scripts/hk --summary "Taking a break" --notes "Work in progress on API endpoints"

# Resume from last session
@.housekeeping/QUICK_RESUME.md        # Instant resume (latest)
@.housekeeping/resume_session_*.md    # Specific session
@RESUME_COMMANDS.txt                  # Copy-paste commands

# Load aliases for shortcuts
source scripts/aliases.sh
hk-quick    # Quick checkpoint
hk-task     # Task completion  
hk-break    # Break/interruption
```

## Context Management Workflow
```bash
# 1. When context gets low:
./scripts/clear_resume                # Captures everything automatically
# Copy the displayed resume commands

# 2. Use /clear in Claude Code
/clear

# 3. Paste the resume commands:
@CLAUDE.md
@tasks/001_FTASKS|Phase1_Integrated_System.md
@adrs/000_PADR|bin2nlp.md
@.housekeeping/QUICK_RESUME.md
/compact
# ✅ Full context restored!
```

## Project Standards

## Technology Stack
- **Frontend:** N/A (API-only service)
- **Backend:** FastAPI with Uvicorn ASGI server, Python 3.11+
- **Database:** Redis (cache-only, no persistent storage)
- **Testing:** Balanced pyramid (pytest, unit tests + integration tests + smoke tests)
- **Deployment:** Multi-container Docker setup (API + workers + Redis)

## Development Standards

### Code Organization
- Modular monolith structure: `src/{api,analysis,llm,models,cache,core}/`
- File naming: `snake_case.py`, Classes: `PascalCase`, Functions: `snake_case`
- Import order: standard library → third-party → local application
- Test files mirror src structure: `tests/{unit,integration,performance}/`

### Coding Patterns
- API endpoints use Pydantic models for request/response validation
- Async/await for all I/O operations (file processing, Redis, LLM calls)
- Background tasks for long-running analysis operations
- Consistent error handling with custom exception hierarchy
- Structured logging with contextual information

### Quality Requirements
- 85% minimum unit test coverage for core business logic
- Type hints required for all function signatures
- Docstrings required for all public functions and classes
- All changes via feature branches with code review
- Pre-commit hooks for code formatting (black, isort, mypy)

## Architecture Principles
- API-first design with automatic OpenAPI documentation
- Stateless operations enabling horizontal scaling
- Fail-fast input validation with clear error messages
- Separation of concerns: API, analysis engine, LLM integration
- Security-first: sandboxed execution, no persistent binary storage

## Implementation Notes
- Use FastAPI dependency injection for Redis, config, and services
- radare2 integration via r2pipe in isolated containers
- Ollama LLM integration with async HTTP client and retry logic
- Result caching with configurable TTL (1-24 hours)
- Container resource limits: API (512MB), Workers (2GB), Redis (256MB)

## AI Dev Tasks Framework Workflow

### Document Creation Sequence
1. **Project Foundation**
   - `000_PPRD|[project-name].md` → `/prds/` (Project PRD)
   - `000_PADR|[project-name].md` → `/adrs/` (Architecture Decision Record)
   - Update this CLAUDE.md with Project Standards from ADR

2. **Feature Development** (repeat for each feature)
   - `[###]_FPRD|[feature-name].md` → `/prds/` (Feature PRD)
   - `[###]_FTDD|[feature-name].md` → `/tdds/` (Technical Design Doc)
   - `[###]_FTID|[feature-name].md` → `/tids/` (Technical Implementation Doc)
   - `[###]_FTASKS|[feature-name].md` → `/tasks/` (Task List)

### Instruction Documents Reference
- `@instruct/001_create-project-prd.md` - Creates project vision and feature breakdown
- `@instruct/002_create-adr.md` - Establishes tech stack and standards
- `@instruct/003_create-feature-prd.md` - Details individual feature requirements
- `@instruct/004_create-tdd.md` - Creates technical architecture and design
- `@instruct/005_create-tid.md` - Provides implementation guidance and coding hints
- `@instruct/006_generate-tasks.md` - Generates actionable development tasks
- `@instruct/007_process-task-list.md` - Guides task execution and progress tracking

## Document Inventory

### Project Level Documents
- ✅ 000_PPRD|bin2nlp.md (Project PRD)
- ✅ 000_PADR|bin2nlp.md (Architecture Decision Record)

### Feature Documents

**Phase 1 Integrated System (Binary Analysis Engine + API Interface):**
- ✅ 001_FPRD|Multi-Platform_Binary_Analysis_Engine.md (Feature PRD)
- ✅ 002_FPRD|RESTful_API_Interface.md (Feature PRD)
- ✅ 001_FTDD|Phase1_Integrated_System.md (Technical Design Doc)
- ✅ 001_FTID|Phase1_Integrated_System.md (Technical Implementation Doc)
- ❌ 001_FTASKS|Phase1_Integrated_System.md (Task List)

### Status Indicators
- ✅ **Complete:** Document finished and reviewed
- ⏳ **In Progress:** Currently being worked on
- ❌ **Pending:** Not yet started
- 🔄 **Needs Update:** Requires revision based on changes

## Task Execution Standards

### Completion Protocol
- ✅ One sub-task at a time, ask permission before next
- ✅ Mark sub-tasks complete immediately: `[ ]` → `[x]`
- ✅ When parent task complete: Run tests → Stage → Clean → Commit → Mark parent complete
- ✅ Never commit without passing tests
- ✅ Always clean up temporary files before commit

### Commit Message Format
```bash
git commit -m "feat: [brief description]" -m "- [key change 1]" -m "- [key change 2]" -m "Related to [Task#] in [PRD]"
```

### Test Commands
- **Unit Tests:** `pytest tests/unit/ -v`
- **Integration Tests:** `pytest tests/integration/ -v --slow`
- **Full Test Suite:** `pytest tests/ -v --cov=src --cov-report=html`
- **Performance Tests:** `pytest tests/performance/ -v`

## Code Quality Checklist

### Before Any Commit
- [ ] All tests passing
- [ ] No console.log/print debugging statements
- [ ] No commented-out code blocks
- [ ] No temporary files (*.tmp, .cache, etc.)
- [ ] Code follows project naming conventions
- [ ] Functions/methods have docstrings if required
- [ ] Error handling implemented per ADR standards

### File Organization Rules
- Follow modular monolith structure: `src/{api,analysis,llm,models,cache,core}/`
- Test files mirror src structure: `tests/{unit,integration,performance}/`
- Use snake_case for Python modules and functions
- Import statements organized: standard library → third-party → local application

## Context Management

### Session End Protocol
```bash
# 1. Update CLAUDE.md status section
# 2. Create session summary
/compact "Completed [specific accomplishments]. Next: [specific next action]."
# 3. Commit progress
git add .
git commit -m "docs: completed [task] - Next: [specific action]"
```

### Context Recovery (If Lost)
```bash
# Mild context loss
@CLAUDE.md
ls -la */
@instruct/[current-phase].md

# Severe context loss  
@CLAUDE.md
@prds/000_PPRD|[project-name].md
@adrs/000_PADR|[project-name].md
ls -la */
@instruct/
```

## Progress Tracking

### Task List Maintenance
- Update task list file after each sub-task completion
- Add newly discovered tasks as they emerge
- Update "Relevant Files" section with any new files created/modified
- Include one-line description for each file's purpose

### Status Indicators for Tasks
- `[ ]` = Not started
- `[x]` = Completed
- `[~]` = In progress (use sparingly, only for current sub-task)
- `[?]` = Blocked/needs clarification

### Session Documentation
After each development session, update:
- Current task position in this CLAUDE.md
- Any blockers or questions encountered
- Next session starting point
- Files modified in this session

## Implementation Patterns

### Error Handling
- Use custom exception hierarchy: `BinaryAnalysisException` base class
- Async exception handling with proper context propagation
- Log errors with structured logging (contextual information)
- API error responses follow consistent JSON format
- User-facing error messages should be friendly and actionable

### Testing Patterns
- Each module gets corresponding test file: `test_[module_name].py`
- Test naming: `test_[function_name]_[scenario]` for pytest
- Mock external dependencies (radare2, Ollama, Redis)
- Test both happy path and error cases
- Aim for 85% coverage minimum for core business logic

## Debugging Protocols

### When Tests Fail
1. Read error message carefully
2. Check recent changes for obvious issues
3. Run individual test to isolate problem
4. Use debugger/console to trace execution
5. Check dependencies and imports
6. Ask for help if stuck > 30 minutes

### When Task is Unclear
1. Review original PRD requirements
2. Check TDD for design intent
3. Look at TID for implementation hints
4. Ask clarifying questions before proceeding
5. Update task description for future clarity

## Feature Priority Order
*[From Project PRD - Core Features]*

**Phase 1 Priority (Weeks 1-2):**
1. Multi-Platform Binary Analysis Engine (Core/MVP)
2. RESTful API Interface (Core/MVP)
3. Basic radare2 integration (Core/MVP)

**Phase 2 Priority (Weeks 3-4):**
4. LLM-Powered Natural Language Translation (Essential)
5. Security-Focused Insight Generation (Essential)
6. Configurable Analysis Depth (Essential)





















## Last Housekeeping
- **Session ID**: session_20250818_051505
- **Timestamp**: 2025-08-18T05:15:05.481700+00:00
- **Snapshot**: `.housekeeping/snapshots/session_20250818_051505.json`
- **Transcript Archive**: `.housekeeping/transcripts/session_20250818_051505/`
- **Resume Script**: `.housekeeping/resume_session_20250818_051505.md`

### Quick Resume
```bash
# Essential context recovery
@CLAUDE.md
@tasks/001_FTASKS|Phase1_Integrated_System.md
@.housekeeping/resume_session_20250818_051505.md
```

## Session History Log

### Session 1: 2025-08-14 - Project Foundation Setup
- **Accomplished:** Created project structure, initial CLAUDE.md, completed Project PRD
- **Next:** Create Architecture Decision Record using @instruct/002_create-adr.md
- **Files Created:** CLAUDE.md, folder structure (prds/, adrs/, tdds/, tids/, tasks/, docs/, instruct/), 000_PPRD|bin2nlp.md
- **Duration:** ~1 hour

### Session 2: 2025-08-15 - Architecture Decision Record Creation
- **Accomplished:** Created comprehensive ADR with tech stack decisions, updated CLAUDE.md with Project Standards
- **Technology Stack:** FastAPI, modular monolith, Redis cache, multi-container Docker, balanced testing
- **Next:** Begin feature development with first Feature PRD for Multi-Platform Binary Analysis Engine
- **Files Created:** 000_PADR|bin2nlp.md, updated CLAUDE.md with standards
- **Duration:** ~45 minutes

### Session 3: 2025-08-16 - Cache Layer Implementation & Testing
- **Accomplished:** Complete Task 2.0 Cache Layer Implementation with comprehensive unit tests
- **Components Built:** Redis client, job queue, result cache, rate limiter, session manager
- **Testing:** 4 comprehensive test suites with mocked Redis, time-based scenarios, error handling
- **Technical Features:** Priority queuing, sliding window rate limiting, TTL management, session tracking
- **Files Created:** src/cache/*.py (5 files), tests/unit/cache/*.py (4 test files), updated requirements.txt
- **Next:** Task 2.7 Integration Tests with Real Redis, or proceed to Task 3.0 Binary Analysis Engine
- **Duration:** ~2 hours

## Quick Reference

### Folder Structure
```
project-root/
├── CLAUDE.md                    # This file
├── adrs/                        # Architecture Decision Records
├── docs/                        # Additional documentation
├── instruct/                    # Framework instruction files
├── prds/                        # Product Requirements Documents
├── tasks/                       # Task Lists
├── tdds/                        # Technical Design Documents
└── tids/                        # Technical Implementation Documents
```

### File Naming Convention
- **Project Level:** `000_PPRD|ProjectName.md`, `000_PADR|ProjectName.md`
- **Feature Level:** `001_FPRD|FeatureName.md`, `001_FTDD|FeatureName.md`, etc.
- **Sequential:** Use 001, 002, 003... for features in priority order

### Emergency Contacts & Resources
- **Framework Documentation:** @instruct/000_README.md
- **Current Project PRD:** @prds/000_PPRD|[project-name].md (after creation)
- **Tech Standards:** @adrs/000_PADR|[project-name].md (after creation)

---

**Framework Version:** 1.0  
**Last Updated:** [Current Date]  
**Project Started:** [Start Date]