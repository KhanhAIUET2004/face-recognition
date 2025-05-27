# app/main.py

from fastapi import FastAPI, File, UploadFile, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import numpy as np
from typing import List, Tuple, Optional # Đảm bảo Optional được import
import os

# Thêm các import này
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse 

# Đảm bảo các import này đúng với cấu trúc thư mục của bạn
from . import crud
from . import models
from . import schemas
from . import face_utils
from .database import SessionLocal, engine, get_db 

# Tạo các bảng trong database nếu chúng chưa tồn tại
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Face Recognition API with Frontend",
    description="API for user registration and face recognition, also serving frontend files.",
    version="1.0.2" # Cập nhật version
)

# --- Cấu hình đường dẫn đến thư mục gốc của project ---
PROJECT_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# --- Cấu hình CORS ---
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Mount thư mục tĩnh ---
# Phục vụ các file CSS từ thư mục "css" ở gốc
app.mount("/css", StaticFiles(directory=os.path.join(PROJECT_ROOT_PATH, "css")), name="css_files")
# Phục vụ các file JavaScript từ thư mục "js" ở gốc
app.mount("/js", StaticFiles(directory=os.path.join(PROJECT_ROOT_PATH, "js")), name="js_files")
# Nếu bạn có thư mục images, cũng mount tương tự:
# app.mount("/images", StaticFiles(directory=os.path.join(PROJECT_ROOT_PATH, "images")), name="images_folder")


# --- Endpoints phục vụ các trang HTML ---

@app.get("/", response_class=FileResponse, tags=["Frontend Pages"], name="home_page")
async def serve_index_page():
    index_path = os.path.join(PROJECT_ROOT_PATH, "index.html")
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="index.html not found")
    return FileResponse(index_path)

# Đổi tên route để tránh trùng với API /register nếu có
@app.get("/register-page", response_class=FileResponse, tags=["Frontend Pages"], name="register_user_page")
async def serve_register_page():
    register_path = os.path.join(PROJECT_ROOT_PATH, "register.html")
    if not os.path.exists(register_path):
        raise HTTPException(status_code=404, detail="register.html not found")
    return FileResponse(register_path)

@app.get("/recognize-page", response_class=FileResponse, tags=["Frontend Pages"], name="recognize_face_page")
async def serve_recognize_page():
    recognize_path = os.path.join(PROJECT_ROOT_PATH, "recognize.html")
    if not os.path.exists(recognize_path):
        raise HTTPException(status_code=404, detail="recognize.html not found")
    return FileResponse(recognize_path)

# --- Các API Endpoints ---

