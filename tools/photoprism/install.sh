apt update && apt install -y wget curl ffmpeg exiftool libvips-tools inotify-tools
mkdir -p /opt/photoprism
cd /opt/photoprism
wget -c https://dl.photoprism.app/pkg/linux/amd64.tar.gz -O - | tar -xz
ln -sf /opt/photoprism/bin/photoprism /usr/local/bin/photoprism
