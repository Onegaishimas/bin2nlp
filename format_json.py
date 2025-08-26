#!/usr/bin/env python3
"""
Script to format compressed JSON files into properly indented multi-line format.
Usage: python3 format_json.py input_file.json [output_file.json]
"""

import json
import sys
import os

def format_json_file(input_file, output_file=None):
    """
    Format a JSON file from compressed single-line to properly indented multi-line format.
    
    Args:
        input_file (str): Path to input JSON file
        output_file (str, optional): Path to output file. If None, will append '_formatted' to input name.
    """
    
    # Determine output filename if not provided
    if output_file is None:
        base_name, ext = os.path.splitext(input_file)
        output_file = f"{base_name}_formatted{ext}"
    
    try:
        print(f"Reading compressed JSON from: {input_file}")
        
        # Read the compressed JSON file
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"Successfully loaded JSON with {len(str(data))} characters")
        
        # Write the formatted JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, separators=(',', ': '))
        
        # Get file sizes for comparison
        input_size = os.path.getsize(input_file)
        output_size = os.path.getsize(output_file)
        
        print(f"Formatted JSON written to: {output_file}")
        print(f"Input file size: {input_size:,} bytes")
        print(f"Output file size: {output_size:,} bytes")
        print(f"Size increase: {((output_size - input_size) / input_size * 100):.1f}%")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON format - {e}")
        return False
    except FileNotFoundError:
        print(f"ERROR: Input file '{input_file}' not found")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    """Main function to handle command line arguments and execute formatting."""
    
    if len(sys.argv) < 2:
        print("Usage: python3 format_json.py input_file.json [output_file.json]")
        print("\nExample:")
        print("  python3 format_json.py ssh-keygen-previous-translation.json")
        print("  python3 format_json.py input.json formatted_output.json")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Validate input file exists
    if not os.path.exists(input_file):
        print(f"ERROR: Input file '{input_file}' does not exist")
        sys.exit(1)
    
    # Format the JSON file
    success = format_json_file(input_file, output_file)
    
    if success:
        print("\n✅ JSON formatting completed successfully!")
    else:
        print("\n❌ JSON formatting failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()