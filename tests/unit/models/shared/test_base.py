"""
Unit tests for base model classes.

Tests the foundational BaseModel and TimestampedModel classes including
validation, serialization, and timestamp management functionality.
"""

import pytest
from datetime import datetime, timezone
from uuid import UUID

from src.models.shared.base import BaseModel, TimestampedModel


class TestBaseModel:
    """Test cases for BaseModel class."""
    
    def test_basic_instantiation(self):
        """Test basic model creation."""
        model = BaseModel()
        assert isinstance(model, BaseModel)
    
    def test_to_dict_method(self):
        """Test dictionary serialization."""
        model = BaseModel()
        result = model.to_dict()
        assert isinstance(result, dict)
    
    def test_to_json_method(self):
        """Test JSON serialization."""
        model = BaseModel()
        result = model.to_json()
        assert isinstance(result, str)
    
    def test_from_dict_method(self):
        """Test model creation from dictionary."""
        model = BaseModel.from_dict({})
        assert isinstance(model, BaseModel)


class TestTimestampedModel:
    """Test cases for TimestampedModel class."""
    
    def test_basic_instantiation(self):
        """Test basic timestamped model creation."""
        model = TimestampedModel()
        assert isinstance(model, TimestampedModel)
        assert isinstance(model.id, UUID)
        assert isinstance(model.created_at, datetime)
        assert model.updated_at is None
    
    def test_mark_updated(self):
        """Test marking model as updated."""
        model = TimestampedModel()
        assert model.updated_at is None
        
        model.mark_updated()
        assert model.updated_at is not None
        assert isinstance(model.updated_at, datetime)
    
    def test_age_calculation(self):
        """Test age calculation methods."""
        model = TimestampedModel()
        age = model.age_seconds()
        assert isinstance(age, float)
        assert age >= 0
    
    def test_is_recent(self):
        """Test recent check functionality."""
        model = TimestampedModel()
        assert model.is_recent(max_age_seconds=3600)  # Should be recent
    
    def test_lifecycle_info(self):
        """Test lifecycle information retrieval."""
        model = TimestampedModel()
        info = model.get_lifecycle_info()
        
        assert isinstance(info, dict)
        assert 'id' in info
        assert 'created_at' in info
        assert 'age_seconds' in info
        assert 'is_recent' in info
    
    def test_string_representations(self):
        """Test string representation methods."""
        model = TimestampedModel()
        
        str_repr = str(model)
        assert isinstance(str_repr, str)
        assert 'TimestampedModel' in str_repr
        assert 'age=' in str_repr
        
        repr_str = repr(model)
        assert isinstance(repr_str, str)
        assert 'TimestampedModel(' in repr_str
    
    def test_equality_and_hashing(self):
        """Test equality comparison and hashing."""
        model1 = TimestampedModel()
        model2 = TimestampedModel()
        
        # Different models should not be equal
        assert model1 != model2
        
        # Model should equal itself
        assert model1 == model1
        
        # Should be hashable
        model_set = {model1, model2}
        assert len(model_set) == 2