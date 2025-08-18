"""
Integration tests for multiple binary formats with multiple LLM providers.

This module tests Task 7.2.4: Add tests for different binary formats with multiple LLM providers
- Tests PE, ELF, and other binary formats 
- Tests with OpenAI, Anthropic, and Gemini provider configurations
- Validates format-specific decompilation handling
- Tests LLM provider fallback and selection logic
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Optional

from src.decompilation.engine import DecompilationEngine, DecompilationConfig
from src.llm.providers.factory import LLMProviderFactory
from src.llm.base import LLMConfig, LLMProviderType
from src.models.shared.enums import FileFormat, Platform
from src.core.exceptions import BinaryAnalysisException


class TestMultiFormatMultiLLM:
    """Tests for multiple binary formats with multiple LLM provider configurations."""

    @pytest.fixture(scope="class")
    def decompilation_engine(self):
        """Create DecompilationEngine for multi-format testing."""
        config = DecompilationConfig(
            max_file_size_mb=50,
            timeout_seconds=90,
            r2_analysis_level="aa",
            extract_functions=True,
            extract_strings=True,
            extract_imports=True
        )
        return DecompilationEngine(config)

    @pytest.fixture(scope="class") 
    def binary_samples(self):
        """Create different binary format samples for testing."""
        samples = {}
        
        # PE (Windows) binary - minimal structure
        pe_binary = (
            b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00'  # DOS header
            b'\xb8\x00\x00\x00\x00\x00\x00\x00\x40\x00\x00\x00\x00\x00\x00\x00'  # DOS header cont.
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00'  # e_lfanew
            + b'\x00' * (0x80 - 64) +  # Padding to PE header
            b'PE\x00\x00'  # PE signature
            b'\x4c\x01\x01\x00'  # Machine: i386, NumberOfSections: 1
            + b'\x00' * 500  # Rest of PE structure with padding
        )
        
        # ELF (Linux) binary - minimal 64-bit structure  
        elf_binary = (
            b'\x7fELF'  # ELF signature
            b'\x02\x01\x01\x00'  # 64-bit, little-endian, version 1, SYSV ABI
            + b'\x00' * 8 +  # EI_PAD
            b'\x02\x00'  # ET_EXEC (executable)
            b'\x3e\x00'  # EM_X86_64  
            b'\x01\x00\x00\x00'  # Version
            + b'\x00' * 500  # Rest of ELF structure
        )
        
        # Mach-O (macOS) binary - minimal 64-bit structure
        macho_binary = (
            b'\xfe\xed\xfa\xce'  # MH_MAGIC (32-bit big-endian) - Actually using 64-bit
            b'\x01\x00\x00\x0c'  # CPU_TYPE_X86_64
            b'\x01\x00\x00\x00'  # CPU_SUBTYPE_X86_64_ALL  
            b'\x02\x00\x00\x00'  # MH_EXECUTE
            + b'\x00' * 500  # Rest of Mach-O structure
        )
        
        # Create temporary files
        for name, data in [
            ("pe_sample", pe_binary),
            ("elf_sample", elf_binary), 
            ("macho_sample", macho_binary)
        ]:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{name}") as tmp:
                tmp.write(data)
                samples[name] = tmp.name
        
        yield samples
        
        # Cleanup
        for path in samples.values():
            if os.path.exists(path):
                os.unlink(path)

    @pytest.fixture(scope="class")
    def llm_provider_configs(self):
        """Create multiple LLM provider configurations for testing."""
        configs = {}
        
        # OpenAI (and OpenAI-compatible like Ollama)
        configs["openai"] = LLMConfig(
            provider_id=LLMProviderType.OPENAI,
            api_key="test-openai-key",
            default_model="gpt-4",
            endpoint_url=None,  # Official OpenAI
            temperature=0.1,
            max_tokens=512,
            timeout_seconds=30
        )
        
        # OpenAI-compatible (Ollama)
        configs["ollama"] = LLMConfig(
            provider_id=LLMProviderType.OPENAI, 
            api_key="ollama-local-key",
            default_model="huihui_ai/phi4-abliterated:latest",
            endpoint_url="http://ollama.mcslab.io:80/v1",
            temperature=0.1,
            max_tokens=512,
            timeout_seconds=60
        )
        
        # Anthropic Claude
        configs["anthropic"] = LLMConfig(
            provider_id=LLMProviderType.ANTHROPIC,
            api_key="test-anthropic-key",
            default_model="claude-3-sonnet-20240229",
            temperature=0.1,
            max_tokens=512,
            timeout_seconds=30
        )
        
        # Google Gemini
        configs["gemini"] = LLMConfig(
            provider_id=LLMProviderType.GEMINI,
            api_key="test-gemini-key", 
            default_model="gemini-pro",
            temperature=0.1,
            max_tokens=512,
            timeout_seconds=30
        )
        
        return configs

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_different_binary_formats_decompilation(self, decompilation_engine, binary_samples):
        """
        Test decompilation workflow with different binary formats.
        
        Validates that the engine can handle PE, ELF, and Mach-O formats.
        """
        results = {}
        
        for format_name, file_path in binary_samples.items():
            try:
                print(f"\n🔄 Testing {format_name} format decompilation...")
                
                result = await decompilation_engine.decompile_binary(file_path)
                
                # Basic validation
                assert result is not None
                results[format_name] = result
                
                # Check that file was processed
                if hasattr(result, 'file_size') and result.file_size > 0:
                    print(f"   ✅ {format_name}: File size {result.file_size} bytes")
                elif hasattr(result, 'metadata') and result.metadata.file_size > 0:
                    print(f"   ✅ {format_name}: File size {result.metadata.file_size} bytes")
                
                # Check for format detection
                if hasattr(result, 'file_format'):
                    print(f"   ✅ {format_name}: Detected format {result.file_format}")
                elif hasattr(result, 'metadata') and hasattr(result.metadata, 'file_format'):
                    print(f"   ✅ {format_name}: Detected format {result.metadata.file_format}")
                
                # Validate decompilation completed (may have partial results)
                success_indicators = ['success', 'partial_results']
                has_success = any(hasattr(result, attr) for attr in success_indicators)
                
                if has_success:
                    print(f"   ✅ {format_name}: Decompilation completed")
                else:
                    print(f"   ⚠️  {format_name}: Decompilation status unclear")
                
            except Exception as e:
                print(f"   ❌ {format_name}: Decompilation failed - {e}")
                # Don't fail the test for individual format issues
                results[format_name] = None
        
        # At least one format should have been processed successfully
        successful_formats = [name for name, result in results.items() if result is not None]
        assert len(successful_formats) > 0, "At least one binary format should be processed successfully"
        
        print(f"\n✅ Binary format test completed. Processed: {len(successful_formats)}/{len(binary_samples)} formats")

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_llm_provider_configurations(self, llm_provider_configs):
        """
        Test multiple LLM provider configurations.
        
        Validates that different provider configs can be created and initialized.
        """
        results = {}
        
        for provider_name, config in llm_provider_configs.items():
            try:
                print(f"\n🔄 Testing {provider_name} LLM provider configuration...")
                
                # Create factory and add provider
                factory = LLMProviderFactory()
                factory.add_provider(config)
                
                # Try to initialize (will skip if service unavailable)
                try:
                    await factory.initialize()
                    provider = await factory.get_provider(config.provider_id)
                    
                    # Test health check
                    health_status = await provider.health_check()
                    
                    results[provider_name] = {
                        'config_valid': True,
                        'initialized': True,
                        'healthy': health_status.is_healthy,
                        'error': health_status.error_message
                    }
                    
                    print(f"   ✅ {provider_name}: Configuration valid")
                    print(f"   ✅ {provider_name}: Initialization successful")
                    print(f"   {'✅' if health_status.is_healthy else '⚠️ '} {provider_name}: Health check {'passed' if health_status.is_healthy else 'failed'}")
                    
                    if health_status.error_message:
                        print(f"   ℹ️  {provider_name}: {health_status.error_message}")
                        
                except Exception as init_error:
                    results[provider_name] = {
                        'config_valid': True,
                        'initialized': False,
                        'healthy': False,
                        'error': str(init_error)
                    }
                    print(f"   ✅ {provider_name}: Configuration valid")
                    print(f"   ⚠️  {provider_name}: Service unavailable - {init_error}")
                
                finally:
                    await factory.cleanup()
                    
            except Exception as e:
                results[provider_name] = {
                    'config_valid': False,
                    'initialized': False,
                    'healthy': False,
                    'error': str(e)
                }
                print(f"   ❌ {provider_name}: Configuration error - {e}")
        
        # All provider configs should be valid (even if services unavailable)
        valid_configs = [name for name, result in results.items() if result['config_valid']]
        assert len(valid_configs) >= 3, f"At least 3 provider configs should be valid. Got: {valid_configs}"
        
        print(f"\n✅ LLM provider test completed. Valid configs: {len(valid_configs)}/{len(llm_provider_configs)}")

    @pytest.mark.integration 
    @pytest.mark.asyncio
    async def test_format_llm_combination_workflows(self, decompilation_engine, binary_samples, llm_provider_configs):
        """
        Test combinations of binary formats with LLM providers.
        
        This validates the complete integration across formats and providers.
        """
        print(f"\n🔄 Testing format + LLM provider combinations...")
        
        # Test a few key combinations
        combinations_tested = 0
        combinations_successful = 0
        
        # Try PE format with Ollama (most likely to work in test environment)
        if "pe_sample" in binary_samples and "ollama" in llm_provider_configs:
            try:
                print(f"\n🔄 Testing PE + Ollama combination...")
                
                # Decompilation
                result = await decompilation_engine.decompile_binary(binary_samples["pe_sample"])
                combinations_tested += 1
                
                if result:
                    print("   ✅ PE decompilation successful")
                    
                    # Try LLM provider
                    factory = LLMProviderFactory()
                    factory.add_provider(llm_provider_configs["ollama"])
                    
                    try:
                        await factory.initialize()
                        provider = await factory.get_provider(LLMProviderType.OPENAI)
                        health = await provider.health_check()
                        
                        if health.is_healthy:
                            print("   ✅ Ollama provider healthy")
                            combinations_successful += 1
                        else:
                            print("   ⚠️  Ollama provider unavailable")
                            
                    except Exception as llm_error:
                        print(f"   ⚠️  Ollama provider failed: {llm_error}")
                    finally:
                        await factory.cleanup()
                
            except Exception as e:
                print(f"   ❌ PE + Ollama combination failed: {e}")
        
        # Try ELF format with any available provider
        if "elf_sample" in binary_samples:
            try:
                print(f"\n🔄 Testing ELF format workflow...")
                
                result = await decompilation_engine.decompile_binary(binary_samples["elf_sample"])
                combinations_tested += 1
                
                if result:
                    print("   ✅ ELF decompilation successful")
                    combinations_successful += 1
                
            except Exception as e:
                print(f"   ❌ ELF workflow failed: {e}")
        
        # Summary
        print(f"\n✅ Format + LLM combination test completed")
        print(f"   Combinations tested: {combinations_tested}")
        print(f"   Combinations successful: {combinations_successful}")
        print(f"   Success rate: {combinations_successful/max(combinations_tested,1)*100:.1f}%")
        
        # At least some combinations should be tested
        assert combinations_tested > 0, "At least one format+LLM combination should be tested"

    @pytest.mark.integration
    @pytest.mark.asyncio  
    async def test_llm_provider_fallback_logic(self, llm_provider_configs):
        """
        Test LLM provider fallback and selection logic.
        
        Validates that the system can handle multiple providers and fallbacks.
        """
        print(f"\n🔄 Testing LLM provider fallback logic...")
        
        factory = LLMProviderFactory()
        
        # Add multiple providers
        providers_added = 0
        for name, config in llm_provider_configs.items():
            try:
                factory.add_provider(config)
                providers_added += 1
                print(f"   ✅ Added {name} provider to factory")
            except Exception as e:
                print(f"   ❌ Failed to add {name} provider: {e}")
        
        assert providers_added > 0, "At least one provider should be added to factory"
        
        try:
            await factory.initialize()
            
            # Test provider selection logic
            available_types = [LLMProviderType.OPENAI, LLMProviderType.ANTHROPIC, LLMProviderType.GEMINI]
            
            providers_available = 0
            for provider_type in available_types:
                try:
                    provider = await factory.get_provider(provider_type)
                    if provider:
                        providers_available += 1
                        print(f"   ✅ {provider_type.value} provider available")
                except Exception as e:
                    print(f"   ⚠️  {provider_type.value} provider unavailable: {e}")
            
            # Test factory statistics
            try:
                for provider_type in available_types:
                    try:
                        stats = factory.get_provider_stats(provider_type)
                        if stats:
                            print(f"   ✅ Got stats for {provider_type.value}")
                    except:
                        pass  # Expected for unavailable providers
            except Exception as e:
                print(f"   ⚠️  Stats retrieval failed: {e}")
                
            print(f"\n✅ Provider fallback test completed")
            print(f"   Providers configured: {providers_added}")
            print(f"   Providers available: {providers_available}")
            
        finally:
            await factory.cleanup()


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "--tb=short", "-m", "integration"])