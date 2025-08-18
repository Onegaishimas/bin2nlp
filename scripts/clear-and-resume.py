#!/usr/bin/env python3
"""
Intelligent Context Clear and Resume System

Automatically captures full context, performs housekeeping, clears the session,
and provides immediate resumption instructions for Claude Code.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from housekeeping import HousekeepingManager, SessionSnapshot


class IntelligentClearResume:
    """Manages intelligent context clearing and resumption."""
    
    def __init__(self, project_root: Path = None):
        """Initialize the clear/resume system."""
        self.project_root = project_root or Path.cwd()
        self.hk_manager = HousekeepingManager(self.project_root)
    
    def auto_detect_current_context(self) -> dict:
        """Auto-detect what we're currently working on."""
        try:
            # Read CLAUDE.md for current status
            claude_md_data = self.hk_manager.read_claude_md()
            current_status = claude_md_data.get('current_status', {})
            
            # Read task file for progress
            task_data = self.hk_manager.read_task_file()
            
            # Get git changes
            git_state = self.hk_manager.capture_git_state()
            
            # Auto-generate context summary
            phase = current_status.get('Phase', 'Unknown phase')
            next_steps = current_status.get('Next Steps', 'Unknown next steps')
            
            # Detect recent changes
            recent_files = []
            if git_state.get('status_files'):
                for status_line in git_state['status_files'][:5]:  # Top 5 files
                    if len(status_line) >= 3:
                        filename = status_line[3:]
                        recent_files.append(filename)
            
            # Auto-generate summary
            summary = f"Working on {phase}. Next: {next_steps}"
            if recent_files:
                summary += f". Recently modified: {', '.join(recent_files[:3])}"
            
            # Extract next steps from current status
            next_steps_list = []
            if 'Next Steps' in current_status:
                # Try to parse next steps
                steps_text = current_status['Next Steps']
                if 'Task' in steps_text:
                    next_steps_list = [steps_text]
                else:
                    next_steps_list = [line.strip() for line in steps_text.split(',') if line.strip()]
            
            # Add fallback next steps based on pending tasks
            if not next_steps_list and task_data.get('pending_tasks'):
                next_steps_list = task_data['pending_tasks'][:3]  # First 3 pending tasks
            
            return {
                'summary': summary,
                'next_steps': next_steps_list,
                'notes': f"Auto-context clear at {datetime.now().strftime('%H:%M')}. "
                        f"Progress: {len(task_data.get('completed_tasks', []))} tasks done, "
                        f"{len(task_data.get('pending_tasks', []))} pending.",
                'detected_phase': phase,
                'recent_files': recent_files
            }
            
        except Exception as e:
            return {
                'summary': f"Context clear checkpoint - {datetime.now().strftime('%H:%M')}",
                'next_steps': ['Continue current work'],
                'notes': f"Auto-detected context (error: {str(e)})",
                'detected_phase': 'Unknown',
                'recent_files': []
            }
    
    def create_instant_resume_commands(self, session_id: str) -> str:
        """Create immediate resume commands for copy-paste."""
        
        # Essential context recovery
        commands = [
            f"# 🚀 INSTANT RESUME - Session {session_id}",
            "",
            "# 1. Load core project context",
            "@CLAUDE.md",
            "@tasks/001_FTASKS|Phase1_Integrated_System.md", 
            "@adrs/000_PADR|bin2nlp.md",
            "",
            "# 2. Load session resume script",
            f"@.housekeeping/resume_{session_id}.md",
            "",
            "# 3. Check current status", 
            "ls -la src/",
            "git status",
            "",
            "# 4. Quick project overview",
            "/compact",
            "",
            "# ✅ READY TO CONTINUE!"
        ]
        
        return "\n".join(commands)
    
    def perform_intelligent_clear(self) -> dict:
        """Perform intelligent context clear with auto-resume."""
        print("🧠 Performing intelligent context clear...")
        
        # Auto-detect current context
        context = self.auto_detect_current_context()
        
        print(f"📍 Detected: {context['detected_phase']}")
        print(f"📝 Summary: {context['summary']}")
        print(f"📋 Next Steps: {len(context['next_steps'])} items")
        
        # Perform housekeeping with detected context
        snapshot = self.hk_manager.capture_session_snapshot(
            context_summary=context['summary'],
            next_steps=context['next_steps'],
            notes=context['notes']
        )
        
        # Save snapshot
        snapshot_path = self.hk_manager.save_session_snapshot(snapshot)
        
        # Create transcript archive  
        transcript_path = self.hk_manager.create_transcript_archive(snapshot.session_id)
        
        # Create resume script
        resume_script = self.hk_manager.create_resumption_script(snapshot)
        
        # Update CLAUDE.md
        self.hk_manager.update_claude_md_with_housekeeping(snapshot)
        
        # Create instant resume commands
        instant_commands = self.create_instant_resume_commands(snapshot.session_id)
        
        # Create a quick resume file for immediate use
        quick_resume_path = self.project_root / ".housekeeping" / "QUICK_RESUME.md"
        quick_resume_path.write_text(instant_commands, encoding='utf-8')
        
        return {
            'session_id': snapshot.session_id,
            'snapshot_path': snapshot_path,
            'transcript_path': transcript_path, 
            'resume_script': resume_script,
            'quick_resume_path': quick_resume_path,
            'instant_commands': instant_commands,
            'detected_context': context
        }


def main():
    """Main execution for clear and resume."""
    print("🚀 Intelligent Context Clear & Resume")
    print("=====================================")
    
    try:
        # Initialize system
        clear_resume = IntelligentClearResume()
        
        # Perform intelligent clear
        result = clear_resume.perform_intelligent_clear()
        
        print("\n✅ Context intelligently captured!")
        print(f"📸 Session: {result['session_id']}")
        print(f"📚 Archive: {result['transcript_path']}")
        print(f"🚀 Resume: {result['resume_script']}")
        
        print("\n" + "="*60)
        print("🎯 COPY-PASTE THESE COMMANDS TO RESUME:")
        print("="*60)
        print(result['instant_commands'])
        print("="*60)
        
        print(f"\n💡 Quick resume file: @.housekeeping/QUICK_RESUME.md")
        print("\n🧹 You can now safely use /clear - everything is preserved!")
        
        # Also save commands to a file for easy access
        commands_file = Path.cwd() / "RESUME_COMMANDS.txt"
        commands_file.write_text(result['instant_commands'])
        print(f"📄 Commands also saved to: {commands_file}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())