@app.post("/api/users/register_with_multiple_faces/", response_model=schemas.UserResponse, tags=["API - Users"])
async def api_register_user_with_multiple_faces(
    username: str = Query(..., min_length=3, max_length=50, description="Tên người dùng để đăng ký."),
    image_files: List[UploadFile] = File(..., description=f"Danh sách các file ảnh chứa khuôn mặt (tối đa {models.MAX_ENCODINGS_PER_USER} mã hóa sẽ được lưu)."),
    db: Session = Depends(get_db)
):
    if not image_files:
        raise HTTPException(status_code=400, detail="Cần ít nhất một file ảnh để đăng ký.")

    # Giới hạn số lượng file ảnh có thể xử lý trong một request để tránh quá tải
    # Frontend có thể gửi nhiều hơn, nhưng backend chỉ xử lý tối đa một số lượng nhất định
    MAX_FILES_TO_PROCESS_AT_ONCE = 10 
    if len(image_files) > MAX_FILES_TO_PROCESS_AT_ONCE:
        raise HTTPException(status_code=400, detail=f"Chỉ cho phép tối đa {MAX_FILES_TO_PROCESS_AT_ONCE} ảnh mỗi lần đăng ký qua API.")

    user_encodings_np: List[np.ndarray] = []
    processed_images_count = 0
    face_detection_errors = 0
    successful_encodings_from_files = 0

    for image_file in image_files:
        if not image_file.content_type or not image_file.content_type.startswith("image/"):
            print(f"Bỏ qua file không phải ảnh: {image_file.filename}")
            continue

        image_bytes = await image_file.read()
        try:
            image_np = face_utils.load_image_into_numpy_array(image_bytes)
            if image_np is None:
                print(f"DEBUG: image_np is None sau khi load từ {image_file.filename}")
                face_detection_errors += 1
                continue
        except ValueError as e:
            print(f"Lỗi khi đọc ảnh {image_file.filename}: {str(e)}")
            face_detection_errors += 1
            continue
        
        current_image_encodings = face_utils.get_face_encodings_from_image(image_np)
        
        if not current_image_encodings:
            print(f"Không tìm thấy khuôn mặt trong ảnh: {image_file.filename}")
            face_detection_errors += 1
            continue
        
        # Lấy encoding đầu tiên tìm thấy trong mỗi ảnh (hoặc logic khác nếu cần)
        user_encodings_np.append(current_image_encodings[0])
        successful_encodings_from_files += 1
        processed_images_count +=1 # Đếm cả ảnh xử lý thành công encoding

        if len(user_encodings_np) >= models.MAX_ENCODINGS_PER_USER:
            print(f"Đã đạt giới hạn {models.MAX_ENCODINGS_PER_USER} mã hóa. Dừng xử lý thêm ảnh.")
            break 
    
    if not user_encodings_np:
        detail_message = "Không thể trích xuất bất kỳ mã hóa khuôn mặt nào từ các ảnh được cung cấp."
        if face_detection_errors > 0:
            detail_message += f" ({face_detection_errors} ảnh không thể xử lý hoặc không tìm thấy khuôn mặt)."
        if processed_images_count == 0 and len(image_files) > 0 and face_detection_errors == len(image_files):
             detail_message = "Tất cả các ảnh được cung cấp không thể xử lý hoặc không tìm thấy khuôn mặt."
        raise HTTPException(status_code=400, detail=detail_message)

    db_user = crud.get_user_by_name(db, name=username)
    if db_user:
        # Logic hiện tại: nếu user đã tồn tại, thì sẽ thêm các encoding mới này vào (nếu còn chỗ)
        # Điều này khác với logic trước là báo lỗi. Hãy chọn logic bạn muốn.
        # Giả sử frontend có cơ chế kiểm tra user tồn tại hoặc người dùng biết họ đang thêm ảnh.
        print(f"Người dùng '{username}' đã tồn tại. Thử thêm mã hóa mới...")
        try:
            # user_encodings_np đã được giới hạn bởi MAX_ENCODINGS_PER_USER ở vòng lặp trên
            updated_user = crud.add_encodings_to_user(db=db, user_id=db_user.id, encodings_np=user_encodings_np)
            if not updated_user:
                 raise HTTPException(status_code=500, detail="Không thể cập nhật mã hóa cho người dùng hiện tại.")
            
            # Tạo response message tùy chỉnh
            response_data = schemas.UserResponse.model_validate(updated_user) # Pydantic V2
            # response_data.message = f"Đã cập nhật người dùng '{username}'. Xử lý {processed_images_count} ảnh, thêm {successful_encodings_from_files} mã hóa mới. Tổng số mã hóa: {len(updated_user.encodings)}."
            # Để có message, bạn cần thêm trường `message: Optional[str] = None` vào `schemas.UserResponse`
            return response_data

        except ValueError as e: # Lỗi từ crud.add_encodings_to_user (ví dụ: đã đạt giới hạn)
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=f"Lỗi server khi cập nhật người dùng: {str(e)}")
    else:
        # Tạo user mới
        print(f"Tạo người dùng mới '{username}' với {len(user_encodings_np)} mã hóa.")
        try:
            # user_encodings_np đã được giới hạn bởi MAX_ENCODINGS_PER_USER
            created_user = crud.create_user_with_encodings(db=db, name=username, encodings_np=user_encodings_np)
        except ValueError as e: # Lỗi từ crud (ví dụ: tên user đã tồn tại do race condition)
            raise HTTPException(status_code=409 if "đã tồn tại" in str(e).lower() else 400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=f"Lỗi server khi tạo người dùng: {str(e)}")

        if not created_user:
            raise HTTPException(status_code=500, detail="Không thể tạo người dùng mới do lỗi không xác định.")
        
        # response_data = schemas.UserResponse.from_orm(created_user) # Pydantic V1
        response_data = schemas.UserResponse.model_validate(created_user) # Pydantic V2
        # response_data.message = f"Đã tạo người dùng '{username}'. Xử lý {processed_images_count} ảnh, lưu {len(created_user.encodings)} mã hóa."
        return response_data


