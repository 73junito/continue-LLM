#!/usr/bin/env bash
set -euo pipefail

echo "== Setup GPU self-hosted runner prerequisites =="

if [ "$EUID" -ne 0 ]; then
  echo "This script requires sudo/root. Re-run as: sudo $0" >&2
  exit 1
fi

echo "Updating apt and installing prerequisites..."
apt-get update
apt-get install -y --no-install-recommends apt-transport-https ca-certificates curl gnupg lsb-release software-properties-common

echo "Installing Docker Engine..."
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
  add-apt-repository "deb [arch=$(dpkg --print-architecture)] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io
  echo "Docker installed. Adding current user to 'docker' group."
  usermod -aG docker "${SUDO_USER:-root}"
else
  echo "Docker already installed: $(docker --version)"
fi

echo "Installing NVIDIA Container Toolkit..."
distribution="$(. /etc/os-release; echo $ID$VERSION_ID)"
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/${distribution}/nvidia-docker.list | tee /etc/apt/sources.list.d/nvidia-docker.list
apt-get update
apt-get install -y nvidia-docker2

echo "Restarting docker to apply NVIDIA runtime..."
systemctl restart docker

echo "Verifying installation..."
if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found after install" >&2
  exit 1
fi

echo "docker version: $(docker --version)"

echo "Checking nvidia-smi on host (may be available inside container only)..."
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi output:"
  nvidia-smi || true
else
  echo "nvidia-smi not found on host. If drivers are missing, install the NVIDIA GPU driver on the host." >&2
fi

echo "Running a quick container test (requires network access to pull image)..."
if docker run --gpus all --rm nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
  echo "Container GPU access looks good (nvidia-smi ran inside container)."
else
  echo "Container test failed. Ensure NVIDIA drivers are installed on the host and the NVIDIA Container Toolkit is configured." >&2
  echo "You can test manually: docker run --gpus all --rm nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi" >&2
  exit 1
fi

echo "Setup complete. Start the GitHub Actions runner per the README and use label 'gpu' for this machine." 
