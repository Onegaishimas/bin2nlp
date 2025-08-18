# Claude Code Housekeeping System

This directory contains the automated housekeeping system for managing Claude Code sessions, preserving context, and enabling seamless workflow resumption.

## Quick Usage

### Intelligent Context Clear & Resume (RECOMMENDED)
```bash
# Auto-detect and prepare for /clear
./scripts/clear_resume

# Then use /clear in Claude Code and paste the resume commands
```

### Basic Housekeeping
```bash
# Interactive mode (recommended for first use)
./scripts/housekeep.sh

# Quick checkpoint
./scripts/housekeep.sh --summary "Completed configuration validation" --next-steps "Start logging system implementation"

# With aliases (after sourcing scripts/aliases.sh)
clear-resume # Intelligent context clear & resume
hk-task      # For completed tasks
hk-break     # For breaks/interruptions  
hk-quick     # Quick checkpoint
```

### Resuming Sessions
```bash
# Find and load the most recent resume script
@.housekeeping/resume_session_YYYYMMDD_HHMMSS.md

# Then run the context recovery commands listed in the script
@CLAUDE.md
@tasks/001_FTASKS|Phase1_Integrated_System.md
```

## What Gets Captured

### Session Snapshot (`.json`)
- Complete task progress and status
- Git repository state and changes
- Current phase and active work
- All modified files in session
- Next steps and context notes

### Transcript Archive (`/transcripts/session_*/`)
- Complete copy of all project files
- Comprehensive session report
- File change summary
- Project structure snapshot
- Resumption instructions

### Resume Script (`.md`)
- Context recovery commands
- Session summary and status  
- Immediate next steps
- Modified files list
- Detailed resumption protocol

## Directory Structure
```
.housekeeping/
├── README.md              # This file
├── sessions/               # Session metadata  
├── snapshots/             # JSON snapshots
│   └── session_*.json
├── transcripts/           # Complete archives
│   └── session_*/
│       ├── session_report.md
│       ├── CLAUDE.md
│       ├── tasks/
│       ├── src/
│       └── ...
└── resume_session_*.md    # Resume scripts
```

## Features

### 🔄 **Context Preservation**
- Captures complete project state
- Preserves task progress and status
- Records all file modifications
- Maintains git repository state

### 📚 **Learning Archive**
- Complete transcript of development session
- All source files at point in time
- Detailed progress reports
- Development decision history

### 🚀 **Seamless Resumption**
- Generated resume scripts with exact commands
- Context recovery protocols
- Immediate next steps
- No lost context or momentum

### 🧹 **Automated Cleanup**
- Organizes session data automatically
- Creates timestamped archives
- Maintains project history
- Enables session comparison

## Best Practices

### When to Use Housekeeping
- ✅ **End of coding session** - Preserve progress
- ✅ **Before long breaks** - Ensure resumption
- ✅ **After completing tasks** - Checkpoint progress  
- ✅ **Before complex changes** - Create restore point
- ✅ **Context getting full** - Compact and continue

### Session Summary Guidelines
- Be specific about what was accomplished
- Note any key decisions or breakthroughs
- Include any blockers encountered
- Mention files that were significantly changed

### Next Steps Guidelines
- List immediate actionable tasks
- Include specific file or function names
- Note any dependencies or prerequisites
- Reference task numbers when applicable

## Advanced Usage

### Custom Scripts
The housekeeping system can be extended with custom scripts:

```python
# Example: Add custom validation
from scripts.housekeeping import HousekeepingManager

manager = HousekeepingManager()
snapshot = manager.capture_session_snapshot()
# Add custom processing...
```

### Integration with Tools
- **Git hooks**: Automatic housekeeping on commits
- **IDE integration**: Keyboard shortcuts for housekeeping
- **CI/CD**: Session archiving in pipelines
- **Monitoring**: Track development velocity

## Troubleshooting

### Common Issues
1. **Permission errors**: Ensure scripts are executable (`chmod +x`)
2. **Python not found**: Ensure Python 3 is installed and in PATH
3. **Git errors**: Ensure you're in a git repository
4. **Path issues**: Run from project root directory

### Recovery
If housekeeping data is corrupted:
1. Session snapshots are in `.housekeeping/snapshots/`
2. Resume scripts are in `.housekeeping/resume_*.md`
3. Full transcripts are in `.housekeeping/transcripts/`
4. Manually reconstruct from CLAUDE.md if needed

## Configuration

The system auto-detects most settings, but can be customized:

```bash
# Custom project root
./scripts/housekeep.sh --project-root /path/to/project

# Custom archive location  
export HOUSEKEEPING_DIR=/custom/path
```

---

*This housekeeping system ensures no development context is ever lost and enables seamless collaboration between human and AI across multiple sessions.*