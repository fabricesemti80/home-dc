# Home DC Overview

High-level map of the homelab. Three repos own everything:

| Repo | Role |
|------|------|
| [`home-dc-proxmox`](../home-dc-proxmox) | Bare-metal Proxmox VE + Ceph cluster |
| [`home-dc-kubernetes`](../home-dc-kubernetes) | Talos Kubernetes cluster and GitOps workloads |
| [`home-dc-docker`](../home-dc-docker) | Host-level Docker Compose services on `morpheus` |

<!-- ponytail: intentionally excludes secret values, token strings, and password hashes; see each repo's local/runtime files -->

---

## Architecture Diagram

```mermaid
flowchart TB
    %% class definitions for cloud-style coloring
    classDef internet fill:#e1f5fe,stroke:#01579b,stroke-width:2px,color:#01579b;
    classDef cloudflare fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#e65100;
    classDef network fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px,color:#6a1b9a;
    classDef proxmox fill:#ffebee,stroke:#b71c1c,stroke-width:2px,color:#b71c1c;
    classDef k8s fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#1565c0;
    classDef docker fill:#e0f7fa,stroke:#00838f,stroke-width:2px,color:#00838f;
    classDef storage fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#2e7d32;
    classDef apps fill:#fff8e1,stroke:#f57f17,stroke-width:2px,color:#f57f17;

    internet([fa:fa-globe Internet]):::internet
    cf([fa:fa-cloud Cloudflare<br/>Zero Trust / DNS / Tunnels]):::cloudflare
    unifi([fa:fa-wifi UniFi DNS<br/>krapulax.home]):::network
    k8s_gw([fa:fa-server k8s-gateway<br/>10.0.40.153]):::network

    subgraph docker["🐳 Docker Host — morpheus (10.0.40.19)"]
        traefik([fa:fa-random Traefik]):::docker
        docker_apps([fa:fa-cubes Arcane / Portainer / Kestra<br/>Uptime Kuma / Whoami / Beszel]):::docker
    end

    subgraph k8s["☸ Kubernetes — Talos Cluster"]
        cp([fa:fa-server k8s-ctrl-01/02/03<br/>10.0.40.90–92]):::k8s
        argo([fa:fa-code-branch Argo CD]):::k8s
        cni([fa:fa-project-diagram Cilium]):::k8s
        dns([fa:fa-globe CoreDNS]):::k8s
        ext_dns([fa:fa-sync external-dns]):::k8s
        envoy_int([fa:fa-door-open envoy-internal<br/>10.0.40.102]):::network
        envoy_ext([fa:fa-door-open envoy-external<br/>10.0.40.103]):::network

        subgraph apps["🚀 Workloads"]
            media([fa:fa-film Media Stack]):::apps
            prod([fa:fa-briefcase Productivity]):::apps
            mon([fa:fa-chart-line Monitoring]):::apps
            web([fa:fa-window-maximize Web]):::apps
        end
    end

    subgraph storage["🗄 Storage"]
        ceph([fa:fa-database Ceph Cluster<br/>10.0.70.0/24]):::storage
        cephfs([fa:fa-folder-open CephFS PVCs]):::storage
        nfs([fa:fa-hdd NFS 10.0.40.2:/media<br/>media-library-pvc]):::storage
    end

    subgraph proxmox["🖥 Proxmox VE Cluster"]
        pve([fa:fa-server pve-0 / pve-1 / pve-2<br/>VIP 10.0.40.15]):::proxmox
    end

    internet --> cf
    cf -->|trinity tunnel| traefik
    cf -->|kubernetes tunnel| envoy_ext
    cf -->|public DNS| k8s_gw
    cf -->|Access policies| envoy_ext

    unifi -->|internal DNS| k8s_gw
    k8s_gw --> envoy_int
    envoy_int --> apps
    envoy_ext --> apps
    traefik --> docker_apps

    argo --> apps
    cni --> apps
    dns --> apps
    ext_dns -->|writes records| cf

    apps --> cephfs
    media --> nfs
    cephfs --> ceph
    pve -->|hosts| ceph
    pve -->|hosts VMs| k8s
    pve -->|hosts VM| docker
```

---

## Network Layout

| Network | CIDR | Purpose |
|---------|------|---------|
| Management / VM | `10.0.40.0/24` | Proxmox UI, VMs, Kubernetes nodes, Docker host, NFS |
| Ceph storage | `10.0.70.0/24` | Ceph cluster traffic between Proxmox nodes |
| Kubernetes pods | `10.42.0.0/16` | Pod IPs (default) |
| Kubernetes services | `10.43.0.0/16` | Service IPs (default) |

### Key Addresses

| Host / Service | IP |
|----------------|-----|
| Proxmox nodes | `10.0.40.10` – `10.0.40.12` |
| Proxmox VIP (Keepalived) | `10.0.40.15` |
| NFS server | `10.0.40.2` |
| Docker host (`morpheus`) | `10.0.40.19` |
| Kubernetes control-plane nodes | `10.0.40.90` – `10.0.40.92` |
| Kubernetes API VIP | `10.0.40.101` |
| Internal gateway (`envoy-internal`) | `10.0.40.102` |
| External gateway (`envoy-external`) | `10.0.40.103` |
| Kubernetes DNS gateway (`k8s-gateway`) | `10.0.40.153` |
| Management VM (`deep-thought-01`) | `10.0.40.100` *(disabled by default)* |

---

## Layer 1: Proxmox (`home-dc-proxmox`)

