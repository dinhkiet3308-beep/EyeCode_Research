
set -e

IMAGE_NAME="ros_humble_image:latest"
CONTAINER_NAME="ros_humble"


SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"

echo "[*] Cấp quyền hiển thị đồ họa X11..."
xhost +local:root > /dev/null 2>&1

if [ -z "$(docker images -q ${IMAGE_NAME} 2> /dev/null)" ]; then
    echo "[*] Image '${IMAGE_NAME}' chưa tồn tại. Đang tự động build từ Dockerfile..."
    docker build -t "${IMAGE_NAME}" -f "${SCRIPT_DIR}/Dockerfile" "${WORKSPACE_DIR}"
fi

if [ "$(docker ps -a -q -f name=^/${CONTAINER_NAME}$)" ]; then
    if [ "$(docker ps -q -f name=^/${CONTAINER_NAME}$)" ]; then
        echo "[*] Container '${CONTAINER_NAME}' đang chạy. Đang kết nối vào..."
        docker exec -it "${CONTAINER_NAME}" bash
    else
        echo "[*] Container '${CONTAINER_NAME}' đang tạm dừng. Đang khởi động lại..."
        docker start "${CONTAINER_NAME}" > /dev/null
        docker exec -it "${CONTAINER_NAME}" bash
    fi
    exit 0
fi

echo "[*] Đang khởi tạo container mới '${CONTAINER_NAME}'..."
mkdir -p "${HOME}/.Xauthority"

docker run -it \
    --name "${CONTAINER_NAME}" \
    --net=host \
    --ipc=host \
    --privileged \
    --gpus all \
    --device /dev/dri \
    -e DISPLAY="${DISPLAY}" \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=all \
    -e __GLX_VENDOR_LIBRARY_NAME=nvidia \
    -e QT_X11_NO_MITSHM=1 \
    -e XAUTHORITY=/root/.Xauthority \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v "${HOME}/.Xauthority:/root/.Xauthority:rw" \
    -v "${WORKSPACE_DIR}:/root/ros2_orin_ws:rw" \
    -w /root/ros2_orin_ws \
    "${IMAGE_NAME}" \
    bash