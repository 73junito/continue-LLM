
# GPU Docker (NVIDIA) — Setup and Usage

This folder provides a minimal scaffold to run Continue inside a CUDA-enabled Docker container using the NVIDIA Container Toolkit.

Prerequisites

- Linux host with NVIDIA drivers and the NVIDIA Container Toolkit (nvidia-docker2 / nvidia-container-toolkit), or Windows with WSL2 and NVIDIA drivers.
- Docker Engine and Docker Compose v2+.

Files added

- `Dockerfile.gpu` — base image `nvidia/cuda:12.2.0-cudnn8-runtime-ubuntu22.04`, installs Python and PyTorch (CUDA 12.2 wheels).
- `docker-compose.gpu.yml` — service definition to build and run the GPU container and execute the benchmark.
- `scripts/run-gpu.sh` — helper script to start the GPU compose stack.
- `examples/benchmark_gpu.py` — small PyTorch script that verifies CUDA and runs a tiny matmul benchmark.
- `envs/conda-gpu.yml` — Conda environment manifest for local GPU development.

Build and run (recommended)

Create and activate the Conda GPU environment locally (optional but useful for running tests outside the container):

```bash
conda env create -f envs/conda-gpu.yml
conda activate continue-gpu
```

Build and run with Docker Compose (recommended; runs the benchmark by default):

```bash
docker compose -f docker-compose.gpu.yml up --build
```

Or build and run directly with Docker:

```bash
docker build -t continue-llm-gpu -f Dockerfile.gpu .
docker run --gpus all -it --rm -v "$(pwd)":/workspace -w /workspace continue-llm-gpu bash -c "python3 examples/benchmark_gpu.py"
```

Quick test (inside Conda env or container)

```bash
python examples/benchmark_gpu.py
```

It should print something like:

```text
torch.__version__: 2.x.x
CUDA available: True
CUDA device count: 1
10 matmuls elapsed: 0.1234s, avg per matmul: 0.0123s
```

Notes

- If your environment uses WSL2 on Windows, ensure the NVIDIA driver for WSL is installed and Docker Desktop is configured to enable WSL integration.
- The `pip` install in the Dockerfile pulls PyTorch wheels from the official PyTorch index for CUDA 12.2. If you prefer a different PyTorch channel or pinned versions, update the `pip` line in `Dockerfile.gpu`.
- For CI or cloud GPU runners, modify `docker-compose.gpu.yml` as needed or push the built image to your registry and run on the target infrastructure.

Troubleshooting

- If the container reports `CUDA available: False`, verify host drivers and that Docker has GPU access by running:

```bash
docker run --gpus all --rm nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

## Self-Hosted Runner

If you want GitHub Actions to run the GPU benchmark, register a self-hosted runner on a GPU machine and label it `gpu`.

Register the runner on the GPU machine:

```bash
# On the GPU machine
mkdir actions-runner && cd actions-runner
curl -o actions-runner-linux-x64.tar.gz -L https://github.com/actions/runner/releases/download/v2.x.x/actions-runner-linux-x64.tar.gz
tar xzf ./actions-runner-linux-x64.tar.gz
./config.sh --url https://github.com/73junito/continue-LLM --token <YOUR_TOKEN>
```

Label the runner (add a GPU label):

```bash
# Add a GPU label
./config.sh --url https://github.com/73junito/continue-LLM --token <YOUR_TOKEN> --labels gpu
```

Start the runner:

```bash
./run.sh
```

Notes for GitHub Actions:

- Use `runs-on: [self-hosted, gpu]` in your workflow to target this runner (the included `gpu-benchmark.yml` already does this).
- Ensure Docker and the NVIDIA Container Toolkit are installed and configured on the runner.
- The workflow builds `Dockerfile.gpu` and runs the benchmark; the runner must have sufficient permissions to run Docker.

### Setup GPU Runner

Before running the workflow, you can prepare a new Ubuntu runner with:

```bash
sudo bash scripts/setup-runner.sh
```

This installs Docker, NVIDIA Container Toolkit, and adds your user to the `docker` group. After running, the runner is ready for `gpu-benchmark.yml`.


