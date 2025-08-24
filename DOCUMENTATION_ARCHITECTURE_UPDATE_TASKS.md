# Documentation Architecture Update Tasks
## Redis → PostgreSQL + File Storage Hybrid System

## 🎯 **Objective**
Update all project documentation in the `0xcc/` directory to accurately reflect the implemented PostgreSQL + File Storage hybrid architecture, removing outdated Redis-centric specifications and replacing them with current system specifications.

## ✅ **CURRENT STATUS**
- ✅ **Technical Implementation**: PostgreSQL + File Storage system 100% operational
- ✅ **Code Architecture**: All Redis dependencies removed and replaced  
- ❌ **Documentation**: Still references original Redis-only architecture
- 🎯 **Goal**: Align documentation with implemented system

## 📊 **UPDATE PRIORITY TASKS**

### 🏆 **CRITICAL PRIORITY (Must Update Immediately)**

#### **Task D01: Update Architecture Decision Record (ADR)**
**File:** `/0xcc/adrs/000_PADR|bin2nlp.md`  
**Priority:** CRITICAL - This is the foundational architecture reference document

**Required Changes:**
- [ ] **D01.1**: Replace "Primary Storage: Redis Only" section (lines 75-96)
  - Replace with "Primary Storage: PostgreSQL + File Storage Hybrid" 
  - Update rationale: ACID transactions, atomic operations, efficient large payloads
  - Remove Redis cache-first design language

- [ ] **D01.2**: Update Module Structure section (lines 68-71)
  - Replace `src/cache/` references with `src/database/` and `src/storage/`
  - Update module descriptions to reflect hybrid architecture

- [ ] **D01.3**: Replace Redis Configuration section (lines 84-96)
  - Remove Redis data patterns, TTL descriptions
  - Add PostgreSQL schema design, stored procedures, atomic operations
  - Add file storage patterns for large payloads

- [ ] **D01.4**: Update Container Architecture section (lines 108-119)
  - Replace `redis-container` with `database-container` (PostgreSQL)
  - Update service descriptions and dependencies

- [ ] **D01.5**: Update Package Dependencies section (lines 386-393)
  - Remove `redis>=5.0.0` dependency
  - Add `asyncpg>=0.28.0` and `databases[postgresql]>=0.7.0`
  - Add file storage dependencies

- [ ] **D01.6**: Update Data Model Architecture section (lines 1269-1482)
  - Remove Redis caching references from model descriptions
  - Add PostgreSQL persistence and file storage patterns
  - Update performance characteristics for hybrid system

#### **Task D02: Update Project PRD Architecture References**
**File:** `/0xcc/prds/000_PPRD|bin2nlp.md`  
**Priority:** CRITICAL - Primary project specification document

**Required Changes:**
- [ ] **D02.1**: Update Dependencies and Assumptions (lines 171-184)
  - Replace "Redis availability and stability" with "PostgreSQL database availability"
  - Update technical dependency list to reflect database requirements
  - Remove cache-specific language from assumptions

- [ ] **D02.2**: Update Analysis Result Caching description (lines 272-276)
  - Replace Redis caching description with hybrid storage approach
  - Update performance expectations for PostgreSQL + file storage
  - Revise caching strategy explanation

- [ ] **D02.3**: Update Infrastructure Costs section (lines 330-335)
  - Remove Redis deployment costs references
  - Add PostgreSQL database infrastructure considerations
  - Update cost modeling for persistent storage vs volatile cache

- [ ] **D02.4**: Update Technical Dependencies (lines 172-178)
  - Replace Redis connectivity requirements
  - Add database connection pooling and persistence requirements
  - Update container runtime environment specifications

### 🔥 **HIGH PRIORITY (Update Soon)**

#### **Task D03: Update Master Task List Architecture Descriptions**
**File:** `/0xcc/tasks/000_MASTER_TASKS|Decompilation_Service.md`  
**Priority:** HIGH - Active task reference document

**Required Changes:**
- [ ] **D03.1**: Rename and update "Cache Layer" section (lines 27-35)
  - Replace "2.0 Cache Layer" with "2.0 Database & Storage Layer"
  - Update status descriptions from "Redis integration" to "PostgreSQL + File Storage"
  - Revise completion status descriptions

- [ ] **D03.2**: Update individual task descriptions (lines 28-34)
  - Replace "Redis Connection Management" with "PostgreSQL Connection Management"
  - Update "Job Queue System" description to reflect PostgreSQL atomic operations
  - Replace "Result Caching" with "Hybrid Storage Management"
  - Update "Rate Limiting" description for PostgreSQL implementation
  - Replace "Session Management" with "Database Session & File Storage"

- [ ] **D03.3**: Update Architecture Status summaries
  - Revise technical achievement descriptions throughout document
  - Update component integration status descriptions
  - Align completion status with actual hybrid implementation

#### **Task D04: Update Phase 1 Task List File References**
**File:** `/0xcc/tasks/001_FTASKS|Phase1_Integrated_System.md`  
**Priority:** HIGH - Detailed implementation reference

**Required Changes:**
- [ ] **D04.1**: Update file path references in "Relevant Files" section (lines 36-40)
  - Replace all `src/cache/` paths with `src/database/` and `src/storage/`
  - Update file descriptions to match new hybrid architecture
  - Remove Redis-specific implementation references

- [ ] **D04.2**: Update component descriptions throughout document
  - Replace Redis backend references with PostgreSQL implementation
  - Update caching terminology to hybrid storage terminology
  - Revise technical implementation descriptions

