#!/usr/bin/env bash
# One-time server setup for Amazon Linux 2023 (run as ec2-user with sudo): Docker, Compose, swap, git.
set -euo pipefail

sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"

# Compose v2 plugin (aarch64 or x86_64 is picked automatically).
sudo mkdir -p /usr/local/lib/docker/cli-plugins
arch="$(uname -m)"
sudo curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${arch}" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Compose v5 requires buildx 0.17 or later, which Amazon Linux's docker package does not ship.
case "$arch" in
  aarch64) buildx_arch=arm64 ;;
  x86_64) buildx_arch=amd64 ;;
  *) echo "Unsupported architecture: $arch" >&2; exit 1 ;;
esac
BUILDX_VERSION=v0.39.0
sudo curl -fsSL "https://github.com/docker/buildx/releases/download/${BUILDX_VERSION}/buildx-${BUILDX_VERSION}.linux-${buildx_arch}" \
  -o /usr/local/lib/docker/cli-plugins/docker-buildx
sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx

# 1 GiB swap protects the 1-2 GiB instance from out-of-memory kills during builds.
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 1G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "Done. Log out and back in so the docker group applies, then run: docker compose version"
