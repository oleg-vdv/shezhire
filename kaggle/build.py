"""Pack the repo into a single Kaggle script that runs the eval on a free GPU.

    python kaggle/build.py && kaggle kernels push -p kaggle/build

The script installs Ollama, pulls the open-weight models and runs
eval/run_eval.py for each. Results land in /kaggle/working/out.tgz.
"""

import base64
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "kaggle" / "build"
MODELS = ["gemma4:e2b-it-qat", "gemma4:12b"]

RUN = r'''
import base64, io, os, subprocess, sys, time, zipfile, urllib.request
BLOB = "{blob}"
MODELS = {models}
W = "/kaggle/working/shezhire"
zipfile.ZipFile(io.BytesIO(base64.b64decode(BLOB))).extractall(W)
os.chdir(W)

def sh(cmd):
    print("$", cmd, flush=True)
    return subprocess.run(cmd, shell=True)

sh("apt-get -qq update >/dev/null 2>&1; apt-get -qq install -y zstd >/dev/null 2>&1")
sh("curl -fsSL https://ollama.com/install.sh | sh")
sh("pip -q install rapidfuzz httpx")
srv = subprocess.Popen(["ollama", "serve"], stdout=open("/kaggle/working/ollama.log", "w"), stderr=subprocess.STDOUT)
for _ in range(60):
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2); break
    except Exception:
        time.sleep(2)
sh("nvidia-smi --query-gpu=name,memory.total --format=csv")
for m in MODELS:
    if sh(f"ollama pull {{m}}").returncode != 0:
        print("pull failed", m); continue
    t0 = time.time()
    sh(f"SHEZHIRE_OLLAMA=http://127.0.0.1:11434 python -X utf8 eval/run_eval.py --model {{m}}")
    print(m, "took", round(time.time() - t0), "s", flush=True)
sh("tar czf /kaggle/working/out.tgz eval/runs eval/results-*.json")
srv.terminate()
'''


def main():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for sub in ["shezhire", "eval", "data/synthetic"]:
            for p in (ROOT / sub).rglob("*"):
                if p.is_file() and "__pycache__" not in p.parts and "runs" not in p.parts:
                    z.write(p, p.relative_to(ROOT).as_posix())
    blob = base64.b64encode(buf.getvalue()).decode()
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "run.py").write_text(RUN.format(blob=blob, models=json.dumps(MODELS)), encoding="utf-8")
    (BUILD / "kernel-metadata.json").write_text(json.dumps({
        "id": "ipgleg/shezhire-eval",
        "title": "shezhire-eval",
        "code_file": "run.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": True,
        "enable_internet": True,
        "machine_shape": "NvidiaTeslaT4",
    }, indent=1), encoding="utf-8")
    print(f"built {BUILD} ({len(blob) // 1024} KB payload)")


if __name__ == "__main__":
    main()
