# Home DC — central infrastructure reference

This repository is the central, documentation-only view of the homelab. It does not provision or configure infrastructure. The diagram shows ownership and runtime relationships; tables below hold the authoritative addresses and operational detail.

[Open the current architecture diagram](docs/architecture.html)

## Repository ownership

| Repository | Owns | Does not own | Main entrypoints |
| --- | --- | --- | --- |
| [`home-dc-proxmox`](https://github.com/fabricesemti80/home-dc-proxmox) | Ansible configuration of the single PVE host `pve-00`: packages, storage, NFS, GPU passthrough, alerts/mail, and PVE API credentials | Guest VM/LXC creation; Kubernetes configuration; cluster HA/Ceph | `task plan`, `task apply`, `task reboot` |
| [`home-dc-terraform`](https://github.com/fabricesemti80/home-dc-terraform) | OpenTofu lifecycle of Proxmox guest VMs/LXCs; Cloudflare Tunnels and Zero Trust Access | PVE host configuration; Talos/Kubernetes configuration or bootstrap; local DNS | `task tf:init`, `task tf:plan`, `task tf:apply`; per-root `proxmox:tf:*`, `cloudflare:tf:*` |
| [`home-dc-kubernetes`](https://github.com/fabricesemti80/home-dc-kubernetes) | Talos configuration and app-cluster bootstrap; the separate physical Talos `infra-cluster`; Kubernetes manifests and Argo CD GitOps for both clusters | PVE host configuration; Proxmox guest lifecycle; OpenTofu roots/state | `task validate`, `task talos:app:bootstrap` (fresh app cluster only), `task infrastructure:verify` |
| [`homelab-terraform-unifi`](../homelab-terraform-unifi/) | Separate UniFi/network configuration | Current local DNS authority | Its own Taskfile; check that repository before network changes |
| `home-dc` (this repository) | Central current-state documentation and diagram | Any infrastructure changes | Read this guide and the linked owner repository before acting |

`home-dc-kubernetes` is the GitOps source of truth. Argo CD on `app-cluster` watches its `main` branch and manages workloads on both Kubernetes clusters. Changes to application state belong in that repository, not in Ansible or OpenTofu.

## Runtime topology

- **Proxmox:** one standalone Proxmox VE 9 host, `pve-00`. It is not a Proxmox cluster. There is no Ceph, PVE HA, or configured scheduled backup job. Ansible configures the host; OpenTofu creates its guests.
- **App cluster:** Talos VMs on `pve-00`, one controller and three workers. Argo CD is the hub and manages both the app cluster and the separate infra cluster.
- **Infra cluster:** two physical Talos nodes, independent of Proxmox guest rebuilds. It remains managed by the app-cluster Argo CD hub; do not reprovision it as part of an app-cluster rebuild.
- **Guest inventory:** OpenTofu declares smoke LXC 4019, PBS-target LXC 4020, controller VM 4090, and worker VMs 4095–4097. The configured inventory is not a health check; verify actual guest state in Proxmox and Kubernetes before operational changes.
- **PBS status:** LXC 4020 is configured as a Debian container target. The OpenTofu root does not run the Community Scripts installer, install PBS, or configure its datastore. Do not treat this LXC as a functioning backup server until those steps are completed and verified.

## Addressing and network

All Proxmox guest addresses below are configured on **VLAN 40**, `10.0.40.0/24`. Guest NICs are untagged on `vmbr0`; the PVE uplink must carry VLAN 40 as its native/access network. The gateway is `10.0.40.1`.

| Endpoint | VMID | Address | Notes |
| --- | ---: | --- | --- |
| NAS | — | `10.0.40.2` | NFS; includes `/media` and Proxmox template/ISO/backup exports |
| Smoke LXC | 4019 | `10.0.40.19/24` | Debian test container |
| PBS-target LXC | 4020 | `10.0.40.20/24` | Debian target only; PBS installation is separate |
| Technitium DNS | — | `10.0.40.53` | Internal `krapulax.home` zone |
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
| `10.0.40.2:/media` | Kubernetes media-library NFS claim |

Each worker has a dedicated data disk intended for the Talos `local-path` user volume at `/var/mnt/local-path-provisioner`. App-cluster config/state PVCs use the node-local `local-path` StorageClass (`ReadWriteOnce`, `Retain`). These volumes are not replicated and do not fail over with a worker. No verified off-host backup/restore process for these PVCs is recorded here; confirm one before treating the data as protected.

The Proxmox host's storage pools are single-host storage, not shared cluster storage. A single-disk pool has no redundancy. PBS installation and backup-job configuration are separate from the current LXC target.

## DNS, ingress, and external access

- **Local DNS:** Technitium serves `krapulax.home` at `10.0.40.53`. `kubernetes.krapulax.home` points at the internal gateway `10.0.40.102`. UniFi DNS records in the separate UniFi repository are legacy; they are not the current local-DNS source of truth.
- **Public services:** Cloudflare is the public edge for `krapulax.dev`. The Kubernetes deployment uses the `kubernetes-apps` and `kubernetes-infra` Cloudflare Tunnels to reach the app- and infra-cluster Envoy gateways. Cloudflare Access policies protect configured applications, with a specific webhook bypass for Argo CD.
- **Ownership:** `home-dc-terraform/cloudflare/` provisions tunnels and Access applications/policies and publishes tunnel credentials to Doppler; it does not define direct Cloudflare DNS-record resources. Kubernetes `ExternalDNS` and GitOps manifests declare application records. The app-cluster Cloudflare DNS application is manually gated because its chart may publish private gateway IPs; verify targets before enabling sync. Technitium is the internal DNS authority.
- **Ingress is tunneled:** The documented design does not require opening inbound public ports on the home network.

## Secrets and state

- The Proxmox Ansible role stores its API-token secret in the 1Password `iac` vault. OpenTofu reads the token through the local `scripts/tofu.sh` wrapper; no credential values belong in Git.
- The Cloudflare OpenTofu tasks use Doppler project/config `home-dc-kubernetes/dev` for provider inputs. Tunnel credentials are written to the `apps` and `infra` configs.
- Kubernetes uses SOPS/age for encrypted Git-stored secrets and the Doppler operator for runtime secret synchronization. Local kubeconfigs, Talos identity material, and private keys remain ignored/local-only.
- OpenTofu states and saved plans are local, Git-ignored files in their owning roots. `home-dc-terraform/state-archive/` contains historical snapshots only; active roots do not load that archive. Never copy or apply an archived state as the current state.

## Deployment workflow

1. **PVE host:** From `home-dc-proxmox`, review `task plan`; run `task apply` only for reviewed host changes. `task reboot` is separate and operator-initiated.
2. **Guest infrastructure:** From `home-dc-terraform`, use `task nodes-plan` and review `tfplan-nodes` before `task nodes-apply`. PBS uses `task pbs-plan` / `task pbs-apply`; those tasks create the Debian LXC target, not a configured PBS server. Cloudflare has its own `cloudflare:tf:plan` and `cloudflare:tf:apply` tasks.
3. **Fresh app-cluster bootstrap only:** From `home-dc-kubernetes`, `task talos:app:bootstrap` is a one-time fresh-cluster workflow. Do not rerun it against an existing etcd cluster. Follow the repo's installation guide for Cilium, platform bootstrap, and verification.
4. **Routine workloads:** Change Kubernetes manifests in `home-dc-kubernetes`, review/merge to `main`, and let Argo CD reconcile. Do not use Terraform or Ansible to deploy applications.

Root Terraform tasks `task tf:init/plan/apply` run both active roots; namespaced `proxmox:tf:*` and `cloudflare:tf:*` tasks target one root. Run `task --list` in each repository for the current full task surface.

## Operational constraints

- One PVE host means no hypervisor HA or host-level failover. Talos' single-controller app cluster also has no control-plane redundancy.
- The PVE host and worker data disks are local. Local-path PVCs are node-local; loss of the worker or disk requires restore from an independent backup.
- The NFS backup export is configured, but this repository does not establish a Proxmox backup schedule. The PBS LXC target does not provide backups until PBS and its datastore are installed and verified.
- Static IPs describe the declared configuration. They do not prove a guest is powered on, reachable, or healthy.
- Historical cluster, Ceph, and service-host configurations are not active topology. Use the current owner repositories above, not stale exports or archived state.
