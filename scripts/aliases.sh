#!/bin/bash
# Claude Code Project Aliases
# Source this file in your shell: source scripts/aliases.sh

# Get project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Housekeeping aliases
alias housekeep="$PROJECT_ROOT/scripts/housekeep.sh"
alias hk="$PROJECT_ROOT/scripts/housekeep.sh"
alias clear-resume="$PROJECT_ROOT/scripts/clear_resume"
alias clear-context="$PROJECT_ROOT/scripts/clear_resume"
alias smart-clear="$PROJECT_ROOT/scripts/clear_resume"

# Quick housekeeping with common patterns
alias hk-quick="$PROJECT_ROOT/scripts/housekeep.sh --summary 'Quick session checkpoint' --next-steps 'Continue with current task'"
alias hk-task="$PROJECT_ROOT/scripts/housekeep.sh --summary 'Completed task checkpoint'"
alias hk-break="$PROJECT_ROOT/scripts/housekeep.sh --summary 'Taking a break - work in progress'"

# Resume from last housekeeping
alias resume-last="find $PROJECT_ROOT/.housekeeping -name 'resume_session_*.md' -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-"

# Quick project navigation
alias cdproj="cd $PROJECT_ROOT"
alias cdsrc="cd $PROJECT_ROOT/src"
alias cdtasks="cd $PROJECT_ROOT/tasks"
alias cdhk="cd $PROJECT_ROOT/.housekeeping"

# Quick file access
alias claude="cat $PROJECT_ROOT/CLAUDE.md"
alias tasks="cat $PROJECT_ROOT/tasks/001_FTASKS|Phase1_Integrated_System.md"
alias adr="cat $PROJECT_ROOT/adrs/000_PADR|bin2nlp.md"

# Git shortcuts for this project
alias gs="git status"
alias gd="git diff"
alias gl="git log --oneline -10"
alias ga="git add"
alias gc="git commit"
alias gp="git push"

echo "🔧 Claude Code aliases loaded!"
echo "  Context: clear-resume, clear-context, smart-clear (intelligent /clear prep)"
echo "  Housekeeping: housekeep, hk, hk-quick, hk-task, hk-break"
echo "  Navigation: cdproj, cdsrc, cdtasks, cdhk" 
echo "  Files: claude, tasks, adr"
echo "  Git: gs, gd, gl, ga, gc, gp"