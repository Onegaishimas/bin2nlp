"""
String extraction and categorization processor for binary analysis.

This module provides comprehensive string extraction capabilities using radare2,
with intelligent categorization and significance scoring following the ADR standards.
"""

import re
import asyncio
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
from urllib.parse import urlparse
import structlog

from pydantic import BaseModel, Field, field_validator
from src.models.shared.enums import AnalysisDepth
from src.analysis.engines.r2_integration import R2Session
from src.core.exceptions import BinaryAnalysisException
from src.core.config import get_settings

logger = structlog.get_logger(__name__)


class ExtractedString(BaseModel):
    """Represents a single extracted string with metadata."""
    
    content: str = Field(..., description="The actual string content")
    offset: int = Field(..., ge=0, description="File offset where string was found")
    size: int = Field(..., ge=0, description="Size of string in bytes")
    encoding: str = Field(default="ascii", description="String encoding (ascii, utf-8, utf-16)")
    section: Optional[str] = Field(default=None, description="Binary section containing the string")
    category: str = Field(default="unknown", description="String category classification")
    significance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Significance score 0-1")
    context: Optional[str] = Field(default=None, description="Surrounding context or references")
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate string content is not empty."""
        if not v.strip():
            raise ValueError("String content cannot be empty")
        return v


class StringCategory(BaseModel):
    """String category classification with patterns."""
    
    name: str = Field(..., description="Category name")
    patterns: List[str] = Field(..., description="Regex patterns for matching")
    weight: float = Field(default=1.0, ge=0.0, description="Category weight for significance scoring")
    description: str = Field(..., description="Category description")


class StringExtractionConfig(BaseModel):
    """Configuration for string extraction analysis."""
    
    min_length: int = Field(default=4, ge=1, description="Minimum string length to extract")
    max_length: int = Field(default=1024, ge=1, description="Maximum string length to extract")
    ascii_only: bool = Field(default=False, description="Extract only ASCII strings")
    include_wide_strings: bool = Field(default=True, description="Include UTF-16 wide strings")
    significance_threshold: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum significance score")
    max_strings: int = Field(default=1000, ge=1, description="Maximum number of strings to extract")
    
    @field_validator('max_length')
    @classmethod
    def validate_max_length(cls, v: int, values: Dict[str, Any]) -> int:
        """Ensure max_length is greater than min_length."""
        min_length = values.get('min_length', 4)
        if v <= min_length:
            raise ValueError("max_length must be greater than min_length")
        return v


class StringExtractionResult(BaseModel):
    """Results from string extraction analysis."""
    
    total_strings_found: int = Field(..., ge=0, description="Total number of strings found")
    filtered_strings: List[ExtractedString] = Field(..., description="Filtered and categorized strings")
    categories_found: Dict[str, int] = Field(..., description="Count of strings per category")
    analysis_time_ms: int = Field(..., ge=0, description="Analysis time in milliseconds")
    config_used: StringExtractionConfig = Field(..., description="Configuration used for extraction")


class StringExtractionException(BinaryAnalysisException):
    """Exception raised during string extraction."""
    pass


class StringExtractor:
    """
    Comprehensive string extraction and categorization processor.
    
    Uses radare2 for string extraction with intelligent categorization
    and significance scoring based on content patterns.
    """
    
    def __init__(self):
        """Initialize the string extractor with default categories."""
        self.settings = get_settings()
        self._categories = self._initialize_categories()
        logger.debug("StringExtractor initialized", categories_count=len(self._categories))
    
    def _initialize_categories(self) -> List[StringCategory]:
        """Initialize predefined string categories with patterns."""
        return [
            StringCategory(
                name="url",
                patterns=[
                    r'https?://[^\s<>"{}|\\^`\[\]]+',
                    r'ftp://[^\s<>"{}|\\^`\[\]]+',
                    r'www\.[^\s<>"{}|\\^`\[\]]+',
                ],
                weight=0.9,
                description="URLs and web addresses"
            ),
            StringCategory(
                name="file_path",
                patterns=[
                    r'[A-Za-z]:\\[^<>:"|?*\n\r]+',  # Windows paths
                    r'/[^\s<>"|*\n\r]+\.[a-zA-Z0-9]+',  # Unix paths with extension
                    r'\\\\[^\s<>"|*\n\r]+',  # UNC paths
                ],
                weight=0.8,
                description="File and directory paths"
            ),
            StringCategory(
                name="registry_key",
                patterns=[
                    r'HKEY_[A-Z_]+\\[^<>"|*\n\r]+',
                    r'HKLM\\[^<>"|*\n\r]+',
                    r'HKCU\\[^<>"|*\n\r]+',
                ],
                weight=0.8,
                description="Windows registry keys"
            ),
            StringCategory(
                name="email",
                patterns=[
                    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                ],
                weight=0.7,
                description="Email addresses"
            ),
            StringCategory(
                name="ip_address",
                patterns=[
                    r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
                    r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',  # IPv6
                ],
                weight=0.7,
                description="IP addresses (IPv4 and IPv6)"
            ),
            StringCategory(
                name="credential",
                patterns=[
                    r'password[=:\s]*[^\s]{4,}',
                    r'passwd[=:\s]*[^\s]{4,}',
                    r'pwd[=:\s]*[^\s]{4,}',
                    r'token[=:\s]*[A-Za-z0-9+/=]{16,}',
                    r'api[_-]?key[=:\s]*[A-Za-z0-9+/=]{16,}',
                ],
                weight=0.9,
                description="Potential credentials and secrets"
            ),
            StringCategory(
                name="crypto_key",
                patterns=[
                    r'-----BEGIN [A-Z ]+-----',
                    r'-----END [A-Z ]+-----',
                    r'\b[A-Fa-f0-9]{32,}\b',  # Hex keys
                ],
                weight=0.8,
                description="Cryptographic keys and certificates"
            ),
            StringCategory(
                name="domain",
                patterns=[
                    r'\b[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}\b',
                ],
                weight=0.6,
                description="Domain names"
            ),
            StringCategory(
                name="user_agent",
                patterns=[
                    r'Mozilla/[0-9.]+',
                    r'User-Agent:.*',
                    r'Chrome/[0-9.]+',
                    r'Firefox/[0-9.]+',
                ],
                weight=0.6,
                description="User agent strings"
            ),
            StringCategory(
                name="version",
                patterns=[
                    r'v?[0-9]+\.[0-9]+(?:\.[0-9]+)*',
                    r'version[=:\s]*[0-9]+\.[0-9]+',
                ],
                weight=0.4,
                description="Version numbers"
            ),
            StringCategory(
                name="error_message",
                patterns=[
                    r'error[:\s]*[^\\n\\r]{10,}',
                    r'exception[:\s]*[^\\n\\r]{10,}',
                    r'failed[:\s]*[^\\n\\r]{10,}',
                ],
                weight=0.5,
                description="Error and exception messages"
            ),
            StringCategory(
                name="debug_string",
                patterns=[
                    r'debug[:\s]*[^\\n\\r]{5,}',
                    r'trace[:\s]*[^\\n\\r]{5,}',
                    r'printf.*%[sd]',
                ],
                weight=0.3,
                description="Debug and trace strings"
            ),
        ]
    
    async def extract_strings(
        self, 
        file_path: str, 
        config: Optional[StringExtractionConfig] = None
    ) -> StringExtractionResult:
        """
        Extract and categorize strings from binary file.
        
        Args:
            file_path: Path to binary file to analyze
            config: Optional extraction configuration
            
        Returns:
            StringExtractionResult with categorized strings
            
        Raises:
            StringExtractionException: If extraction fails
        """
        if config is None:
            config = StringExtractionConfig()
            
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(
                "string_extraction_started",
                file_path=file_path,
                min_length=config.min_length,
                max_length=config.max_length
            )
            
            # Extract strings using radare2
            raw_strings = await self._extract_raw_strings(file_path, config)
            
            logger.debug("raw_strings_extracted", count=len(raw_strings))
            
            # Filter and categorize strings
            categorized_strings = self._categorize_strings(raw_strings, config)
            
            # Calculate significance scores
            scored_strings = self._calculate_significance_scores(categorized_strings)
            
            # Filter by significance threshold
            filtered_strings = [
                s for s in scored_strings 
                if s.significance_score >= config.significance_threshold
            ]
            
            # Limit results
            if len(filtered_strings) > config.max_strings:
                filtered_strings = sorted(
                    filtered_strings, 
                    key=lambda x: x.significance_score, 
                    reverse=True
                )[:config.max_strings]
            
            # Count categories
            categories_found = {}
            for string in filtered_strings:
                categories_found[string.category] = categories_found.get(string.category, 0) + 1
            
            analysis_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            
            result = StringExtractionResult(
                total_strings_found=len(raw_strings),
                filtered_strings=filtered_strings,
                categories_found=categories_found,
                analysis_time_ms=analysis_time_ms,
                config_used=config
            )
            
            logger.info(
                "string_extraction_completed",
                total_found=result.total_strings_found,
                filtered_count=len(result.filtered_strings),
                analysis_time_ms=result.analysis_time_ms,
                categories=list(categories_found.keys())
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "string_extraction_failed",
                file_path=file_path,
                error=str(e),
                error_type=type(e).__name__
            )
            raise StringExtractionException(f"Failed to extract strings: {str(e)}") from e
    
    async def _extract_raw_strings(
        self, 
        file_path: str, 
        config: StringExtractionConfig
    ) -> List[ExtractedString]:
        """Extract raw strings from binary using radare2."""
        strings = []
        
        try:
            async with R2Session(file_path) as r2:
                # Configure string extraction parameters
                await r2.execute(f"e str.min={config.min_length}")
                await r2.execute(f"e str.max={config.max_length}")
                
                # Extract ASCII strings
                ascii_result = await r2.execute("izzj")  # JSON format strings
                if ascii_result:
                    ascii_strings = self._parse_r2_strings_json(ascii_result, "ascii")
                    strings.extend(ascii_strings)
                
                # Extract wide strings if enabled
                if config.include_wide_strings:
                    wide_result = await r2.execute("izzwj")  # Wide strings in JSON
                    if wide_result:
                        wide_strings = self._parse_r2_strings_json(wide_result, "utf-16")
                        strings.extend(wide_strings)
                
                # Get section information for context
                sections_result = await r2.execute("iSj")
                sections_map = self._parse_sections_json(sections_result) if sections_result else {}
                
                # Add section context to strings
                for string in strings:
                    string.section = self._find_section_for_offset(string.offset, sections_map)
                
        except Exception as e:
            logger.error("r2_string_extraction_failed", error=str(e))
            raise StringExtractionException(f"radare2 string extraction failed: {str(e)}")
        
        return strings
    
    def _parse_r2_strings_json(self, json_data: str, encoding: str) -> List[ExtractedString]:
        """Parse radare2 JSON string output."""
        import json
        
        strings = []
        try:
            data = json.loads(json_data)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'string' in item:
                        string = ExtractedString(
                            content=item['string'],
                            offset=item.get('vaddr', item.get('paddr', 0)),
                            size=item.get('size', len(item['string'])),
                            encoding=encoding
                        )
                        strings.append(string)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("failed_to_parse_r2_strings", error=str(e))
        
        return strings
    
    def _parse_sections_json(self, json_data: str) -> Dict[str, Tuple[int, int]]:
        """Parse radare2 sections JSON to get offset ranges."""
        import json
        
        sections = {}
        try:
            data = json.loads(json_data)
            if isinstance(data, list):
                for section in data:
                    if isinstance(section, dict) and 'name' in section:
                        start = section.get('vaddr', section.get('paddr', 0))
                        size = section.get('vsize', section.get('size', 0))
                        sections[section['name']] = (start, start + size)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("failed_to_parse_sections", error=str(e))
        
        return sections
    
    def _find_section_for_offset(
        self, 
        offset: int, 
        sections_map: Dict[str, Tuple[int, int]]
    ) -> Optional[str]:
        """Find which section contains the given offset."""
        for section_name, (start, end) in sections_map.items():
            if start <= offset < end:
                return section_name
        return None
    
    def _categorize_strings(
        self, 
        strings: List[ExtractedString], 
        config: StringExtractionConfig
    ) -> List[ExtractedString]:
        """Categorize strings based on content patterns."""
        for string in strings:
            string.category = self._classify_string_content(string.content)
        
        return strings
    
    def _classify_string_content(self, content: str) -> str:
        """Classify a string based on its content using category patterns."""
        content_lower = content.lower().strip()
        
        # Check each category pattern
        for category in self._categories:
            for pattern in category.patterns:
                try:
                    if re.search(pattern, content, re.IGNORECASE):
                        return category.name
                except re.error:
                    logger.warning("invalid_regex_pattern", pattern=pattern, category=category.name)
                    continue
        
        # Default classification based on content characteristics
        if len(content) < 8:
            return "short_string"
        elif content.isdigit():
            return "numeric"
        elif content.isalpha():
            return "text"
        elif any(char in content for char in ['/', '\\', '.']):
            return "path_like"
        else:
            return "unknown"
    
    def _calculate_significance_scores(
        self, 
        strings: List[ExtractedString]
    ) -> List[ExtractedString]:
        """Calculate significance scores for strings based on multiple factors."""
        for string in strings:
            score = 0.0
            
            # Base score from category weight
            category_weight = self._get_category_weight(string.category)
            score += category_weight * 0.4
            
            # Length factor (optimal range scoring)
            length_score = self._calculate_length_score(len(string.content))
            score += length_score * 0.2
            
            # Content complexity factor
            complexity_score = self._calculate_complexity_score(string.content)
            score += complexity_score * 0.2
            
            # Section context factor
            section_score = self._calculate_section_score(string.section)
            score += section_score * 0.1
            
            # Encoding factor
            encoding_score = 0.1 if string.encoding == "ascii" else 0.05
            score += encoding_score * 0.1
            
            string.significance_score = min(score, 1.0)
        
        return strings
    
    def _get_category_weight(self, category_name: str) -> float:
        """Get weight for a specific category."""
        for category in self._categories:
            if category.name == category_name:
                return category.weight
        
        # Default weights for dynamic categories
        weights = {
            "short_string": 0.1,
            "numeric": 0.2,
            "text": 0.3,
            "path_like": 0.5,
            "unknown": 0.2
        }
        return weights.get(category_name, 0.2)
    
    def _calculate_length_score(self, length: int) -> float:
        """Calculate score based on string length (optimal range)."""
        if length < 4:
            return 0.0
        elif length <= 20:
            return 0.8
        elif length <= 50:
            return 1.0
        elif length <= 100:
            return 0.8
        elif length <= 200:
            return 0.6
        else:
            return 0.4
    
    def _calculate_complexity_score(self, content: str) -> float:
        """Calculate score based on content complexity."""
        score = 0.0
        
        # Character variety
        char_types = 0
        if any(c.islower() for c in content):
            char_types += 1
        if any(c.isupper() for c in content):
            char_types += 1
        if any(c.isdigit() for c in content):
            char_types += 1
        if any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in content):
            char_types += 1
        
        score += (char_types / 4.0) * 0.5
        
        # Entropy approximation (simple)
        unique_chars = len(set(content.lower()))
        entropy_score = min(unique_chars / len(content), 1.0) if content else 0.0
        score += entropy_score * 0.5
        
        return min(score, 1.0)
    
    def _calculate_section_score(self, section: Optional[str]) -> float:
        """Calculate score based on binary section context."""
        if not section:
            return 0.0
        
        section_scores = {
            ".text": 0.3,     # Code section
            ".data": 0.8,     # Data section - likely interesting strings
            ".rdata": 0.9,    # Read-only data - often contains strings
            ".rsrc": 0.7,     # Resources
            ".rodata": 0.9,   # Read-only data
            "__TEXT": 0.3,    # macOS text section
            "__DATA": 0.8,    # macOS data section
            "__RODATA": 0.9,  # macOS read-only data
        }
        
        # Check for exact matches first
        for sect_name, score in section_scores.items():
            if sect_name.lower() in section.lower():
                return score
        
        # Default score for unknown sections
        return 0.5


    def get_category_info(self) -> List[Dict[str, Any]]:
        """Get information about all available string categories."""
        return [
            {
                "name": category.name,
                "description": category.description,
                "weight": category.weight,
                "pattern_count": len(category.patterns)
            }
            for category in self._categories
        ]
    
    def add_custom_category(self, category: StringCategory) -> None:
        """Add a custom string category."""
        # Remove existing category with same name
        self._categories = [c for c in self._categories if c.name != category.name]
        self._categories.append(category)
        
        logger.info(
            "custom_category_added",
            category_name=category.name,
            patterns_count=len(category.patterns)
        )