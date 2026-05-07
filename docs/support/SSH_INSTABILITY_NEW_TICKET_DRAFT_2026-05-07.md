# DigitalOcean Support Draft — New Ticket (SSH Instability)

This draft is for a **separate ticket** from `#12151413`.

`#12151413` covers vLLM/ROCm serving correctness.
This ticket covers droplet SSH/network accessibility instability.

## Message to send

Hi team,

I'm opening a separate ticket from `#12151413` for **droplet SSH/network accessibility instability**. This is not about vLLM model behavior; it is about host reachability.

### Summary

On AMD MI300X droplets in `atl1`, the control plane reports the droplet as `active` with a valid public IP, but SSH intermittently fails with:

- `Connection refused`
- occasional timeouts

This blocks automation and normal remote workflows even when the VM appears healthy in API/UI.

### Scope (separate from #12151413)

- `#12151413` covers vLLM/ROCm serving correctness.
- This new ticket covers **infrastructure access instability** (SSH path / host reachability).

### Environment

- Size: `gpu-mi300x1-192gb-devcloud`
- Region: `atl1`
- Snapshot/image used: `appbid-final-20260506-150705` (`image id 227555448`)
- SSH auth: key-based root login (same key works when connection is available)

### Repro pattern

1. Create MI300X droplet from snapshot.
2. Wait for status `active` and public IPv4 assigned.
3. Attempt repeated SSH from local:
   - `ssh -i ~/.ssh/id_ed25519_amd_mi300x root@<public-ip> "echo ok"`
4. Observe alternating availability:
   - sometimes accepts briefly,
   - then returns `Connection refused` for sustained periods.

### What we verified on-host (when console/SSH was briefly available)

- `systemctl status ssh` showed service **active (running)**.
- Journal showed normal session opens/closes when reachable.
- No obvious sshd crash loop at the times checked.

This suggests the issue is likely not a persistent `sshd` config problem, and may be in host/network path health.

### Recovery attempts tried

- Repeated reconnect/retry loops (low-frequency and high-frequency).
- API `reboot`.
- API `power_cycle`.
- Fresh droplet recreation from same snapshot.
- Host key reset locally (`ssh-keygen -R <ip>`).

Behavior persisted across instances: control plane `active`, but SSH intermittently unavailable.

### Practical impact

- Blocks reliable automation (SCP/SSH orchestration).
- Causes benchmark/training jobs to fail to launch despite healthy control-plane status.
- Consumes paid GPU time during unreachable windows.

### Requested outcome

1. Investigate why droplets can be marked `active` while SSH is intermittently unreachable.
2. Provide recommended stable recovery workflow for this specific failure mode.
3. Provide stronger health signaling (for example, guest/SSH readiness) beyond control-plane `active`.
4. Confirm whether this is a known issue for `gpu-mi300x1-192gb-devcloud` in `atl1` and ETA/workaround.

Thanks.
