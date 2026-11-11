# Home DC — central infrastructure reference

This repository is the central, documentation-only view of the homelab. It does not provision or configure infrastructure. The diagram shows ownership and runtime relationships; tables below hold the authoritative addresses and operational detail.

## Logical overview

![Home DC architecture: repository ownership, Proxmox guests, Kubernetes clusters, and service dependencies](docs/architecture.svg)

## Repository ownership

| Repository | Owns | Does not own | Main entrypoints |
| --- | --- | --- | --- |
| [`home-dc-proxmox`](https://github.com/fabricesemti80/home-dc-proxmox) | Ansible configuration of the single PVE host `pve-00`: packages, storage, NFS, GPU passthrough, alerts/mail, and PVE API credentials | Guest VM/LXC creation; Kubernetes configuration; cluster HA/Ceph | `task plan`, `task apply`, `task reboot` |
| [`home-dc-terraform`](https://github.com/fabricesemti80/home-dc-terraform) | OpenTofu lifecycle of Proxmox guest VMs/LXCs; Cloudflare Tunnels and Zero Trust Access | PVE host configuration; Talos/Kubernetes configuration or bootstrap; local DNS | `task init`, `task plan`, `task apply`; per-root `proxmox:*`, `cloudflare:*` |
| [`home-dc-kubernetes`](https://github.com/fabricesemti80/home-dc-kubernetes) | Talos configuration; Kubernetes manifests and Argo CD GitOps for app-cluster and the separate physical infra-cluster | PVE host configuration; Proxmox guest lifecycle; OpenTofu roots/state | `task validate`, `task talos:app:bootstrap` (fresh app cluster only), `task infrastructure:verify` |
| [`homelab-terraform-unifi`](https://github.com/fabricesemti80/homelab-terraform-unifi) | Separate UniFi/network configuration | Current local DNS authority | Its own Taskfile; check that repository before network changes |
| `home-dc` (this repository) | Central current-state documentation and diagram | Any infrastructure changes | Read this guide and the linked owner repository before acting |
| [`home-kestra`](https://github.com/fabricesemti80/home-kestra) | Separate Kestra maintenance workflows | Current `pve-00` and Kubernetes topology | Inspect its own flow definitions before relying on them |

`home-dc-kubernetes` is the GitOps source of truth. The single Argo CD installation runs on `app-cluster`, watches the repository's `main` branch, and reconciles workloads to both clusters. The infra-cluster has no separate Argo CD installation. Changes to application state belong in that repository, not in Ansible or OpenTofu.

## Runtime topology

- **Proxmox:** one standalone Proxmox VE 9 host, `pve-00`. It is not a Proxmox cluster. There is no Ceph, PVE HA, or configured scheduled backup job. Ansible configures the host; OpenTofu creates its guests.
- **App cluster:** Talos VMs on `pve-00`: controller `k8s-ctrl-01`, workers `k8s-wrkr-01-gpu`, `k8s-wrkr-02`, `k8s-wrkr-03`. Live `kubectl` showed all four Ready. The three workers share one Proxmox host.
- **Infra cluster:** unchanged physical Talos nodes `infra-cp-01` and `infra-wk-01`; both were Ready in live `kubectl`. The app-cluster Argo CD hub manages it; no Argo CD installation exists there. Do not reprovision it as part of an app-cluster rebuild.
- **Guest inventory:** OpenTofu declares PBS-target LXC 4020, controller VM 4090, and worker VMs 4095–4097. PBS is a configured LXC setup target; service readiness and any manually initiated backups were not verified. There is no configured scheduled Proxmox/PBS backup job. The Kubernetes Backrest backup flows below are separate.

## Physical hardware

The PVE host is a Dell Precision 7820 Tower (board `0G7W4R`, revision `A00`) on UEFI 5.14 firmware with Secure Boot disabled and TPM 2.0 present. It carries two Intel Xeon Gold 6152 processors (22 cores / 44 threads each, 88 logical CPUs) and 128 GB of memory as 8 × 16 GB Micron `18ASF2G72PDZ-2G6D1` at 2666 MT/s, leaving four DIMM sockets empty. Networking is the onboard Intel I219-LM on `nic0`. The full inventory — serials, partition layouts, PCIe link widths, boot path, and free expansion points — is recorded in [`home-dc-proxmox/docs/hardware.md`](https://github.com/fabricesemti80/home-dc-proxmox/blob/main/docs/hardware.md).

| Device | Model | Capacity | Interface | Role |
|---|---|---:|---|---|
| NVMe | Samsung `MZVKW1T0HMLH-000L7` | 953.9 GiB | PCIe x4 @ 8 GT/s via Intel VMD | Boot device and sole member of ZFS pool `rpool` |
| HDD | HGST `HDS724040ALE640` | 3.6 TiB (4 TB) | SATA 6 Gbps, 512e | Sole member of ZFS pool `slow` |
| Optical | PLDS `DVD+/-RW DU-8A5LH` | 1024 MiB | SATA 1.5 Gbps | Optical drive |
| GPU | Quadro P2000 | — | PCIe x16 link, 8 GT/s capable (2.5 GT/s when last sampled, unloaded) | Passed through to a guest via `vfio-pci` |
| GPU | GeForce GT 710 | — | PCIe x1 @ 5 GT/s | Host console, firmware primary display |

Both ZFS pools are single-disk vdevs with `ashift=12` and no redundancy, and the host boots from a single EFI System Partition on the NVMe. Six of the eight AHCI SATA ports and three PCIe root ports are free, so a second 4 TB HDD and a second NVMe are both physically possible; neither is installed.

## Addressing and network

All Proxmox guest addresses below are configured on **VLAN 40**, `10.0.40.0/24`. Guest NICs are untagged on `vmbr0`; the PVE uplink must carry VLAN 40 as its native/access network. The gateway is `10.0.40.1`.

| Endpoint | VMID | Address | Notes |
| --- | ---: | --- | --- |
| NAS | — | `10.0.40.2` | NFS; includes `/media` and Proxmox template/ISO/backup exports |
| PBS LXC | 4020 | `10.0.40.20/24` | Debian 13 target; post-deployment setup uses the NAS PBS export |
| Talos controller `k8s-ctrl-01` | 4090 | `10.0.40.90` | Proxmox `local-nvme` |
| Talos worker `k8s-wrkr-01-gpu` | 4095 | `10.0.40.95` | P2000 passthrough; Proxmox `local-hdd` |
| Talos worker `k8s-wrkr-02` | 4096 | `10.0.40.96` | Proxmox `local-hdd` |
| Talos worker `k8s-wrkr-03` | 4097 | `10.0.40.97` | Proxmox `local-hdd` |
| App-cluster API VIP | — | `10.0.40.101` | Talos/Kubernetes API endpoint |
| App-cluster internal gateway | — | `10.0.40.102` | Internal route target documented in the Kubernetes repo |

The PVE host is accessed through the SSH alias `pve-00`; its host address is not declared in the reviewed inventory, so it is intentionally not repeated here. VLAN 40 clients can reach guest addresses directly. Access from other VLANs requires working routing and firewall rules in the home network; these repositories do not configure those network paths.

Kubernetes uses `10.42.0.0/16` for pod addresses and `10.43.0.0/16` for service addresses. These are overlay/service networks, not VLANs.

## Storage and data durability

| Storage | Use |
| --- | --- |
| `local` | Default file storage; current OpenTofu Debian template download only, not guest disks |
| `local-nvme` | Controller system disk and LXC root filesystems |
| `local-hdd` | Worker system disks and dedicated worker data disks |
| `nfs-proxmox-template` | Registered NAS export for container templates; current OpenTofu downloads its Debian template to `local` |
| `nfs-proxmox-iso` | Boot ISOs and imported VM/cloud-init images |
| `nfs-proxmox-backup` | VZDump archive content only; no scheduled job is configured |
| `10.0.40.2:/media` | Shared media-library NFS claim; Immich originals live under `/media/immich` |
| `10.0.40.2:/k8s-backup` | Backrest backup target on both clusters, mounted inside Backrest at `/backups` |

App-cluster persistent application config/state, caches and queues use the default `longhorn` StorageClass (`ReadWriteOnce`, `Retain`), configured with **three replicas** across the workers. NFS is reserved for the shared media library (`10.0.40.2:/media`) and the Backrest target (`10.0.40.2:/k8s-backup`, mounted at `/backups`). Immich originals remain in the shared media tree, not on a Longhorn database volume. The physical infra-cluster is unchanged: its application state uses node-local `hostPath`/`local-path` storage (including static `technitium-local` volumes), plus the same NFS backup target.

Three worker replicas do not provide host-level redundancy: all app workers run on `pve-00`. Replication is not a backup. Live inspection found 16 Longhorn volumes configured for three replicas: 15 healthy; one retained `immich-postgres-data-longhorn` volume was detached with robustness `unknown`. This includes retained rollback data; not every detached volume represents a mounted workload. Do not interpret the StorageClass replica setting as proof that every retained volume is healthy.

The Proxmox host's storage pools are single-host storage, not shared cluster storage. Both ZFS pools — `rpool` behind `local-nvme` and `slow` behind `local-hdd` — are single-disk vdevs with no redundancy, and the host boots from one EFI System Partition on the NVMe, so losing that disk ends the installation regardless of pool contents. Mirroring a second disk into either pool is documented but not performed; see the [hardware inventory](https://github.com/fabricesemti80/home-dc-proxmox/blob/main/docs/hardware.md). PBS setup is a separate Terraform-managed LXC workflow; its live service/datastore status is unverified.

## DNS, ingress, and external access

- **Internal DNS:** web apps use `<app>.krapulax.home` HTTPRoutes attached to their cluster's `envoy-internal`. Each cluster's Technitium ExternalDNS watches internal routes for that gateway and zone, then updates Technitium at `10.0.40.53` over RFC2136. App routes resolve through `kubernetes.krapulax.home` (`10.0.40.102`); infra routes use the infra gateway (`10.0.40.106`). Live routes were accepted and resolved on both clusters.
- **Public routes are opt-in, not universal:** explicit `krapulax.dev` HTTPRoutes go through the appropriate Cloudflare Tunnel to that cluster's `envoy-external`. Several current services do have public routes; internal routing alone does not publish an app. No inbound public port forwarding is required by this design.
- **Ownership:** `home-dc-terraform/cloudflare/` provisions tunnels and Access applications/policies and publishes tunnel credentials to Doppler. Kubernetes GitOps owns cloudflared configuration, HTTPRoutes and ExternalDNS. Access policy is application-specific.
- **Cloudflare DNS caveat:** the app-cluster Cloudflare ExternalDNS deployment is running, but its Argo CD sync remains manually gated because publishing private gateway addresses would be wrong. Verify targets before enabling sync. UniFi DNS records are legacy, not the current internal DNS authority.
- The app- and infra-cluster operators use Doppler project `home-dc-kubernetes` with configs `apps` and `infra`, respectively. The Proxmox Ansible and OpenTofu consumers use projects `home-dc-proxmox/prd` and `home-dc-terraform/prd`; the latter publishes Cloudflare tunnel values referenced by Kubernetes. The Doppler operator runs on both clusters. Live Doppler resources reported ready synchronization; values were not inspected. SOPS/age also protects Git-stored bootstrap secrets; local kubeconfigs, Talos identity material, and private keys remain ignored/local-only.

## Secrets and state

This repository holds no secrets or environment variables. Each owner repository keeps the authoritative inventory of its secrets, their Doppler sources and their consumers:

| Repository | Inventory |
| --- | --- |
| `home-dc-proxmox` | [`docs/secrets-and-env-vars.md`](https://github.com/fabricesemti80/home-dc-proxmox/blob/main/docs/secrets-and-env-vars.md) |
| `home-dc-terraform` | [`docs/secrets-and-env-vars.md`](https://github.com/fabricesemti80/home-dc-terraform/blob/main/docs/secrets-and-env-vars.md) |
| `home-dc-kubernetes` | [`docs/secrets-and-env-vars.md`](https://github.com/fabricesemti80/home-dc-kubernetes/blob/main/docs/secrets-and-env-vars.md) |

- The Proxmox Ansible and OpenTofu consumers use separate projects `home-dc-proxmox/prd` and `home-dc-terraform/prd`; the latter publishes Cloudflare tunnel values referenced by Kubernetes. Kubernetes uses project `home-dc-kubernetes`, config `apps` on app-cluster and `infra` on infra-cluster. Its Doppler operator runs on both clusters. Live resources reported ready synchronization; values were not inspected. SOPS/age also protects Git-stored bootstrap secrets; local kubeconfigs, Talos identity material, and private keys remain ignored/local-only.
- OpenTofu states and saved plans are local, Git-ignored files in their owning roots. `home-dc-terraform/state-archive/` contains historical snapshots only; active roots do not load that archive. Never copy or apply an archived state as the current state.

## Backups

Each cluster runs its own Backrest instance. Both mount NAS export `10.0.40.2:/k8s-backup` at `/backups`; this is a backup destination, not application-state storage. App protection jobs stage supported application backups for Backrest. Native PostgreSQL export jobs cover Immich on app-cluster and LiteLLM on infra-cluster; both ran successfully on 2026-11-11 and are scheduled every six hours. App-cluster Backrest also mounts `/media/immich` read-only at `/photos` for the separate Immich originals backup.

Running Backrest pods, mounted targets and successful database export jobs verify the configured flow, **not** a complete recoverability guarantee. No NAS snapshot contents, Backrest restore, or end-to-end Immich restore was checked for this documentation change; the Immich database export and originals are separate backup sources. Follow the owner repository's [Backrest operations guide](https://github.com/fabricesemti80/home-dc-kubernetes/blob/main/docs/operations/backrest.md) before relying on a recovery.

## Deployment workflow

1. **PVE host:** From `home-dc-proxmox`, review `task plan`; run `task apply` only for reviewed host changes. `task reboot` is separate and operator-initiated.
2. **Guest infrastructure:** From `home-dc-terraform`, use `task nodes-plan` and review `tfplan-nodes` before `task nodes-apply`. PBS uses `task pbs-plan` / `task pbs-apply`; those tasks create the Debian LXC target, not a configured PBS server. Cloudflare has its own `cloudflare:tf:plan` and `cloudflare:tf:apply` tasks.
3. **Fresh app-cluster bootstrap only:** From `home-dc-kubernetes`, `task talos:app:bootstrap` is a one-time fresh-cluster workflow. Do not rerun it against an existing etcd cluster. Follow the repo's installation guide for Cilium, platform bootstrap, and verification.
4. **Routine workloads:** Change Kubernetes manifests in `home-dc-kubernetes`, review/merge to `main`, and let Argo CD reconcile. Do not use Terraform or Ansible to deploy applications.

Root Terraform tasks `task init`, `task plan`, and `task apply` run both active roots; namespaced `proxmox:*` and `cloudflare:*` tasks target one root. Run `task --list` in each repository for the current full task surface.

## Operational constraints

- One PVE host means no hypervisor HA or host-level failover. Talos' single-controller app cluster also has no control-plane redundancy.
- Infra-cluster node-local state does not fail over with a node. App-cluster Longhorn tolerates eligible worker-volume failures, but not loss of its single Proxmox host; independent backups and tested restores remain necessary.
- The NFS backup export is configured, but this repository does not establish a Proxmox backup schedule. The PBS LXC target does not provide backups until PBS and its datastore are installed and verified.
- Static IPs describe the declared configuration. They do not prove a guest is powered on, reachable, or healthy.
- Historical cluster, Ceph, and service-host configurations are not active topology. Use the current owner repositories above, not stale exports or archived state.
