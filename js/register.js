// js/register.js
document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('videoElement');
    const captureButton = document.getElementById('captureButton');
    const usernameInput = document.getElementById('username');
    const messageArea = document.getElementById('messageArea');
    const capturedImagesContainer = document.getElementById('capturedImagesContainer'); // Thêm div để chứa ảnh đã chụp
    const registerAllButton = document.getElementById('registerAllButton'); // Nút mới để gửi tất cả ảnh
    const instructionText = document.getElementById('instructionText'); // Để hướng dẫn

    const MAX_CAPTURES = 10;
    let stream;
    let capturedBlobs = []; // Mảng lưu trữ các blob ảnh đã chụp
    let captureCount = 0;

    async function startCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
            video.srcObject = stream;
            video.onloadedmetadata = () => {
                // Không cần set canvas.width/height ở đây nữa vì sẽ tạo canvas tạm khi chụp
                updateInstructionText();
            };
        } catch (err) {
            console.error("Lỗi truy cập camera:", err);
            showMessage(`Lỗi truy cập camera: ${err.message}`, 'error');
        }
    }

    function showMessage(message, type = 'info') {
        messageArea.textContent = message;
        messageArea.className = type;
    }

    function updateInstructionText() {
        if (captureCount < MAX_CAPTURES) {
            instructionText.textContent = `Vui lòng chụp ${MAX_CAPTURES - captureCount} ảnh nữa. Hãy thay đổi góc mặt, biểu cảm.`;
            captureButton.disabled = false;
            registerAllButton.style.display = 'none';
        } else {
            instructionText.textContent = `Đã chụp đủ ${MAX_CAPTURES} ảnh. Sẵn sàng đăng ký!`;
            captureButton.disabled = true;
            registerAllButton.style.display = 'inline-block';
        }
    }

    function displayCapturedImage(blob) {
        const imageUrl = URL.createObjectURL(blob);
        const imgElement = document.createElement('img');
        imgElement.src = imageUrl;
        imgElement.style.width = "100px"; // Kích thước thumbnail
        imgElement.style.height = "auto";
        imgElement.style.margin = "5px";
        imgElement.style.border = "1px solid #ccc";
        capturedImagesContainer.appendChild(imgElement);
    }

    captureButton.addEventListener('click', async () => {
        if (!stream || !video.srcObject || video.readyState < video.HAVE_METADATA) {
            showMessage("Camera chưa sẵn sàng.", 'error');
            return;
        }
        if (captureCount >= MAX_CAPTURES) {
            showMessage(`Đã chụp đủ ${MAX_CAPTURES} ảnh.`, 'info');
            return;
        }

        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = video.videoWidth;
        tempCanvas.height = video.videoHeight;
        const tempContext = tempCanvas.getContext('2d');
        tempContext.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);

        tempCanvas.toBlob((blob) => {
            if (blob) {
                capturedBlobs.push(blob);
                displayCapturedImage(blob);
                captureCount++;
                updateInstructionText();
                showMessage(`Đã chụp ảnh ${captureCount}/${MAX_CAPTURES}.`, 'info');
            } else {
                showMessage("Không thể tạo blob từ ảnh.", 'error');
            }
        }, 'image/jpeg', 0.9);
    });

    registerAllButton.addEventListener('click', async () => {
        const username = usernameInput.value.trim();
        if (!username) {
            showMessage("Vui lòng nhập tên người dùng.", 'error');
            return;
        }
        if (capturedBlobs.length === 0) {
            showMessage("Chưa có ảnh nào được chụp.", 'error');
            return;
        }

        showMessage(`Đang gửi ${capturedBlobs.length} ảnh cho người dùng '${username}'...`, 'info');
        registerAllButton.disabled = true;
        captureButton.disabled = true;

        const formData = new FormData();
        // Quan trọng: Tên field "image_files" phải khớp với tham số List[UploadFile] trong FastAPI
        capturedBlobs.forEach((blob, index) => {
            formData.append('image_files', blob, `${username}_capture_${index + 1}.jpg`);
        });

        try {
            // Đảm bảo URL API và tên endpoint đúng
            // Thay đổi URL nếu endpoint của bạn là /api/users/register_with_multiple_faces/
            const response = await fetch(`${FASTAPI_BASE_URL}/api/users/register_with_multiple_faces/?username=${encodeURIComponent(username)}`, {
                method: 'POST',
                body: formData,
                // Không cần 'Content-Type': 'multipart/form-data', browser tự đặt khi dùng FormData
            });

            const result = await response.json();

            if (response.ok) {
                let successMsg = `Đăng ký thành công cho: ${result.name}.`;
                if (result.encodings) {
                    successMsg += ` Số mã hóa đã lưu: ${result.encodings.length}.`;
                }
                // Thêm thông báo từ server nếu có (ví dụ về số ảnh xử lý)
                if(result.message) { // Nếu bạn thêm message vào UserResponse
                    successMsg += ` ${result.message}`;
                }
                showMessage(successMsg, 'success');
                usernameInput.value = '';
                capturedBlobs = []; // Xóa blobs đã gửi
                capturedImagesContainer.innerHTML = ''; // Xóa thumbnails
                captureCount = 0;
                updateInstructionText();
            } else {
                const errorDetail = result.detail || `Lỗi không xác định từ server (status ${response.status}).`;
                showMessage(`Lỗi đăng ký: ${errorDetail}`, 'error');
                console.error("API Error:", result);
            }
        } catch (err) {
            console.error("Lỗi khi gọi API đăng ký:", err);
            showMessage(`Lỗi kết nối hoặc xử lý: ${err.message}`, 'error');
        } finally {
            registerAllButton.disabled = false;
            // Nút captureButton vẫn nên disabled nếu đã chụp đủ, hoặc bật lại nếu muốn người dùng chụp lại
            updateInstructionText(); // Sẽ set lại trạng thái nút capture
        }
    });

    startCamera();
    updateInstructionText(); // Gọi ban đầu để set text và trạng thái nút
});