# AMD MI300X Droplet Bootstrap Commands

This is the exact bootstrap sequence used on the new droplet, with command
provenance notes.

## Executed Commands (in order)

1) SSH connectivity check

```bash
ssh -i ~/.ssh/id_ed25519_amd_mi300x -o StrictHostKeyChecking=accept-new root@129.212.188.229 "echo connected && uname -a"
```

- Source: standard SSH workflow (not AMD-specific doc)

2) Apply security updates (as prompted by cloud security banner)

```bash
ssh -i ~/.ssh/id_ed25519_amd_mi300x root@129.212.188.229 "export DEBIAN_FRONTEND=noninteractive && apt-get update && apt-get upgrade -y"
```

- Source: **official platform security notice shown at droplet creation**

3) Reboot after updates

```bash
ssh -i ~/.ssh/id_ed25519_amd_mi300x root@129.212.188.229 "reboot"
```

- Source: **official platform security notice shown at droplet creation**

4) Wait for host to come back

```bash
for i in $(seq 1 30); do
  if ssh -i ~/.ssh/id_ed25519_amd_mi300x -o ConnectTimeout=5 root@129.212.188.229 "echo rebooted && uptime" 2>/dev/null; then
    break
  fi
  sleep 5
done
```

- Source: operational convenience (not from AMD docs)

5) Post-reboot runtime and GPU validation

```bash
ssh -i ~/.ssh/id_ed25519_amd_mi300x root@129.212.188.229 "echo '=== system ===' && uname -a && echo '=== docker ===' && docker --version && echo '=== rocm-smi ===' && rocm-smi --showproductname --showmeminfo vram --showuse"
```

- Source: ROCm tooling best practice (`rocm-smi`) + standard environment checks

## Official Documentation Alignment

- **Security update + reboot**: directly from the provider's security notice displayed during droplet creation.
- **ROCm/vLLM image selection**: aligned with AMD quick-start image guidance (prebuilt ROCm+vLLM environment).
- **Project-specific commands** (next step): from this repo docs (`infra/devcloud.sh doctor`, `serve`, `benchmark`), not AMD platform docs.

## Next Commands (project bootstrap on droplet)

Run these next after cloning the repo on the droplet:

```bash
apt-get update && apt-get install -y python3.12-venv
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env
infra/devcloud.sh doctor
VLLM_ENABLE_LORA=0 VLLM_MODEL=Qwen/Qwen2.5-7B-Instruct infra/devcloud.sh serve dev
VLLM_URL=http://localhost:8001/v1 VLLM_BENCH_MODEL=Qwen/Qwen2.5-7B-Instruct infra/devcloud.sh benchmark dev
```

## Observed Runtime Notes

- `python3.12-venv` was required before virtualenv creation on this image.
- `doctor` now treats missing host `torch` as a warning when `rocm-smi` is
  healthy (common for Docker-first vLLM images).
- `serve` now falls back to Docker automatically if host `vllm` binary is not
  present.
- Current unresolved issue on this droplet: vLLM engine exits with
  `RuntimeError: No HIP GPUs are available` during serve startup, despite
  container torch showing GPU visibility. This needs AMD image/runtime guidance.

