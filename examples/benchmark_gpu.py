import time
try:
    import torch
except Exception as e:
    print("PyTorch not installed or failed to import:", e)
    raise

def main():
    print("torch.__version__:", torch.__version__)
    cuda_avail = torch.cuda.is_available()
    print("CUDA available:", cuda_avail)
    print("CUDA device count:", torch.cuda.device_count())
    if not cuda_avail:
        return
    dev = torch.device('cuda')
    # small benchmark
    a = torch.randn(1024, 1024, device=dev)
    b = torch.randn(1024, 1024, device=dev)
    # warmup
    for _ in range(5):
        _ = torch.mm(a, b)
    torch.cuda.synchronize()
    start = time.time()
    for _ in range(10):
        _ = torch.mm(a, b)
    torch.cuda.synchronize()
    elapsed = time.time() - start
    print(f"10 matmuls elapsed: {elapsed:.4f}s, avg per matmul: {elapsed/10:.4f}s")

if __name__ == '__main__':
    main()
