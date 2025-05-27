# app/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

# --- FaceEncoding Schemas ---

class FaceEncodingResponse(BaseModel):
    id: int = Field(..., description="ID của mã hóa khuôn mặt này.")
    # user_id: int # Có thể thêm nếu bạn muốn thấy ID người dùng trực tiếp trên đối tượng mã hóa

    class Config:
        from_attributes = True# Cho phép Pydantic đọc dữ liệu từ model SQLAlchemy

# --- User Schemas ---

class UserCreate(BaseModel): # Schema để tạo người dùng mới
    name: str = Field(..., description="Tên duy nhất của người dùng.")

class UserResponse(BaseModel): # Schema để hiển thị thông tin người dùng
    id: int = Field(..., description="ID của người dùng.")
    name: str = Field(..., description="Tên của người dùng.")
    encodings: List[FaceEncodingResponse] = Field(
        default_factory=list,
        description="Danh sách các mã hóa khuôn mặt của người dùng này."
    )

    class Config:
        from_attributes = True

class RecognitionMatch(BaseModel):
    name: str = Field(..., description="Tên người được nhận dạng, hoặc 'Unknown'.")
    distance: Optional[float] = Field(
        None,
        description="Điểm khoảng cách khuôn mặt (càng thấp càng khớp). Có nếu khớp với khuôn mặt đã biết."
    )

class RecognitionResponse(BaseModel):
    recognized_faces: List[RecognitionMatch] = Field(
        ...,
        description="Danh sách các khuôn mặt tìm thấy trong ảnh và trạng thái nhận dạng."
    )
    message: Optional[str] = Field(
        None,
        description="Thông báo tùy chọn về quá trình nhận dạng."
    )

# --- General API Message Schema ---
class MessageResponse(BaseModel):
    message: str = Field(..., description="Thông báo kết quả hoạt động.")

class RecognitionMatch(BaseModel):
    name: str = Field(..., description="Tên người được nhận dạng, hoặc 'Unknown'.")
    distance: Optional[float] = Field(
        None,
        description="Điểm khoảng cách khuôn mặt (càng thấp càng khớp). Có nếu khớp với khuôn mặt đã biết."
    )
    box: Optional[List[int]] = Field( # THÊM DÒNG NÀY
        None,
        description="Tọa độ [top, right, bottom, left] của khuôn mặt trong ảnh gốc đã gửi đi."
    )

class RecognitionResponse(BaseModel):
    recognized_faces: List[RecognitionMatch] = Field(
        ...,
        description="Danh sách các khuôn mặt tìm thấy trong ảnh và trạng thái nhận dạng."
    )
    message: Optional[str] = Field(
        None,
        description="Thông báo tùy chọn về quá trình nhận dạng."
    )