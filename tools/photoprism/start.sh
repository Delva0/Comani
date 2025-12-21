export PHOTOPRISM_AUTH_MODE="public"
export PHOTOPRISM_ORIGINALS_PATH="/workspace/ComfyUI/output"
export PHOTOPRISM_STORAGE_PATH="/workspace/photoprism/storage"
export PHOTOPRISM_IMPORT_PATH="/workspace/ComfyUI/import"
export PHOTOPRISM_HTTP_PORT=8081
export PHOTOPRISM_HTTP_HOST="0.0.0.0"
export PHOTOPRISM_DATABASE_DRIVER="sqlite"

export PHOTOPRISM_DISABLE_TENSORFLOW="true"
export PHOTOPRISM_DISABLE_FACES="true"
export PHOTOPRISM_DISABLE_CLASSIFICATION="true"
export PHOTOPRISM_DETECT_NS="-1"

export PHOTOPRISM_DISABLE_VIDEOS="false"
export PHOTOPRISM_FFMPEG_ENCODER="nvidia"

photoprism start &

sleep 5

echo "Starting folder watch (Images & Videos)..."

photoprism index


shopt -s nocasematch
last_run=0
debounce_delay=3

inotifywait -m -r -e close_write --format '%w%f' "$PHOTOPRISM_ORIGINALS_PATH" | while read -r file; do
    if [[ "$file" =~ \.(png|jpg|jpeg|webp|gif|mp4|mov|avi|mkv|webm|flv)$ ]]; then
        current_time=$(date +%s)

        # 检查距离上次运行是否超过了延迟时间
        if (( current_time - last_run > debounce_delay )); then
            (
              # 使用 flock 防止多个索引进程同时运行
              flock -n 9 || exit 1
              echo "[$(date +'%H:%M:%S')] Detected change in: $file. Triggering index..."
              photoprism index
            ) 9>/var/lock/photoprism_indexing.lock

            last_run=$(date +%s)
        fi
    fi
done
