"""
String extraction and categorization processor for binary analysis.

This module implements comprehensive string extraction from binary files using
radare2 integration, with intelligent categorization and significance scoring.
Follows ADR standards with structured logging and error handling.
"""

import re
import hashlib
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Any, Tuple, Union
from pathlib import Path

from ...core.exceptions import AnalysisException, ProcessorException
from ...core.logging import get_logger
from ...models.shared.enums import StringCategory, StringSignificance
from ...models.analysis.results import StringInfo, StringExtraction, StringContext
from ..engines.r2_integration import R2Session


# String extraction patterns and constants
MIN_STRING_LENGTH = 4
MAX_STRING_LENGTH = 1024
ASCII_PRINTABLE = set(range(32, 127))
UNICODE_RANGES = [
    (0x0020, 0x007E),  # Basic Latin
    (0x00A0, 0x00FF),  # Latin-1 Supplement
    (0x0100, 0x017F),  # Latin Extended-A
    (0x0180, 0x024F),  # Latin Extended-B
]


# StringContext is now imported from results models


class StringExtractor:
    """
    Comprehensive string extraction and categorization processor.
    
    Extracts ASCII and Unicode strings from binary files using radare2,
    categorizes them by type and usage, and scores significance for
    security analysis and reverse engineering workflows.
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Compilation patterns for string categorization
        self._compile_categorization_patterns()
        
        # String filtering settings
        self.min_length = MIN_STRING_LENGTH
        self.max_length = MAX_STRING_LENGTH
        self.extract_ascii = True
        self.extract_unicode = True
        self.extract_wide = True
        
    def _compile_categorization_patterns(self) -> None:
        """Compile regex patterns for string categorization."""
        
        # URL patterns
        self.url_patterns = [
            re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE),
            re.compile(r'ftp://[^\s<>"{}|\\^`\[\]]+', re.IGNORECASE),
            re.compile(r'[a-zA-Z][a-zA-Z0-9+.-]*://[^\s<>"{}|\\^`\[\]]+'),
        ]
        
        # File path patterns
        self.file_path_patterns = [
            re.compile(r'[A-Za-z]:\\(?:[^\\/:*?"<>|\r\n]+\\)*[^\\/:*?"<>|\r\n]*'),  # Windows paths
            re.compile(r'/(?:[^/\0]+/)*[^/\0]+'),  # Unix paths
            re.compile(r'\\\\[^\\]+\\[^\\]+(?:\\[^\\]*)*'),  # UNC paths
        ]
        
        # Registry key patterns
        self.registry_patterns = [
            re.compile(r'HKEY_[A-Z_]+\\[^\\]+(?:\\[^\\]*)*', re.IGNORECASE),
            re.compile(r'HKLM\\[^\\]+(?:\\[^\\]*)*', re.IGNORECASE),
            re.compile(r'HKCU\\[^\\]+(?:\\[^\\]*)*', re.IGNORECASE),
        ]
        
        # Domain and hostname patterns
        self.domain_patterns = [
            re.compile(r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}'),
            re.compile(r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'),
        ]
        
        # Email patterns
        self.email_patterns = [
            re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'),
        ]
        
        # Credential patterns (simple detection)
        self.credential_patterns = [
            re.compile(r'(?:password|passwd|pwd|pass|key|secret|token|auth)', re.IGNORECASE),
            re.compile(r'(?:username|user|login|account|uid)', re.IGNORECASE),
            re.compile(r'(?:api[_-]?key|access[_-]?token|bearer[_-]?token)', re.IGNORECASE),
        ]
        
        # Configuration patterns
        self.config_patterns = [
            re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*\s*=\s*[^\s]+'),  # key=value
            re.compile(r'\[([^\]]+)\]'),  # INI sections
            re.compile(r'<([^>]+)>'),  # XML/HTML tags
        ]
        
        # Executable/library patterns
        self.executable_patterns = [
            re.compile(r'[a-zA-Z0-9_-]+\.(?:exe|dll|sys|ocx|cpl|scr|drv)', re.IGNORECASE),
            re.compile(r'[a-zA-Z0-9_-]+\.(?:so|dylib|a|o)', re.IGNORECASE),
        ]
        
        # Network service patterns
        self.service_patterns = [
            re.compile(r'(?:tcp|udp)://[^\s]+', re.IGNORECASE),
            re.compile(r'(?:smtp|pop3|imap|ftp|ssh|telnet|http|https)://[^\s]+', re.IGNORECASE),
        ]
        
        # Format string patterns
        self.format_patterns = [
            re.compile(r'%[sdxoicpfge%]'),  # C format strings
            re.compile(r'\{[0-9]*\}'),  # .NET format strings
            re.compile(r'%\([^)]+\)[sdxoicpfge]'),  # Python format strings
        ]
        
        # Command line patterns
        self.command_patterns = [
            re.compile(r'--?[a-zA-Z][a-zA-Z0-9-]*'),  # Command line flags
            re.compile(r'/[a-zA-Z][a-zA-Z0-9]*'),  # Windows command flags
        ]
    
    async def extract_strings(
        self,
        r2_session: R2Session,
        min_length: Optional[int] = None,
        max_length: Optional[int] = None,
        include_context: bool = True
    ) -> StringExtraction:
        """
        Extract strings from binary using radare2 with comprehensive analysis.
        
        Args:
            r2_session: Active radare2 session
            min_length: Minimum string length (default: 4)
            max_length: Maximum string length (default: 1024)
            include_context: Whether to extract context information
            
        Returns:
            StringExtraction with categorized strings and metadata
            
        Raises:
            ProcessorException: If string extraction fails
        """
        try:
            self.logger.info("starting_string_extraction",
                           min_length=min_length or self.min_length,
                           max_length=max_length or self.max_length,
                           include_context=include_context)
            
            min_len = min_length or self.min_length
            max_len = max_length or self.max_length
            
            # Extract different types of strings
            ascii_strings = await self._extract_ascii_strings(r2_session, min_len, max_len)
            unicode_strings = await self._extract_unicode_strings(r2_session, min_len, max_len)
            wide_strings = await self._extract_wide_strings(r2_session, min_len, max_len)
            
            # Combine all strings
            all_strings = ascii_strings + unicode_strings + wide_strings
            
            # Add context information if requested
            if include_context:
                all_strings = await self._add_context_information(r2_session, all_strings)
            
            # Categorize strings
            categorized_strings = self._categorize_strings(all_strings)
            
            # Calculate significance scores
            scored_strings = self._score_string_significance(categorized_strings)
            
            # Create extraction result
            extraction_result = StringExtraction(
                total_strings=len(scored_strings),
                ascii_count=len(ascii_strings),
                unicode_count=len(unicode_strings),
                wide_count=len(wide_strings),
                strings=scored_strings,
                extraction_settings={
                    'min_length': min_len,
                    'max_length': max_len,
                    'include_context': include_context,
                    'extract_ascii': self.extract_ascii,
                    'extract_unicode': self.extract_unicode,
                    'extract_wide': self.extract_wide
                }
            )
            
            self.logger.info("string_extraction_complete",
                           total_strings=len(scored_strings),
                           ascii_count=len(ascii_strings),
                           unicode_count=len(unicode_strings),
                           wide_count=len(wide_strings))
            
            return extraction_result
            
        except Exception as e:
            self.logger.error("string_extraction_failed", error=str(e))
            raise ProcessorException(f"String extraction failed: {str(e)}")
    
    async def _extract_ascii_strings(
        self,
        r2_session: R2Session,
        min_length: int,
        max_length: int
    ) -> List[StringInfo]:
        """Extract ASCII strings using radare2."""
        try:
            # Use radare2 string extraction command
            cmd = f"izj~{{}}[?len>={min_length}][?len<={max_length}]"
            result = await r2_session.execute_command(cmd)
            
            strings = []
            if result and isinstance(result, list):
                for string_data in result:
                    if not isinstance(string_data, dict):
                        continue
                    
                    string_info = StringInfo(
                        value=string_data.get('string', ''),
                        address=string_data.get('vaddr', 0),
                        size=string_data.get('size', 0),
                        length=string_data.get('length', 0),
                        encoding='ascii',
                        section=string_data.get('section', ''),
                        type=string_data.get('type', 'ascii'),
                        context=StringContext(address=string_data.get('vaddr', 0))
                    )
                    strings.append(string_info)
            
            return strings
            
        except Exception as e:
            self.logger.warning("ascii_string_extraction_failed", error=str(e))
            return []
    
    async def _extract_unicode_strings(
        self,
        r2_session: R2Session,
        min_length: int,
        max_length: int
    ) -> List[StringInfo]:
        """Extract Unicode strings using radare2."""
        try:
            # Extract Unicode strings
            cmd = f"izu~{{}}[?len>={min_length}][?len<={max_length}]"
            result = await r2_session.execute_command(cmd)
            
            strings = []
            if result and isinstance(result, list):
                for string_data in result:
                    if not isinstance(string_data, dict):
                        continue
                    
                    string_info = StringInfo(
                        value=string_data.get('string', ''),
                        address=string_data.get('vaddr', 0),
                        size=string_data.get('size', 0),
                        length=string_data.get('length', 0),
                        encoding='unicode',
                        section=string_data.get('section', ''),
                        type=string_data.get('type', 'unicode'),
                        context=StringContext(address=string_data.get('vaddr', 0))
                    )
                    strings.append(string_info)
            
            return strings
            
        except Exception as e:
            self.logger.warning("unicode_string_extraction_failed", error=str(e))
            return []
    
    async def _extract_wide_strings(
        self,
        r2_session: R2Session,
        min_length: int,
        max_length: int
    ) -> List[StringInfo]:
        """Extract wide (UTF-16) strings using radare2."""
        try:
            # Extract wide strings (UTF-16)
            cmd = f"izw~{{}}[?len>={min_length}][?len<={max_length}]"
            result = await r2_session.execute_command(cmd)
            
            strings = []
            if result and isinstance(result, list):
                for string_data in result:
                    if not isinstance(string_data, dict):
                        continue
                    
                    string_info = StringInfo(
                        value=string_data.get('string', ''),
                        address=string_data.get('vaddr', 0),
                        size=string_data.get('size', 0),
                        length=string_data.get('length', 0),
                        encoding='utf-16',
                        section=string_data.get('section', ''),
                        type=string_data.get('type', 'wide'),
                        context=StringContext(address=string_data.get('vaddr', 0))
                    )
                    strings.append(string_info)
            
            return strings
            
        except Exception as e:
            self.logger.warning("wide_string_extraction_failed", error=str(e))
            return []
    
    async def _add_context_information(
        self,
        r2_session: R2Session,
        strings: List[StringInfo]
    ) -> List[StringInfo]:
        """Add context information to extracted strings."""
        try:
            # Get section information
            sections_cmd = "iSj"
            sections_result = await r2_session.execute_command(sections_cmd)
            section_map = {}
            
            if sections_result and isinstance(sections_result, list):
                for section in sections_result:
                    if isinstance(section, dict):
                        start = section.get('vaddr', 0)
                        end = start + section.get('vsize', 0)
                        section_map[(start, end)] = section.get('name', '')
            
            # Get function information
            functions_cmd = "aflj"
            functions_result = await r2_session.execute_command(functions_cmd)
            function_map = {}
            
            if functions_result and isinstance(functions_result, list):
                for func in functions_result:
                    if isinstance(func, dict):
                        start = func.get('offset', 0)
                        end = start + func.get('size', 0)
                        function_map[(start, end)] = func.get('name', '')
            
            # Enhance string context
            for string_info in strings:
                addr = string_info.address
                
                # Find section
                for (start, end), section_name in section_map.items():
                    if start <= addr < end:
                        string_info.context.section_name = section_name
                        break
                
                # Find containing function
                for (start, end), func_name in function_map.items():
                    if start <= addr < end:
                        string_info.context.function_name = func_name
                        break
                
                # Get cross-references
                xrefs_cmd = f"axtj @ {addr}"
                xrefs_result = await r2_session.execute_command(xrefs_cmd)
                
                if xrefs_result and isinstance(xrefs_result, list):
                    for xref in xrefs_result:
                        if isinstance(xref, dict):
                            from_addr = xref.get('from', 0)
                            if from_addr:
                                string_info.context.xrefs_from.append(from_addr)
            
            return strings
            
        except Exception as e:
            self.logger.warning("context_extraction_failed", error=str(e))
            return strings
    
    def _categorize_strings(self, strings: List[StringInfo]) -> List[StringInfo]:
        """Categorize strings based on content patterns."""
        for string_info in strings:
            value = string_info.value
            categories = set()
            
            # Check URL patterns
            if any(pattern.search(value) for pattern in self.url_patterns):
                categories.add(StringCategory.URL)
            
            # Check file path patterns
            if any(pattern.search(value) for pattern in self.file_path_patterns):
                categories.add(StringCategory.FILE_PATH)
            
            # Check registry patterns
            if any(pattern.search(value) for pattern in self.registry_patterns):
                categories.add(StringCategory.REGISTRY)
            
            # Check domain patterns
            if any(pattern.search(value) for pattern in self.domain_patterns):
                categories.add(StringCategory.DOMAIN)
            
            # Check email patterns
            if any(pattern.search(value) for pattern in self.email_patterns):
                categories.add(StringCategory.EMAIL)
            
            # Check credential patterns
            if any(pattern.search(value) for pattern in self.credential_patterns):
                categories.add(StringCategory.CREDENTIAL)
            
            # Check configuration patterns
            if any(pattern.search(value) for pattern in self.config_patterns):
                categories.add(StringCategory.CONFIGURATION)
            
            # Check executable patterns
            if any(pattern.search(value) for pattern in self.executable_patterns):
                categories.add(StringCategory.EXECUTABLE)
            
            # Check service patterns
            if any(pattern.search(value) for pattern in self.service_patterns):
                categories.add(StringCategory.NETWORK_SERVICE)
            
            # Check format string patterns
            if any(pattern.search(value) for pattern in self.format_patterns):
                categories.add(StringCategory.FORMAT_STRING)
            
            # Check command patterns
            if any(pattern.search(value) for pattern in self.command_patterns):
                categories.add(StringCategory.COMMAND_LINE)
            
            # Default to generic if no specific category found
            if not categories:
                if value.isprintable() and len(value.strip()) > 0:
                    categories.add(StringCategory.GENERIC)
                else:
                    categories.add(StringCategory.BINARY_DATA)
            
            string_info.categories = list(categories)
        
        return strings
    
    def _score_string_significance(self, strings: List[StringInfo]) -> List[StringInfo]:
        """Score string significance for analysis prioritization."""
        for string_info in strings:
            score = 0.0
            factors = []
            
            # Base score from categories
            category_scores = {
                StringCategory.CREDENTIAL: 10.0,
                StringCategory.URL: 8.0,
                StringCategory.NETWORK_SERVICE: 8.0,
                StringCategory.EMAIL: 7.0,
                StringCategory.REGISTRY: 7.0,
                StringCategory.CONFIGURATION: 6.0,
                StringCategory.FILE_PATH: 5.0,
                StringCategory.EXECUTABLE: 5.0,
                StringCategory.DOMAIN: 4.0,
                StringCategory.FORMAT_STRING: 3.0,
                StringCategory.COMMAND_LINE: 3.0,
                StringCategory.GENERIC: 1.0,
                StringCategory.BINARY_DATA: 0.5
            }
            
            max_category_score = max(
                (category_scores.get(cat, 1.0) for cat in string_info.categories),
                default=1.0
            )
            score += max_category_score
            factors.append(f"category_max={max_category_score}")
            
            # Length factor (longer strings often more significant)
            length_factor = min(string_info.length / 50.0, 2.0)
            score += length_factor
            factors.append(f"length={length_factor:.2f}")
            
            # Cross-reference factor
            if string_info.context and string_info.context.xrefs_from:
                xref_factor = min(len(string_info.context.xrefs_from) / 5.0, 3.0)
                score += xref_factor
                factors.append(f"xrefs={xref_factor:.2f}")
            
            # Section factor (.data, .rdata more significant than .rsrc)
            if string_info.context and string_info.context.section_name:
                section_name = string_info.context.section_name.lower()
                if any(s in section_name for s in ['.data', '.rdata', '.rodata']):
                    score += 2.0
                    factors.append("section_data=2.0")
                elif '.text' in section_name:
                    score += 1.5
                    factors.append("section_text=1.5")
                elif '.rsrc' in section_name:
                    score -= 1.0
                    factors.append("section_rsrc=-1.0")
            
            # Entropy factor (random-looking strings might be encoded/encrypted)
            entropy = self._calculate_string_entropy(string_info.value)
            if entropy > 6.0:  # High entropy
                score += 2.0
                factors.append(f"high_entropy={entropy:.2f}")
            elif entropy < 3.0:  # Low entropy (repetitive)
                score -= 1.0
                factors.append(f"low_entropy={entropy:.2f}")
            
            # Determine significance level
            if score >= 12.0:
                significance = StringSignificance.CRITICAL
            elif score >= 8.0:
                significance = StringSignificance.HIGH
            elif score >= 5.0:
                significance = StringSignificance.MEDIUM
            elif score >= 2.0:
                significance = StringSignificance.LOW
            else:
                significance = StringSignificance.NOISE
            
            string_info.significance = significance
            string_info.significance_score = score
            string_info.significance_factors = factors
        
        return strings
    
    def _calculate_string_entropy(self, string_value: str) -> float:
        """Calculate Shannon entropy of a string."""
        if not string_value:
            return 0.0
        
        # Count character frequencies
        char_counts = {}
        for char in string_value:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # Calculate entropy
        string_length = len(string_value)
        entropy = 0.0
        
        for count in char_counts.values():
            probability = count / string_length
            if probability > 0:
                entropy -= probability * (probability).bit_length()
        
        return entropy