#!/bin/bash
# Claude Code Session Housekeeping Script
# Usage: ./scripts/housekeep.sh [options]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧹 Claude Code Session Housekeeping${NC}"
echo "============================================"

# Get project root (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Error: Not in a git repository${NC}"
    exit 1
fi

# Interactive mode if no arguments provided
if [ $# -eq 0 ]; then
    echo -e "${YELLOW}📝 Interactive Housekeeping Mode${NC}"
    echo
    
    # Get context summary
    echo "Briefly summarize what was accomplished in this session:"
    read -r SUMMARY
    
    # Get next steps
    echo
    echo "What are the immediate next steps? (Enter each on a new line, empty line to finish):"
    NEXT_STEPS=()
    while IFS= read -r line; do
        [[ -z "$line" ]] && break
        NEXT_STEPS+=("$line")
    done
    
    # Get notes
    echo
    echo "Any additional notes for resumption? (optional):"
    read -r NOTES
    
    # Build command arguments
    CMD_ARGS=()
    [[ -n "$SUMMARY" ]] && CMD_ARGS+=(--summary "$SUMMARY")
    [[ ${#NEXT_STEPS[@]} -gt 0 ]] && CMD_ARGS+=(--next-steps "${NEXT_STEPS[@]}")
    [[ -n "$NOTES" ]] && CMD_ARGS+=(--notes "$NOTES")
    
else
    # Use provided arguments
    CMD_ARGS=("$@")
fi

# Add project root to arguments
CMD_ARGS+=(--project-root "$PROJECT_ROOT")

echo
echo -e "${BLUE}🔄 Running housekeeping operation...${NC}"

# Run the Python housekeeping script
if python3 "$SCRIPT_DIR/housekeeping.py" "${CMD_ARGS[@]}"; then
    echo
    echo -e "${GREEN}✅ Housekeeping completed successfully!${NC}"
    echo
    echo -e "${YELLOW}📋 What happened:${NC}"
    echo "  • Session snapshot captured and saved"
    echo "  • Complete transcript archive created for study"
    echo "  • Resume script generated for seamless continuation"
    echo "  • CLAUDE.md updated with housekeeping info"
    echo
    echo -e "${BLUE}🚀 To resume this session:${NC}"
    echo "  1. Load the resume script: @.housekeeping/resume_session_*.md"
    echo "  2. Run the context recovery commands listed in the script"
    echo "  3. Continue with the next steps"
    echo
    echo -e "${YELLOW}💡 Pro tip:${NC} The transcript archive contains all your files"
    echo "   for learning and reference. Check .housekeeping/transcripts/"
    
else
    echo -e "${RED}❌ Housekeeping failed. Check the error messages above.${NC}"
    exit 1
fi