### 🟡 **MEDIUM PRIORITY (Update When Convenient)**

#### **Task D05: Review and Update Feature PRDs**
**Files:** `/0xcc/prds/001_FPRD|*.md`, `/0xcc/prds/002_FPRD|*.md`  
**Priority:** MEDIUM - Supporting specification documents

**Required Changes:**
- [ ] **D05.1**: Scan Feature PRDs for Redis-specific implementation details
- [ ] **D05.2**: Update any technical implementation sections that assume Redis
- [ ] **D05.3**: Revise performance specifications based on PostgreSQL characteristics
- [ ] **D05.4**: Update deployment complexity discussions

#### **Task D06: Review Technical Design Documents**  
**Files:** `/0xcc/tdds/001_FTDD|*.md`  
**Priority:** MEDIUM - Technical design specifications

**Required Changes:**
- [ ] **D06.1**: Update database design sections that specify Redis data structures
- [ ] **D06.2**: Revise integration patterns for PostgreSQL + file storage
- [ ] **D06.3**: Update technical architecture diagrams and descriptions
- [ ] **D06.4**: Align performance and scalability discussions

#### **Task D07: Update Technical Implementation Documents**
**Files:** `/0xcc/tids/001_FTID|*.md`  
**Priority:** MEDIUM - Implementation guidance documents

**Required Changes:**
- [ ] **D07.1**: Update implementation hints for database operations
- [ ] **D07.2**: Replace Redis code patterns with PostgreSQL patterns
- [ ] **D07.3**: Update file references and import statements
- [ ] **D07.4**: Revise testing patterns for hybrid storage

### 📝 **STANDARDIZED REPLACEMENT PATTERNS**

#### **Language Transformation Guide:**

**Storage Architecture:**
```markdown
# REPLACE:
"Cache-first design with TTL-based expiration"
"In-memory operations for fast result retrieval"
"Redis clustering support for high-availability caching"

# WITH:
"Hybrid PostgreSQL metadata with file-based large payload storage"
"Atomic PostgreSQL operations with file system caching for optimal performance"
"PostgreSQL connection pooling with file storage redundancy"
```

**Data Persistence:**
```markdown
# REPLACE:
"No persistent storage of potentially sensitive binaries"
"Automatic cleanup prevents storage bloat"
"LRU eviction policy for memory management"

# WITH:
"Metadata persistence in PostgreSQL with automatic TTL cleanup"
"Structured data in database with large payloads in secure file storage"
"Database-managed TTL with file system cleanup procedures"
```

**Performance Characteristics:**
```markdown
# REPLACE:
"Sub-millisecond cache access times"
"Memory-based performance optimization"
"Redis pub/sub for real-time updates"

# WITH:
"Atomic database operations with optimized query performance"
"ACID transaction guarantees with efficient large payload handling"
"PostgreSQL triggers and stored procedures for real-time processing"
```

**Dependencies:**
```markdown
# REPLACE:
"`redis>=5.0.0`: Cache and session storage with async support"
"`redis[hiredis]`: High-performance Redis client"

# WITH:
"`asyncpg>=0.28.0`: PostgreSQL async driver for database operations"
"`databases[postgresql]>=0.7.0`: Database abstraction layer with connection pooling"
"`sqlalchemy>=2.0.0`: Database ORM for schema management"
```

**Container Architecture:**
```markdown
# REPLACE:
"├── redis-container/        # Redis cache service"
"└── docker-compose.yml     # Multi-container orchestration"

# WITH:
"├── database-container/     # PostgreSQL database service"  
"├── storage-container/      # File storage management service"
"└── docker-compose.yml     # Multi-container orchestration with database"
```

### 🎯 **EXECUTION APPROACH**

#### **Phase 1: Foundation Documents (Days 1-2)**
1. Complete Task D01 (ADR) - Most critical reference
2. Complete Task D02 (Project PRD) - User-facing specifications
3. Validate changes for consistency and accuracy

#### **Phase 2: Active Task Documents (Days 3-4)**  
1. Complete Task D03 (Master Task List) - Active development reference
2. Complete Task D04 (Phase 1 Task List) - Implementation details
3. Cross-reference updates for internal consistency

#### **Phase 3: Supporting Documents (Days 5-6)**
1. Complete Tasks D05-D07 (Feature PRDs, TDDs, TIDs) - Supporting specifications
2. Final consistency review across all documents
3. Validate all cross-references and eliminate Redis mentions

### ✅ **SUCCESS CRITERIA**

1. **Zero Redis References**: No mentions of Redis architecture in any 0xcc/ documents
2. **Accurate Architecture**: All documents reflect PostgreSQL + File Storage hybrid
3. **Consistent Terminology**: Uniform language across all specification documents
4. **Complete Coverage**: All technical references updated to match implementation
5. **Developer Clarity**: New developers can understand architecture from documentation

### 📊 **PROGRESS TRACKING**

- **Critical Priority**: 0/6 tasks complete (0%)
- **High Priority**: 0/4 tasks complete (0%) 
- **Medium Priority**: 0/3 tasks complete (0%)
- **Overall Progress**: 0/13 tasks complete (0%)

**Next Action**: Begin with Task D01 (ADR Update) - foundational architecture document

---

**Document Created**: 2025-08-24  
**Last Updated**: 2025-08-24  
**Priority**: CRITICAL - Align documentation with implemented system  
**Estimated Completion**: 6 days (assuming 2 tasks per day)