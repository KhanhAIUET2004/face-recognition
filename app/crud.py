# app/crud.py
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import numpy as np
from typing import List, Tuple, Optional
from sqlalchemy.orm import selectinload

from . import models
from . import schemas # Mặc dù không trực tiếp dùng schemas trong CRUD, nhưng nó liên quan

# --- User CRUD Operations ---

def get_user(db: Session, user_id: int) -> Optional[models.User]:
    """
    Lấy một người dùng bằng ID.
    """
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_name(db: Session, name: str) -> Optional[models.User]:
    """
    Lấy một người dùng bằng tên.
    Tên người dùng là duy nhất.
    """
    return db.query(models.User).filter(models.User.name == name).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[models.User]:
    """
    Lấy danh sách người dùng với phân trang.
    """
    return db.query(models.User).offset(skip).limit(limit).all()

def create_user_with_encodings(db: Session, name: str, encodings_np: List[np.ndarray]) -> Optional[models.User]:
    """
    Tạo một người dùng mới với danh sách các mã hóa khuôn mặt ban đầu.
    Các mã hóa được chuyển đổi thành đối tượng FaceEncoding.
    """
    if not name:
        raise ValueError("Tên người dùng không được để trống.")
    if get_user_by_name(db, name):
        raise ValueError(f"Người dùng với tên '{name}' đã tồn tại.")
    
    if len(encodings_np) > models.MAX_ENCODINGS_PER_USER:
        # Hoặc bạn có thể chỉ lấy MAX_ENCODINGS_PER_USER phần tử đầu tiên
        raise ValueError(f"Số lượng mã hóa vượt quá giới hạn {models.MAX_ENCODINGS_PER_USER}.")

    db_user = models.User(name=name)
    
    for enc_np in encodings_np:
        db_encoding = models.FaceEncoding()
        try:
            db_encoding.set_encoding_array(enc_np)
            db_user.encodings.append(db_encoding) # SQLAlchemy sẽ tự động set user_id khi commit
        except ValueError as e:
            # Log lỗi này nếu cần thiết
            print(f"Lỗi khi set encoding cho user {name}: {e}")
            # Có thể quyết định rollback hoặc bỏ qua encoding lỗi
            # Hiện tại, nếu một encoding lỗi, user vẫn có thể được tạo với các encoding hợp lệ khác
            pass 
            # Hoặc raise lại lỗi nếu muốn toàn bộ quá trình thất bại
            # raise ValueError(f"Không thể xử lý một trong các mã hóa: {e}") from e

    if not db_user.encodings: # Nếu không có encoding nào hợp lệ được thêm
        # Quyết định xem có cho phép tạo user không có encoding không.
        # Hiện tại, nếu không có encoding nào, user vẫn được tạo.
        # Nếu muốn yêu cầu ít nhất 1 encoding, có thể raise lỗi ở đây:
        # raise ValueError("Không có mã hóa hợp lệ nào được cung cấp để tạo người dùng.")
        pass

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError as e: # Bắt lỗi nếu tên user bị trùng do race condition (ít khả năng với check get_user_by_name)
        db.rollback()
        # Log the error e
        raise ValueError(f"Lỗi Integrity khi tạo user '{name}': {e.orig}") from e
    except Exception as e:
        db.rollback()
        # Log the error e
        raise RuntimeError(f"Lỗi không xác định khi tạo user '{name}': {e}") from e


