#!/usr/bin/env python3
"""
Configuration CLI utility for bin2nlp.

Provides command-line tools for validating, testing, and debugging
application configuration.
"""

import argparse
import sys
from pathlib import Path

from .config import (
    get_settings,
    create_example_env_file,
    create_configuration_report,
    detect_configuration_issues,
    check_required_environment_variables,
    validate_configuration_consistency,
    load_and_validate_settings,
    validate_and_warn
)


def cmd_validate(args):
    """Validate current configuration."""
    print("🔍 Validating configuration...")
    
    try:
        success = validate_and_warn()
        if success:
            print("✅ Configuration is valid!")
            return 0
        else:
            print("❌ Configuration validation failed!")
            return 1
    except Exception as e:
        print(f"❌ Configuration validation error: {e}")
        return 1


def cmd_report(args):
    """Generate configuration report."""
    try:
        report = create_configuration_report()
        print(report)
        return 0
    except Exception as e:
        print(f"❌ Failed to generate report: {e}")
        return 1


def cmd_check_env(args):
    """Check environment variables and dependencies."""
    print("🔍 Checking environment variables and dependencies...")
    
    success, issues = check_required_environment_variables()
    
    if success:
        print("✅ All environment checks passed!")
        return 0
    else:
        print("❌ Environment issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return 1


def cmd_check_consistency(args):
    """Check configuration consistency."""
    print("🔍 Checking configuration consistency...")
    
    success, errors = validate_configuration_consistency()
    
    if success:
        print("✅ Configuration is consistent!")
        return 0
    else:
        print("❌ Configuration consistency errors:")
        for error in errors:
            print(f"  - {error}")
        return 1


def cmd_create_example(args):
    """Create example environment file."""
    env_file = args.output or ".env.example"
    
    try:
        create_example_env_file(env_file)
        print(f"✅ Created example environment file: {env_file}")
        return 0
    except Exception as e:
        print(f"❌ Failed to create example file: {e}")
        return 1


def cmd_test_load(args):
    """Test loading settings with full validation."""
    print("🔍 Testing settings loading with full validation...")
    
    try:
        settings = load_and_validate_settings()
        print("✅ Settings loaded and validated successfully!")
        
        if args.show_config:
            print("\n=== Current Configuration ===")
            config_dict = settings.to_config_dict()
            for section, values in config_dict.items():
                if isinstance(values, dict):
                    print(f"\n{section}:")
                    for key, value in values.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"{section}: {values}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Failed to load settings: {e}")
        return 1


def cmd_detect_issues(args):
    """Detect and categorize configuration issues."""
    print("🔍 Detecting configuration issues...")
    
    try:
        issues = detect_configuration_issues()
        
        total_issues = sum(len(issue_list) for issue_list in issues.values())
        
        if total_issues == 0:
            print("✅ No configuration issues detected!")
            return 0
        
        print(f"⚠️  Detected {total_issues} total issues:")
        
        if issues["critical"]:
            print(f"\n🚨 CRITICAL ({len(issues['critical'])}):")
            for issue in issues["critical"]:
                print(f"  - {issue}")
        
        if issues["warnings"]:
            print(f"\n⚠️  WARNINGS ({len(issues['warnings'])}):")
            for warning in issues["warnings"]:
                print(f"  - {warning}")
        
        if issues["recommendations"]:
            print(f"\n💡 RECOMMENDATIONS ({len(issues['recommendations'])}):")
            for rec in issues["recommendations"]:
                print(f"  - {rec}")
        
        # Return error code if critical issues found
        return 1 if issues["critical"] else 0
        
    except Exception as e:
        print(f"❌ Failed to detect issues: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="bin2nlp Configuration Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s validate                    # Validate current configuration
  %(prog)s report                      # Generate comprehensive report
  %(prog)s check-env                   # Check environment variables
  %(prog)s check-consistency          # Check configuration consistency
  %(prog)s create-example             # Create .env.example file
  %(prog)s test-load --show-config    # Test loading with config display
  %(prog)s detect-issues              # Detect all configuration issues
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")
    validate_parser.set_defaults(func=cmd_validate)
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate configuration report")
    report_parser.set_defaults(func=cmd_report)
    
    # Check environment command
    env_parser = subparsers.add_parser("check-env", help="Check environment variables")
    env_parser.set_defaults(func=cmd_check_env)
    
    # Check consistency command
    consistency_parser = subparsers.add_parser("check-consistency", help="Check configuration consistency")
    consistency_parser.set_defaults(func=cmd_check_consistency)
    
    # Create example command
    example_parser = subparsers.add_parser("create-example", help="Create example .env file")
    example_parser.add_argument("--output", "-o", help="Output file path (default: .env.example)")
    example_parser.set_defaults(func=cmd_create_example)
    
    # Test load command
    load_parser = subparsers.add_parser("test-load", help="Test loading settings")
    load_parser.add_argument("--show-config", action="store_true", help="Show current configuration")
    load_parser.set_defaults(func=cmd_test_load)
    
    # Detect issues command
    issues_parser = subparsers.add_parser("detect-issues", help="Detect configuration issues")
    issues_parser.set_defaults(func=cmd_detect_issues)
    
    args = parser.parse_args()
    
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())