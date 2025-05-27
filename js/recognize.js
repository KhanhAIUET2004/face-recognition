// js/recognize.js
document.addEventListener('DOMContentLoaded', () => {
    const video = document.getElementById('videoElement');
    const canvas = document.getElementById('recognitionCanvas');
    const messageArea = document.getElementById('messageArea');
    const toggleButton = document.getElementById('toggleRecognitionButton');
    const context = canvas.getContext('2d');

    let stream;
    const processingInterval = 0;
    let recognitionLoopId = null; // ID cho setTimeout/setInterval
    let isRecognitionActive = false; // Trạng thái nhận dạng đang chạy hay không
    let isProcessingFrame = false; // Cờ để tránh xử lý chồng chéo

    async function startCamera() {
        try {
            stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
            video.srcObject = stream;
            video.onloadedmetadata = () => {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                showMessage("Camera sẵn sàng. Nhấn 'Bắt đầu Nhận dạng' để tiếp tục.", 'info');
                toggleButton.disabled = false; // Kích hoạt nút khi camera sẵn sàng
            };
            video.onplay = () => { // Có thể hữu ích để biết video thực sự đang chạ
                console.log("Video is playing");
            };
        } catch (err) {
            console.error("Lỗi truy cập camera:", err);
            showMessage(`Lỗi truy cập camera: ${err.message}`, 'error');
            toggleButton.disabled = true;
        }
    }

    function showMessage(message, type = 'info') {
        messageArea.textContent = message;
        messageArea.className = type; // success, error, info
    }

    function drawRecognitions(recognitionData) {
        context.clearRect(0, 0, canvas.width, canvas.height); // Xóa canvas trước khi vẽ mới

        if (recognitionData && recognitionData.recognized_faces) {
            recognitionData.recognized_faces.forEach(face => {
                if (face.box) {
                    // box: [top, right, bottom, left]
                    const [top, right, bottom, left] = face.box;
                    
                    const rectX = left;
                    const rectY = top;
                    const rectWidth = right - left;
                    const rectHeight = bottom - top;

                    context.strokeStyle = (face.name !== "Unknown" && !face.name.includes("Unknown (")) ? "lime" : "red";
                    context.lineWidth = 2;
                    context.strokeRect(rectX, rectY, rectWidth, rectHeight);

                    context.fillStyle = context.strokeStyle; // Cùng màu với hộp
                    context.font = "16px Arial";
                    let label = face.name;
                    if (face.distance !== null && face.distance !== undefined) {
                        label += ` (${face.distance.toFixed(2)})`;
                    }
                    // Đảm bảo text không vẽ ra ngoài canvas
                    const textX = rectX;
                    const textY = rectY > 20 ? rectY - 5 : rectY + rectHeight + 15;
                    context.fillText(label, textX, textY);
                }
            });
        }
    }
    
    async function processFrameAndRecognize() {
        if (isProcessingFrame || !isRecognitionActive || !video.srcObject || video.paused || video.ended || video.readyState < video.HAVE_METADATA) {
            return; // Không xử lý nếu đang xử lý, không active, hoặc video không sẵn sàng
        }
        isProcessingFrame = true;

        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = video.videoWidth;
        tempCanvas.height = video.videoHeight;
        const tempContext = tempCanvas.getContext('2d');
        tempContext.drawImage(video, 0, 0, tempCanvas.width, tempCanvas.height);

        tempCanvas.toBlob(async (blob) => {
            if (!blob) {
                console.error("Không thể tạo blob từ video frame.");
                isProcessingFrame = false;
                return;
            }

            const formData = new FormData();
            formData.append('image_file', blob, "recognition_frame.jpg");

            try {
                // Đảm bảo URL đúng với API endpoint trong main.py
                const response = await fetch(`${FASTAPI_BASE_URL}/api/recognize/`, {
                    method: 'POST',
                    body: formData,
                });
                const result = await response.json();

                if (response.ok) {
                    drawRecognitions(result);
                    if (result.message) { // Hiển thị message từ server (nếu có và khác với message mặc định)
                        // Chỉ hiển thị nếu message khác với thông báo mặc định "Đang nhận dạng..."
                        if (result.recognized_faces && result.recognized_faces.length > 0) {
                             // Có thể tạo message tổng hợp ở đây dựa trên result.recognized_faces
                            let names = result.recognized_faces.map(f => f.name).filter(name => name !== "Unknown" && !name.includes("Unknown (")).join(', ');
                            if(names) {
                                showMessage(`Phát hiện: ${names}. (${result.message})`, 'info');
                            } else {
                                showMessage(result.message, 'info');
                            }
                        } else {
                             showMessage(result.message, 'info'); // Ví dụ: "Không tìm thấy khuôn mặt nào..."
                        }
                    }
                } else {
                    const errorDetail = result.detail || `Lỗi server (${response.status})`;
                    showMessage(`Lỗi nhận dạng: ${errorDetail}`, 'error');
                    drawRecognitions(null); // Xóa các hình vẽ cũ nếu có lỗi
                    console.error("API Error:", result);
                }
            } catch (err) {
                console.error("Lỗi khi gọi API nhận dạng:", err);
                showMessage(`Lỗi kết nối hoặc xử lý: ${err.message}`, 'error');
                drawRecognitions(null);
            } finally {
                isProcessingFrame = false;
            }
        }, 'image/jpeg', 0.85); // Chất lượng JPEG, có thể điều chỉnh
    }

    function startRecognitionLoop() {
        if (recognitionLoopId) clearInterval(recognitionLoopId); // Xóa loop cũ nếu có
        
        // Gọi lần đầu ngay lập tức, sau đó theo interval
        processFrameAndRecognize(); 
        recognitionLoopId = setInterval(processFrameAndRecognize, processingInterval);
        showMessage("Đang nhận dạng...", 'info');
    }

    function stopRecognitionLoop() {
        if (recognitionLoopId) {
            clearInterval(recognitionLoopId);
            recognitionLoopId = null;
        }
        isProcessingFrame = false; // Reset cờ
        context.clearRect(0, 0, canvas.width, canvas.height); // Xóa canvas
        showMessage("Đã dừng nhận dạng. Nhấn 'Bắt đầu Nhận dạng' để tiếp tục.", 'info');
    }

    toggleButton.addEventListener('click', () => {
        isRecognitionActive = !isRecognitionActive;
        if (isRecognitionActive) {
            toggleButton.textContent = 'Dừng Nhận dạng';
            startRecognitionLoop();
        } else {
            toggleButton.textContent = 'Bắt đầu Nhận dạng';
            stopRecognitionLoop();
        }
    });

    // Bắt đầu camera khi trang tải
    startCamera();
    toggleButton.disabled = true; // Vô hiệu hóa nút cho đến khi camera sẵn sàng

    // Dọn dẹp khi rời trang (tùy chọn nhưng tốt)
    window.addEventListener('beforeunload', () => {
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
        }
        stopRecognitionLoop(); // Dừng vòng lặp
    });
});