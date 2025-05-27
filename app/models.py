# app/models.py
import json
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship # For defining relationships
import numpy as np
from typing import List

from .database import Base

MAX_ENCODINGS_PER_USER = 10

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    encodings = relationship("FaceEncoding", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', num_encodings={len(self.encodings) if self.encodings else 0})>"

class FaceEncoding(Base):
    __tablename__ = "face_encodings"

    id = Column(Integer, primary_key=True, index=True)
    encoding_data = Column(Text, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="encodings")

    def get_encoding_array(self) -> np.ndarray:
        """Converts the JSON string encoding back to a numpy array."""
        if self.encoding_data:
            try:
                return np.array(json.loads(self.encoding_data))
            except json.JSONDecodeError:
                # Log this
                raise ValueError("Invalid face encoding data format.")
        raise ValueError("FaceEncoding object has no encoding data.")

    def set_encoding_array(self, encoding_array: np.ndarray):
        """Converts a numpy array encoding to a JSON string for storage."""
        if not isinstance(encoding_array, np.ndarray) or encoding_array.ndim != 1 or encoding_array.size == 0:
            raise ValueError("Invalid encoding array provided: Must be a non-empty 1D numpy array.")
        self.encoding_data = json.dumps(encoding_array.tolist())

    def __repr__(self):
        return f"<FaceEncoding(id={self.id}, user_id={self.user_id})>"