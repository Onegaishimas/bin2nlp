#!/usr/bin/env python3
"""
Claude Code Session Housekeeping System

Provides automated context management, transcript archiving, and seamless
workflow resumption for long-running development sessions.
"""

import os
import sys
import json
import time
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict


@dataclass
class SessionSnapshot:
    """Captures complete session state for resumption."""
    
    # Session metadata
    session_id: str
    timestamp: str
    project_name: str
    current_phase: str
    
    # Work context
    active_task: str
    completed_tasks: List[str]
    pending_tasks: List[str]
    current_files: List[str]
    
    # Development state
    last_commit_hash: Optional[str]
    working_directory: str
    git_status: Dict[str, Any]
    
    # Session context
    context_summary: str
    next_steps: List[str]
    blockers: List[str]
    notes: str
    
    # Files modified in session
    modified_files: List[Dict[str, Any]]
    created_files: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionSnapshot':
        """Create from dictionary."""
        return cls(**data)


class HousekeepingManager:
    """Manages session housekeeping, archiving, and resumption."""
    
    def __init__(self, project_root: Path = None):
        """Initialize housekeeping manager."""
        self.project_root = project_root or Path.cwd()
        self.archive_dir = self.project_root / ".housekeeping"
        self.sessions_dir = self.archive_dir / "sessions"
        self.transcripts_dir = self.archive_dir / "transcripts" 
        self.snapshots_dir = self.archive_dir / "snapshots"
        
        # Create directories
        for dir_path in [self.archive_dir, self.sessions_dir, self.transcripts_dir, self.snapshots_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    def create_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return f"session_{timestamp}"
    
    def capture_git_state(self) -> Dict[str, Any]:
        """Capture current git repository state."""
        try:
            import subprocess
            
            # Get git status
            status_result = subprocess.run(
                ["git", "status", "--porcelain=v1"], 
                capture_output=True, text=True, cwd=self.project_root
            )
            
            # Get last commit
            commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"], 
                capture_output=True, text=True, cwd=self.project_root
            )
            
            # Get current branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"], 
                capture_output=True, text=True, cwd=self.project_root
            )
            
            return {
                "status_output": status_result.stdout,
                "last_commit": commit_result.stdout.strip() if commit_result.returncode == 0 else None,
                "current_branch": branch_result.stdout.strip() if branch_result.returncode == 0 else None,
                "has_uncommitted_changes": bool(status_result.stdout.strip()),
                "status_files": [line.strip() for line in status_result.stdout.strip().split('\n') if line.strip()]
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def read_claude_md(self) -> Dict[str, Any]:
        """Read and parse CLAUDE.md for current status."""
        claude_md_path = self.project_root / "CLAUDE.md"
        
        if not claude_md_path.exists():
            return {"error": "CLAUDE.md not found"}
        
        try:
            content = claude_md_path.read_text(encoding='utf-8')
            
            # Extract key sections using simple parsing
            lines = content.split('\n')
            sections = {}
            current_section = None
            current_content = []
            
            for line in lines:
                if line.startswith('## '):
                    if current_section:
                        sections[current_section] = '\n'.join(current_content)
                    current_section = line[3:].strip()
                    current_content = []
                else:
                    current_content.append(line)
            
            # Add last section
            if current_section:
                sections[current_section] = '\n'.join(current_content)
            
            # Extract current status
            current_status = {}
            if 'Current Status' in sections:
                status_lines = sections['Current Status'].split('\n')
                for line in status_lines:
                    if line.startswith('- **'):
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            key = parts[0].replace('- **', '').replace('**', '').strip()
                            value = parts[1].strip()
                            current_status[key] = value
            
            return {
                "sections": sections,
                "current_status": current_status,
                "full_content": content
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def read_task_file(self) -> Dict[str, Any]:
        """Read current task file and extract progress."""
        tasks_dir = self.project_root / "tasks"
        
        # Find active task file
        task_files = list(tasks_dir.glob("*.md"))
        if not task_files:
            return {"error": "No task files found"}
        
        # Use the most recent or primary task file
        active_task_file = task_files[0]  # Could be smarter about this
        
        try:
            content = active_task_file.read_text(encoding='utf-8')
            
            # Parse tasks (simple checkbox parsing)
            completed_tasks = []
            pending_tasks = []
            
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if '- [x]' in line:
                    completed_tasks.append(line.replace('- [x]', '').strip())
                elif '- [ ]' in line:
                    pending_tasks.append(line.replace('- [ ]', '').strip())
            
            return {
                "task_file": str(active_task_file),
                "content": content,
                "completed_tasks": completed_tasks,
                "pending_tasks": pending_tasks,
                "total_tasks": len(completed_tasks) + len(pending_tasks),
                "completion_rate": len(completed_tasks) / max(1, len(completed_tasks) + len(pending_tasks))
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def capture_session_snapshot(self, context_summary: str = "", next_steps: List[str] = None, 
                                notes: str = "") -> SessionSnapshot:
        """Capture complete session state."""
        session_id = self.create_session_id()
        
        # Read project state
        claude_md_data = self.read_claude_md()
        task_data = self.read_task_file()
        git_state = self.capture_git_state()
        
        # Extract current status
        current_status = claude_md_data.get('current_status', {})
        
        # Get modified files from git
        modified_files = []
        if 'status_files' in git_state:
            for status_line in git_state['status_files']:
                if len(status_line) >= 3:
                    status = status_line[:2]
                    filename = status_line[3:]
                    modified_files.append({
                        'filename': filename,
                        'status': status,
                        'is_new': status.startswith('??'),
                        'is_modified': status.startswith(' M') or status.startswith('M '),
                        'is_staged': status[0] != ' ' and status[0] != '?'
                    })
        
        # Create snapshot
        snapshot = SessionSnapshot(
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            project_name="bin2nlp",
            current_phase=current_status.get('Phase', 'Unknown'),
            active_task=current_status.get('Next Steps', 'Unknown'),
            completed_tasks=task_data.get('completed_tasks', []),
            pending_tasks=task_data.get('pending_tasks', []),
            current_files=[str(f) for f in self.project_root.rglob('*.py') if '/.' not in str(f)],
            last_commit_hash=git_state.get('last_commit'),
            working_directory=str(self.project_root),
            git_status=git_state,
            context_summary=context_summary,
            next_steps=next_steps or [],
            blockers=[],
            notes=notes,
            modified_files=modified_files,
            created_files=[f['filename'] for f in modified_files if f.get('is_new', False)]
        )
        
        return snapshot
    
    def save_session_snapshot(self, snapshot: SessionSnapshot) -> Path:
        """Save session snapshot to disk."""
        snapshot_file = self.snapshots_dir / f"{snapshot.session_id}.json"
        
        with open(snapshot_file, 'w', encoding='utf-8') as f:
            json.dump(snapshot.to_dict(), f, indent=2, ensure_ascii=False)
        
        print(f"✅ Session snapshot saved: {snapshot_file}")
        return snapshot_file
    
    def create_transcript_archive(self, session_id: str) -> Path:
        """Create transcript archive for study purposes."""
        transcript_dir = self.transcripts_dir / session_id
        transcript_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy key project files for reference
        key_files = [
            "CLAUDE.md",
            "tasks/*.md",
            "adrs/*.md", 
            "prds/*.md",
            "src/**/*.py",
            "requirements.txt",
            "pyproject.toml",
            "pytest.ini"
        ]
        
        for pattern in key_files:
            for file_path in self.project_root.glob(pattern):
                if file_path.is_file():
                    relative_path = file_path.relative_to(self.project_root)
                    dest_path = transcript_dir / relative_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, dest_path)
        
        # Create a comprehensive session report
        report_path = transcript_dir / "session_report.md"
        self._create_session_report(report_path, session_id)
        
        print(f"✅ Transcript archive created: {transcript_dir}")
        return transcript_dir
    
    def _create_session_report(self, report_path: Path, session_id: str):
        """Create detailed session report."""
        claude_md_data = self.read_claude_md()
        task_data = self.read_task_file()
        git_state = self.capture_git_state()
        
        report_content = f"""# Session Report: {session_id}

## Session Overview
- **Timestamp**: {datetime.now(timezone.utc).isoformat()}
- **Project**: bin2nlp
- **Working Directory**: {self.project_root}

## Current Status
{claude_md_data.get('sections', {}).get('Current Status', 'Status not available')}

## Task Progress
- **Total Tasks**: {task_data.get('total_tasks', 0)}
- **Completed**: {len(task_data.get('completed_tasks', []))}
- **Pending**: {len(task_data.get('pending_tasks', []))}
- **Completion Rate**: {task_data.get('completion_rate', 0):.1%}

### Recently Completed Tasks
{chr(10).join(f"- {task}" for task in task_data.get('completed_tasks', [])[-10:])}

### Next Pending Tasks
{chr(10).join(f"- {task}" for task in task_data.get('pending_tasks', [])[:10])}

## Git Status
- **Current Branch**: {git_state.get('current_branch', 'Unknown')}
- **Last Commit**: {git_state.get('last_commit', 'Unknown')}
- **Has Uncommitted Changes**: {git_state.get('has_uncommitted_changes', False)}

### Modified Files
{chr(10).join(git_state.get('status_files', []))}

## Project Structure
```
{self._get_project_tree()}
```

## Key Files Modified This Session
{self._get_session_file_changes()}

## Resumption Instructions

### Quick Resume Commands
```bash
# 1. Load project context
@CLAUDE.md
@tasks/001_FTASKS|Phase1_Integrated_System.md

# 2. Check current status
ls -la src/
git status

# 3. Continue with next task
# Check CLAUDE.md "Next Steps" section for specific task
```

### Context Recovery
If context is lost, use these commands:
```bash
@CLAUDE.md                                    # Load project status
@adrs/000_PADR|bin2nlp.md                    # Load architecture decisions
@tasks/001_FTASKS|Phase1_Integrated_System.md # Load task progress
```

## Session Learning Notes
*Space for manual notes about key decisions, breakthroughs, or patterns discovered*

---
*Report generated automatically by housekeeping system*
"""
        
        report_path.write_text(report_content, encoding='utf-8')
    
    def _get_project_tree(self) -> str:
        """Generate project tree structure."""
        try:
            import subprocess
            result = subprocess.run(
                ["tree", "-I", "__pycache__|*.pyc|.git|.env*|node_modules", "-L", "3"],
                capture_output=True, text=True, cwd=self.project_root
            )
            return result.stdout if result.returncode == 0 else "Tree command not available"
        except:
            # Fallback to simple directory listing
            dirs = []
            for path in sorted(self.project_root.rglob("*")):
                if path.is_dir() and not any(skip in str(path) for skip in ['.git', '__pycache__', '.env']):
                    level = len(path.relative_to(self.project_root).parts)
                    if level <= 3:
                        dirs.append("  " * (level - 1) + path.name + "/")
            return "\n".join(dirs[:50])  # Limit output
    
    def _get_session_file_changes(self) -> str:
        """Get summary of files changed in this session."""
        git_state = self.capture_git_state()
        changes = []
        
        for status_line in git_state.get('status_files', []):
            if len(status_line) >= 3:
                status = status_line[:2]
                filename = status_line[3:]
                
                if status.startswith('??'):
                    changes.append(f"- **NEW**: {filename}")
                elif status.startswith('M') or status.startswith(' M'):
                    changes.append(f"- **MODIFIED**: {filename}")
                elif status.startswith('A'):
                    changes.append(f"- **ADDED**: {filename}")
                elif status.startswith('D'):
                    changes.append(f"- **DELETED**: {filename}")
        
        return "\n".join(changes) if changes else "*No file changes detected*"
    
    def perform_housekeeping(self, context_summary: str = "", next_steps: List[str] = None, 
                           notes: str = "") -> Dict[str, Any]:
        """Perform complete housekeeping operation."""
        print("🧹 Starting housekeeping operation...")
        
        try:
            # 1. Capture session snapshot
            snapshot = self.capture_session_snapshot(context_summary, next_steps, notes)
            snapshot_path = self.save_session_snapshot(snapshot)
            
            # 2. Create transcript archive
            transcript_path = self.create_transcript_archive(snapshot.session_id)
            
            # 3. Create resumption script
            resume_script = self.create_resumption_script(snapshot)
            
            # 4. Update CLAUDE.md with housekeeping info
            self.update_claude_md_with_housekeeping(snapshot)
            
            results = {
                "session_id": snapshot.session_id,
                "snapshot_file": str(snapshot_path),
                "transcript_archive": str(transcript_path),
                "resume_script": str(resume_script),
                "status": "success"
            }
            
            print("✅ Housekeeping completed successfully!")
            print(f"📸 Session snapshot: {snapshot_path}")
            print(f"📚 Transcript archive: {transcript_path}")
            print(f"🚀 Resume script: {resume_script}")
            
            return results
            
        except Exception as e:
            print(f"❌ Housekeeping failed: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def create_resumption_script(self, snapshot: SessionSnapshot) -> Path:
        """Create script for seamless workflow resumption."""
        script_path = self.archive_dir / f"resume_{snapshot.session_id}.md"
        
        resume_content = f"""# Resume Script: {snapshot.session_id}

## Context Recovery Commands
```bash
# Load essential project context
@CLAUDE.md
@tasks/001_FTASKS|Phase1_Integrated_System.md
@adrs/000_PADR|bin2nlp.md

# Check current file status
ls -la src/
git status
```

## Session Context
**Last Session**: {snapshot.timestamp}
**Phase**: {snapshot.current_phase}
**Active Task**: {snapshot.active_task}

## Where We Left Off
{snapshot.context_summary}

## Immediate Next Steps
{chr(10).join(f"{i+1}. {step}" for i, step in enumerate(snapshot.next_steps))}

## Files Modified in Last Session
{chr(10).join(f"- {f['filename']} ({f['status']})" for f in snapshot.modified_files[:10])}

## Quick Progress Check
- **Completed Tasks**: {len(snapshot.completed_tasks)} tasks
- **Pending Tasks**: {len(snapshot.pending_tasks)} tasks
- **Git Status**: {'Clean' if not snapshot.git_status.get('has_uncommitted_changes') else 'Has uncommitted changes'}

## Resume Protocol
1. Run context recovery commands above
2. Review current task status in task file
3. Check for any merge conflicts or issues
4. Continue with next steps listed above

## Notes from Last Session
{snapshot.notes}

---
*Generated automatically - modify as needed*
"""
        
        script_path.write_text(resume_content, encoding='utf-8')
        return script_path
    
    def update_claude_md_with_housekeeping(self, snapshot: SessionSnapshot):
        """Update CLAUDE.md with housekeeping information."""
        claude_md_path = self.project_root / "CLAUDE.md"
        
        if not claude_md_path.exists():
            return
        
        # Add housekeeping section
        housekeeping_section = f"""
## Last Housekeeping
- **Session ID**: {snapshot.session_id}
- **Timestamp**: {snapshot.timestamp}
- **Snapshot**: `.housekeeping/snapshots/{snapshot.session_id}.json`
- **Transcript Archive**: `.housekeeping/transcripts/{snapshot.session_id}/`
- **Resume Script**: `.housekeeping/resume_{snapshot.session_id}.md`

### Quick Resume
```bash
# Essential context recovery
@CLAUDE.md
@tasks/001_FTASKS|Phase1_Integrated_System.md
@.housekeeping/resume_{snapshot.session_id}.md
```
"""
        
        # Read current content
        content = claude_md_path.read_text(encoding='utf-8')
        
        # Remove any existing housekeeping section
        lines = content.split('\n')
        filtered_lines = []
        skip_section = False
        
        for line in lines:
            if line.startswith('## Last Housekeeping'):
                skip_section = True
                continue
            elif line.startswith('## ') and skip_section:
                skip_section = False
            
            if not skip_section:
                filtered_lines.append(line)
        
        # Add new housekeeping section before session history
        content = '\n'.join(filtered_lines)
        
        # Insert before session history or at end
        if '## Session History Log' in content:
            content = content.replace('## Session History Log', housekeeping_section + '\n## Session History Log')
        else:
            content += housekeeping_section
        
        claude_md_path.write_text(content, encoding='utf-8')


def main():
    """CLI interface for housekeeping system."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Claude Code Session Housekeeping")
    parser.add_argument("--summary", "-s", help="Context summary for this session")
    parser.add_argument("--next-steps", "-n", nargs="*", help="Next steps for resumption")
    parser.add_argument("--notes", help="Additional notes about the session")
    parser.add_argument("--project-root", help="Project root directory", type=Path)
    
    args = parser.parse_args()
    
    # Initialize housekeeping manager
    manager = HousekeepingManager(args.project_root)
    
    # Perform housekeeping
    results = manager.perform_housekeeping(
        context_summary=args.summary or "",
        next_steps=args.next_steps or [],
        notes=args.notes or ""
    )
    
    if results["status"] == "success":
        print("\n🎉 Housekeeping completed successfully!")
        print(f"\nTo resume this session later, use:")
        print(f"@{results['resume_script']}")
        sys.exit(0)
    else:
        print(f"\n❌ Housekeeping failed: {results.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()