def add_encodings_to_user(db: Session, user_id: int, encodings_np: List[np.ndarray]) -> Optional[models.User]:
    """
    Thêm các mã hóa khuôn mặt mới cho một người dùng hiện tại.
    Kiểm tra giới hạn số lượng mã hóa.
    """
    db_user = get_user(db, user_id)
    if not db_user:
        return None # Hoặc raise HTTPException(status_code=404, detail="User not found") từ API layer

    current_encoding_count = len(db_user.encodings)
    allowed_new_encodings = models.MAX_ENCODINGS_PER_USER - current_encoding_count

    if allowed_new_encodings <= 0:
        # User đã đạt giới hạn, không thể thêm nữa
        # Có thể raise lỗi hoặc trả về user hiện tại mà không thay đổi
        raise ValueError(f"Người dùng {db_user.name} đã đạt giới hạn mã hóa.")

    encodings_to_add_np = encodings_np[:allowed_new_encodings] # Chỉ lấy số lượng được phép

    if not encodings_to_add_np: # Nếu không có encoding nào được cung cấp hoặc đã cắt hết
        return db_user # Trả về user hiện tại không thay đổi

    for enc_np in encodings_to_add_np:
        db_encoding = models.FaceEncoding()
        try:
            db_encoding.set_encoding_array(enc_np)
            # db_encoding.user_id = db_user.id # Không cần thiết nếu dùng append và relationship được cấu hình đúng
            db_user.encodings.append(db_encoding)
        except ValueError as e:
            print(f"Lỗi khi set encoding cho user {db_user.name} (ID: {user_id}): {e}")
            # Xử lý lỗi tương tự như create_user_with_encodings
            pass

    try:
        db.commit()
        db.refresh(db_user)
        return db_user
    except Exception as e:
        db.rollback()
        # Log the error e
        raise RuntimeError(f"Lỗi khi thêm encoding cho user ID {user_id}: {e}") from e

def delete_user(db: Session, user_id: int) -> bool:
    """
    Xóa một người dùng và tất cả các mã hóa liên quan (do cascade).
    Trả về True nếu xóa thành công, False nếu không tìm thấy user.
    """
    db_user = get_user(db, user_id)
    if db_user:
        try:
            db.delete(db_user)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            # Log the error e
            print(f"Lỗi khi xóa user ID {user_id}: {e}") # Ghi log lỗi
            return False # Hoặc raise lại lỗi để API layer xử lý
    return False

# --- FaceEncoding CRUD Operations (thường được quản lý thông qua User) ---

def get_face_encoding(db: Session, encoding_id: int) -> Optional[models.FaceEncoding]:
    """
    Lấy một mã hóa khuôn mặt cụ thể bằng ID của nó.
    """
    return db.query(models.FaceEncoding).filter(models.FaceEncoding.id == encoding_id).first()

# Hàm này thường không cần thiết nếu bạn chỉ thêm/xóa encoding qua User.
# Nhưng có thể hữu ích nếu bạn muốn xóa một encoding cụ thể mà không xóa user.
def delete_face_encoding(db: Session, encoding_id: int) -> bool:
    """
    Xóa một mã hóa khuôn mặt cụ thể.
    """
    db_encoding = get_face_encoding(db, encoding_id)
    if db_encoding:
        try:
            db.delete(db_encoding)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            # Log the error e
            print(f"Lỗi khi xóa encoding ID {encoding_id}: {e}")
            return False
    return False


def get_all_known_encodings_and_names(db: Session) -> Tuple[List[np.ndarray], List[str]]:
    """
    Lấy tất cả các mã hóa khuôn mặt đã biết và tên người dùng tương ứng từ database.
    Sử dụng cho việc so sánh trong quá trình nhận dạng.
    """
    all_users_with_encodings = db.query(models.User).options(
        # `joinedload` hoặc `selectinload` để tải các encodings liên quan một cách hiệu quả
        # `joinedload` sẽ thực hiện JOIN, `selectinload` sẽ thực hiện một query riêng.
        # Chọn joinedload nếu bạn thường xuyên cần truy cập cả user và encodings cùng lúc
        # và số lượng encodings trên mỗi user không quá lớn.
        # from sqlalchemy.orm import joinedload
        # joinedload(models.User.encodings) 
        # Dùng selectinload để tránh cartesian product nếu một user có nhiều encoding
        selectinload(models.User.encodings)
    ).all()

    known_encodings_list: List[np.ndarray] = []
    known_names_list: List[str] = []

    for user in all_users_with_encodings:
        if user.encodings: # Chỉ xử lý user có encodings
            for face_encoding_obj in user.encodings:
                try:
                    encoding_array = face_encoding_obj.get_encoding_array()
                    known_encodings_list.append(encoding_array)
                    known_names_list.append(user.name) # Mỗi encoding tương ứng với tên của user đó
                except ValueError as e:
                    # Log lỗi này: encoding bị hỏng trong DB
                    print(f"Lỗi khi đọc encoding ID {face_encoding_obj.id} cho user {user.name}: {e}")
                    pass # Bỏ qua encoding lỗi

    return known_encodings_list, known_names_list