- **3-node Proxmox VE cluster** (`pve-0`, `pve-1`, `pve-2`) on Debian 12.
- **Keepalived** floating VIP at `10.0.40.15` for HA web UI access.
- **Ceph** distributed storage across the three nodes, using dedicated NVMe drives on the `10.0.70.0/24` storage network.
- **NFS integration** from `10.0.40.2` for backups, ISOs, templates, and the shared media library.
- **API tokens** for Packer (`packer@pve`) and Terraform (`terraform@pve`) automation.
- **Backup jobs**, Gmail SMTP notifications, Chrony NTP, SSH key deployment.

Managed with Ansible + `Taskfile.yml`.

---

## Layer 2: Kubernetes (`home-dc-kubernetes`)

### Cluster

- **Talos Linux** VMs running on Proxmox.
- Active nodes: 3 control-plane nodes only (`k8s-ctrl-01` – `k8s-ctrl-03`).
- Legacy worker VMs exist in Proxmox but are **powered off** and not in the active Talos inventory.
- API endpoint uses a Talos VIP at `10.0.40.101`.

### Networking

- **Cilium** CNI in kube-proxy-free mode.
- **CoreDNS** for in-cluster DNS.
- **Envoy Gateway** (`envoy-internal` / `envoy-external`) exposes HTTPRoutes.
- **k8s-gateway** at `10.0.40.153` provides split-horizon DNS for local clients.
- **Cloudflare Tunnel** (`cloudflared`) brings public traffic in without opening ports.
- **external-dns** publishes records to Cloudflare.

### GitOps

- **Argo CD** watches `fabricesemti80/home-dc-kubernetes` and reconciles apps under `kubernetes/apps/`.
- Bootstrap ordering in `bootstrap/helmfile.d/` installs Cilium, CoreDNS, Spegel, cert-manager, Argo CD, etc.

### Storage

- **CephFS** via `ceph-csi` for workload config PVCs (`storageClass: cephfs`).
- **NFS media library** at `10.0.40.2:/media` exposed as `media-library-pvc` for media apps.

### Workloads

| Namespace | Apps |
|-----------|------|
| `media` | jellyfin, jellyseerr, immich, prowlarr, qbittorrent, radarr, sonarr, sabnzbd, recyclarr, tdarr |
| `productivity` | linkwarden, n8n, termix |
| `monitoring` | kube-prometheus-stack (Prometheus + Grafana), beszel-agent |
| `network` | cloudflare-dns, cloudflare-tunnel, envoy-gateway, k8s-gateway |
| `web` | glance, homepage |
| `argo-system` | argo-cd |
| `kube-system` | cilium, coredns, etcd-defrag, metrics-server, reloader, spegel, ceph-csi |
| `ci-cd` | arc-controller, arc-runner-set-homelab |
| `default` | echo |
| `doppler-operator-system` | doppler-operator |

### Ingress / Domains

- Base domain: `krapulax.dev`
- Internal domain: `krapulax.home`
- Public apps terminate through Cloudflare Access / Zero Trust, except webhook paths and bypassed apps like Jellyfin.
- Local DNS records for media apps point to the internal gateway via UniFi.

### Secrets

- **Doppler** operator syncs secrets into Kubernetes.
- **SOPS + age** for encrypted Git-stored secrets.
- No secrets committed to Git.

---

## Layer 3: Docker Host (`home-dc-docker`)

Plain Docker Compose stack on `morpheus` (`10.0.40.19`) for services kept outside Kubernetes.

### Services

| Service | Role |
|---------|------|
| Traefik | Reverse proxy / ingress for Docker services |
| cloudflared | Cloudflare Tunnel for Docker-host apps |
| Arcane | Secret / password manager |
| Beszel | Monitoring agent for Docker host |
| Uptime Kuma | Uptime monitoring |
| Whoami | Test / debug endpoint |
| Portainer | Docker management UI |
| Kestra | Workflow automation (standalone, H2-backed) |

### Network / Access

- Shared `homelab_proxy` network.
- Services exposed via `*.krapulax.dev` through the `trinity` Cloudflare tunnel.
- Some apps protected by Cloudflare Access; Beszel is bypassed.

### Secrets

- Rendered from Doppler `project-homelab / dev_homelab` into ignored `runtime/` files.

---

## Terraform / OpenTofu Stacks

| Stack | Repo | Purpose |
|-------|------|---------|
| `infra/terraform_proxmox` | `home-dc-kubernetes` | Proxmox VMs for Talos and optional management VM |
| `infra/terraform_cloudflare` | `home-dc-kubernetes` | Kubernetes tunnel, DNS, Access apps/policies |
| `infra/terraform_localdns` | `home-dc-kubernetes` | UniFi local DNS records for `*.krapulax.home` |
| `terraform/cloudflare` | `home-dc-docker` | Docker-host tunnel, DNS, Access apps |

---

## Common Entrypoints

### Proxmox repo

```bash
task plan      # dry-run Ansible
task apply     # deploy cluster config
```

### Kubernetes repo

```bash
mise install && task deps
task tf:plan
task talos:genconfig
task talos:bootstrap
task apps:bootstrap
task verify:cluster
```

### Docker repo

```bash
task stack:render
task stack:config
task stack:deploy
```

---

## Notes / Simplifications

- The Kubernetes cluster runs control-plane-only for current workloads; workers are retained as rollback capacity.
- Kestra runs standalone with H2; move to Postgres when workflow durability matters.
- Docker-host admin tools are still public via Cloudflare; likely next hardening step is Tailscale-only access.
- Management VM `deep-thought-01` is defined but disabled by default.