@app.post("/api/recognize/", response_model=schemas.RecognitionResponse, tags=["API - Recognition"])
async def api_recognize_faces_in_image(
    image_file: UploadFile = File(..., description="Ảnh cần nhận dạng khuôn mặt."),
    db: Session = Depends(get_db)
):
    if not image_file.content_type or not image_file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File tải lên không phải là ảnh.")

    image_bytes = await image_file.read()
    try:
        unknown_image_np = face_utils.load_image_into_numpy_array(image_bytes)
        if unknown_image_np is None: # Quan trọng
            print("DEBUG: unknown_image_np is None after load in recognize endpoint!")
            raise HTTPException(status_code=400, detail="Không thể xử lý ảnh tải lên (ảnh lỗi hoặc không được hỗ trợ).")
    except ValueError as e:
        print(f"ERROR loading image for recognition: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Không thể đọc hoặc xử lý ảnh: {str(e)}")
    
    # print(f"DEBUG (recognize): unknown_image_np.shape: {unknown_image_np.shape}, dtype: {unknown_image_np.dtype}")

    face_locations = []
    unknown_encodings_np = []
    try:
        # Sử dụng model="hog" (mặc định) cho tốc độ, hoặc "cnn" cho độ chính xác cao hơn nhưng chậm hơn
        face_locations = face_recognition.face_locations(unknown_image_np, model="hog") 
        if face_locations: # Chỉ lấy encoding nếu có location
            unknown_encodings_np = face_recognition.face_encodings(unknown_image_np, known_face_locations=face_locations)
    except Exception as e:
        print(f"ERROR in face_recognition processing (main.py): {type(e).__name__} - {e}")
        # Cân nhắc việc lưu ảnh lỗi để debug nếu cần
        # from PIL import Image
        # import time
        # try:
        #     error_img = Image.fromarray(unknown_image_np)
        #     error_img.save(f"error_image_recognize_{int(time.time())}.jpg")
        #     print("DEBUG: Saved error image from recognize endpoint.")
        # except Exception as save_err:
        #     print(f"DEBUG: Could not save error image: {save_err}")
        raise HTTPException(status_code=500, detail=f"Server error during face detection: {str(e)}")

    # Trường hợp 1: Không tìm thấy khuôn mặt nào (cả location và encoding đều rỗng)
    if not face_locations: # Nếu không có face_locations thì cũng không có unknown_encodings_np
        return schemas.RecognitionResponse(
            recognized_faces=[],
            message="Không tìm thấy khuôn mặt nào trong ảnh được cung cấp."
        )
    
    # Trường hợp 2: Có locations nhưng không có encodings (hiếm khi xảy ra với face_recognition, nhưng để an toàn)
    # Điều này có nghĩa là face_recognition.face_encodings() không trả về gì dù có locations.
    if face_locations and not unknown_encodings_np:
        recognized_matches_only_locs: List[schemas.RecognitionMatch] = []
        for loc in face_locations:
             recognized_matches_only_locs.append(schemas.RecognitionMatch(name="Unknown (encoding error)", distance=None, box=list(loc)))
        return schemas.RecognitionResponse(
            recognized_faces=recognized_matches_only_locs,
            message=f"Phát hiện {len(face_locations)} vị trí khuôn mặt nhưng không thể tạo mã hóa."
        )

    # Từ đây, chúng ta chắc chắn có cả face_locations và unknown_encodings_np (cùng số lượng)

    known_encodings_from_db, known_names_from_db = crud.get_all_known_encodings_and_names(db)
    
    # Trường hợp 3: Có khuôn mặt trong ảnh gửi lên, nhưng DB không có dữ liệu để so sánh
    if not known_encodings_from_db:
        recognized_matches_no_db: List[schemas.RecognitionMatch] = []
        for i, loc in enumerate(face_locations): # Dùng face_locations đã có
             # unknown_encoding = unknown_encodings_np[i] # không cần thiết vì không có gì để so sánh
             recognized_matches_no_db.append(schemas.RecognitionMatch(name="Unknown (no known faces in DB)", distance=None, box=list(loc)))
        return schemas.RecognitionResponse(
            recognized_faces=recognized_matches_no_db,
            message=f"Phát hiện {len(face_locations)} khuôn mặt, nhưng không có dữ liệu khuôn mặt nào trong hệ thống để so sánh."
        )

    # Trường hợp 4: Xử lý nhận dạng chính
    recognized_matches: List[schemas.RecognitionMatch] = []
    for i, unknown_encoding_single in enumerate(unknown_encodings_np): # Đổi tên biến để tránh nhầm lẫn
        current_location = face_locations[i] # (top, right, bottom, left)
        name, distance = face_utils.find_best_match(
            unknown_encoding=unknown_encoding_single,
            known_encodings=known_encodings_from_db,
            known_names=known_names_from_db,
            tolerance=face_utils.RECOGNITION_TOLERANCE
        )
        if name and distance is not None: # Tìm thấy match
            recognized_matches.append(schemas.RecognitionMatch(name=name, distance=distance, box=list(current_location)))
        else: # Không tìm thấy match (vượt tolerance)
            recognized_matches.append(schemas.RecognitionMatch(name="Unknown", distance=None, box=list(current_location)))
            
    message = f"Đã xử lý {len(unknown_encodings_np)} khuôn mặt được phát hiện."
    
    # Kiểm tra xem có match nào không, nếu không thì message có thể cụ thể hơn
    found_known_face = any(match.name != "Unknown" and match.name != "Unknown (encoding error)" and match.name != "Unknown (no known faces in DB)" for match in recognized_matches)
    if not found_known_face and recognized_matches: # Có phát hiện nhưng không match ai
        message += " Không nhận dạng được khuôn mặt nào đã biết."
    elif not recognized_matches and unknown_encodings_np : # Lỗi logic đâu đó nếu có encoding mà không có match (kể cả Unknown)
        message = "Lỗi logic: Có mã hóa nhưng không có kết quả nhận dạng."


    return schemas.RecognitionResponse(
        recognized_faces=recognized_matches,
        message=message
    )


# --- Các Endpoints CRUD cơ bản cho Users ---
@app.get("/api/users/", response_model=List[schemas.UserResponse], tags=["API - Users Management"])
def api_read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@app.get("/api/users/{user_id}", response_model=schemas.UserResponse, tags=["API - Users Management"])
def api_read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@app.delete("/api/users/{user_id}", response_model=schemas.MessageResponse, tags=["API - Users Management"])
def api_delete_user_endpoint(user_id: int, db: Session = Depends(get_db)):
    deleted = crud.delete_user(db, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found or could not be deleted")
    return schemas.MessageResponse(message=f"User with ID {user_id} and their encodings successfully deleted.")

# Import face_recognition ở đầu file nếu chưa có
import face_recognition 