"""
Base model classes for the bin2nlp analysis system.

Provides foundational Pydantic models with common functionality including
validation, serialization, and timestamp management.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set, Type
from uuid import UUID, uuid4

from pydantic import BaseModel as PydanticBaseModel, Field, ConfigDict, field_validator, ValidationError


class BaseModel(PydanticBaseModel):
    """
    Base model class for all bin2nlp data models.
    
    Provides common functionality including:
    - JSON serialization with proper field naming
    - Field validation and type checking
    - Configuration for serialization behavior
    """
    
    model_config = ConfigDict(
        # Use snake_case for field names in JSON
        alias_generator=lambda field_name: field_name,
        # Populate fields by name (allow both alias and field name)
        populate_by_name=True,
        # Validate assignment after model creation
        validate_assignment=True,
        # Use enum values instead of names in serialization
        use_enum_values=True,
        # Allow extra fields to be ignored rather than causing errors
        extra='ignore',
        # Serialize datetime objects as ISO format strings
        json_encoders={
            datetime: lambda dt: dt.isoformat(),
            UUID: lambda uuid_obj: str(uuid_obj),
        }
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model to dictionary with proper field naming.
        
        Returns:
            Dictionary representation of the model
        """
        return self.model_dump(by_alias=True, exclude_none=True)
    
    def to_json(self) -> str:
        """
        Convert model to JSON string.
        
        Returns:
            JSON string representation of the model
        """
        return self.model_dump_json(by_alias=True, exclude_none=True)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """
        Create model instance from dictionary.
        
        Args:
            data: Dictionary containing model data
            
        Returns:
            Model instance
            
        Raises:
            ValidationError: If data doesn't match model schema
        """
        return cls.model_validate(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> "BaseModel":
        """
        Create model instance from JSON string.
        
        Args:
            json_str: JSON string containing model data
            
        Returns:
            Model instance
            
        Raises:
            ValidationError: If JSON doesn't match model schema
        """
        return cls.model_validate_json(json_str)
    
    def update_from_dict(self, data: Dict[str, Any]) -> "BaseModel":
        """
        Update model instance with values from dictionary.
        
        Args:
            data: Dictionary containing updated values
            
        Returns:
            New model instance with updated values
            
        Raises:
            ValidationError: If updated data doesn't match model schema
        """
        current_data = self.to_dict()
        current_data.update(data)
        return self.__class__.from_dict(current_data)
    
    def validate_required_fields(self) -> bool:
        """
        Validate that all required fields are present and valid.
        
        Returns:
            True if all required fields are valid
            
        Raises:
            ValidationError: If any required field is missing or invalid
        """
        try:
            # Re-validate the current instance
            self.__class__.model_validate(self.to_dict())
            return True
        except ValidationError:
            raise
    
    def get_field_names(self) -> Set[str]:
        """
        Get set of all field names in this model.
        
        Returns:
            Set of field names
        """
        return set(self.model_fields.keys())
    
    def get_changed_fields(self, other: "BaseModel") -> Set[str]:
        """
        Compare this model with another and return changed field names.
        
        Args:
            other: Another model instance to compare with
            
        Returns:
            Set of field names that differ between models
            
        Raises:
            TypeError: If comparing with different model type
        """
        if not isinstance(other, self.__class__):
            raise TypeError(f"Cannot compare {self.__class__.__name__} with {type(other).__name__}")
        
        changed_fields = set()
        for field_name in self.get_field_names():
            if getattr(self, field_name) != getattr(other, field_name):
                changed_fields.add(field_name)
        
        return changed_fields
    
    def has_field(self, field_name: str) -> bool:
        """
        Check if model has a specific field.
        
        Args:
            field_name: Name of field to check
            
        Returns:
            True if field exists in model
        """
        return field_name in self.model_fields
    
    def get_field_value(self, field_name: str, default: Any = None) -> Any:
        """
        Get field value with optional default.
        
        Args:
            field_name: Name of field to get
            default: Default value if field doesn't exist
            
        Returns:
            Field value or default
        """
        return getattr(self, field_name, default)
    
    def is_empty(self) -> bool:
        """
        Check if all optional fields are None or empty.
        
        Returns:
            True if model has no meaningful data
        """
        for field_name, field_info in self.model_fields.items():
            value = getattr(self, field_name)
            
            # Skip required fields that have values
            if field_info.is_required() and value is not None:
                return False
            
            # Check if optional field has meaningful value
            if value is not None and value != "" and value != [] and value != {}:
                return False
        
        return True


class TimestampedModel(BaseModel):
    """
    Base model with automatic timestamp management.
    
    Provides created_at and updated_at fields with automatic population
    and validation. Useful for tracking entity lifecycle.
    """
    
    id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the model instance"
    )
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the model was created"
    )
    
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the model was last updated"
    )
    
    def mark_updated(self) -> None:
        """
        Update the updated_at timestamp to current time.
        
        Should be called whenever the model is modified after creation.
        """
        self.updated_at = datetime.now(timezone.utc)
    
    def age_seconds(self) -> float:
        """
        Calculate age of the model in seconds since creation.
        
        Returns:
            Age in seconds as a float
        """
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()
    
    def is_recent(self, max_age_seconds: int = 3600) -> bool:
        """
        Check if the model was created recently.
        
        Args:
            max_age_seconds: Maximum age in seconds to consider recent (default: 1 hour)
            
        Returns:
            True if model was created within the specified time window
        """
        return self.age_seconds() <= max_age_seconds
    
    def time_since_update(self) -> float:
        """
        Calculate time in seconds since last update.
        
        Returns:
            Seconds since last update, or since creation if never updated
        """
        reference_time = self.updated_at if self.updated_at else self.created_at
        return (datetime.now(timezone.utc) - reference_time).total_seconds()
    
    def is_stale(self, max_staleness_seconds: int = 86400) -> bool:
        """
        Check if the model data is considered stale.
        
        Args:
            max_staleness_seconds: Maximum staleness in seconds (default: 24 hours)
            
        Returns:
            True if model hasn't been updated within the specified time window
        """
        return self.time_since_update() > max_staleness_seconds
    
    def get_lifecycle_info(self) -> Dict[str, Any]:
        """
        Get comprehensive lifecycle information for the model.
        
        Returns:
            Dictionary with creation time, update time, age, and staleness info
        """
        age_seconds = self.age_seconds()
        time_since_update = self.time_since_update()
        
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "age_seconds": age_seconds,
            "age_human": self._format_duration(age_seconds),
            "time_since_update_seconds": time_since_update,
            "time_since_update_human": self._format_duration(time_since_update),
            "is_recent": self.is_recent(),
            "is_stale": self.is_stale(),
            "has_been_updated": self.updated_at is not None
        }
    
    def _format_duration(self, seconds: float) -> str:
        """
        Format duration in seconds to human-readable string.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            Human-readable duration string
        """
        if seconds < 60:
            return f"{seconds:.1f} seconds"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f} minutes"
        elif seconds < 86400:
            hours = seconds / 3600
            return f"{hours:.1f} hours"
        else:
            days = seconds / 86400
            return f"{days:.1f} days"
    
    @field_validator('created_at', 'updated_at')
    @classmethod
    def validate_timestamps(cls, v: Optional[datetime]) -> Optional[datetime]:
        """
        Validate timestamp fields.
        
        Args:
            v: Timestamp value to validate
            
        Returns:
            Validated timestamp
            
        Raises:
            ValueError: If timestamp is in the future
        """
        if v is not None and v > datetime.now(timezone.utc):
            raise ValueError("Timestamps cannot be in the future")
        return v
    
    def validate_update_sequence(self) -> bool:
        """
        Validate that updated_at is after created_at if both are present.
        
        Returns:
            True if update sequence is valid
            
        Raises:
            ValueError: If updated_at is before created_at
        """
        if self.updated_at and self.updated_at < self.created_at:
            raise ValueError("updated_at cannot be before created_at")
        return True
    
    def __str__(self) -> str:
        """Enhanced string representation showing ID, age, and update status."""
        age_str = self._format_duration(self.age_seconds())
        update_status = "updated" if self.updated_at else "never updated"
        return f"{self.__class__.__name__}(id={str(self.id)[:8]}..., age={age_str}, {update_status})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging with lifecycle info."""
        return (
            f"{self.__class__.__name__}("
            f"id={self.id}, "
            f"created_at={self.created_at.isoformat()}, "
            f"updated_at={self.updated_at.isoformat() if self.updated_at else None}, "
            f"age_seconds={self.age_seconds():.1f})"
        )
    
    def __eq__(self, other: object) -> bool:
        """
        Enhanced equality comparison for timestamped models.
        
        Args:
            other: Object to compare with
            
        Returns:
            True if models are equal (same ID and class)
        """
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash based on ID for use in sets and dictionaries."""
        return hash(self.id)
    
    def __lt__(self, other: "TimestampedModel") -> bool:
        """Less than comparison based on creation time."""
        if not isinstance(other, TimestampedModel):
            return NotImplemented
        return self.created_at < other.created_at