#!/usr/bin/env python3
"""Generate the architecture diagram for home-dc/README.md.

Requires:
    pip install diagrams
    graphviz binary (e.g. nix-shell -p graphviz, apt install graphviz, brew install graphviz)
"""

from pathlib import Path

from diagrams import Diagram, Cluster, Edge
from diagrams.custom import Custom
from diagrams.onprem.network import Internet, Envoy
from diagrams.generic.network import Firewall, Router
from diagrams.onprem.container import Docker
from diagrams.onprem.compute import Server
from diagrams.onprem.storage import Ceph
from diagrams.generic.storage import Storage

OUT = Path(__file__).parent / "architecture.png"
ICON_DIR = Path(__file__).parent / "icons"


def icon(name: str) -> str:
    return str(ICON_DIR / name)


graph_attr = {
    "pad": "0.5",
    "ranksep": "1.5",
    "nodesep": "0.5",
    "splines": "spline",
    "bgcolor": "white",
    "fontname": "Helvetica",
}

with Diagram(
    "Architecture Diagram",
    filename=str(OUT.with_suffix("")),
    show=False,
    direction="TB",
    graph_attr=graph_attr,
):
    internet = Internet("Internet")
    cloudflare = Firewall("Cloudflare\nZero Trust / DNS / Tunnels")
    unifi = Router("UniFi DNS\nkrapulax.home")

    with Cluster("Service Hosts — home-dc-service-hosts"):
        pbs = Server("proxmox-pbs-0\n10.0.40.16")
        docker0 = Docker(
            "docker-svc-0\n10.0.40.54\n"
            "Portainer / Docktail / Beszel / Apps"
        )
        docker1 = Docker(
            "docker-svc-1\n10.0.40.53\n"
            "Portainer Agent / Beszel Agent"
        )
        physical = Server("Physical service hosts\nfuture/edge nodes")

    with Cluster("Proxmox VE Cluster"):
        pve0 = Custom("pve-0\n10.0.40.10", icon("proxmox.png"))
        pve1 = Custom("pve-1\n10.0.40.11", icon("proxmox.png"))
        pve2 = Custom("pve-2\n10.0.40.12", icon("proxmox.png"))

    with Cluster("Kubernetes — Talos Cluster"):
        with Cluster("Control Plane"):
            cp0 = Custom("k8s-ctrl-01\n10.0.40.90", icon("kubernetes.png"))
            cp1 = Custom("k8s-ctrl-02\n10.0.40.91", icon("kubernetes.png"))
            cp2 = Custom("k8s-ctrl-03\n10.0.40.92", icon("kubernetes.png"))

        k8s_gw = Server("k8s-gateway\n10.0.40.153")
        argo = Server("Argo CD")
        cilium = Server("Cilium")
        coredns = Server("CoreDNS")
        ext_dns = Server("external-dns")
        envoy_int = Envoy("envoy-internal\n10.0.40.102")
        envoy_ext = Envoy("envoy-external\n10.0.40.103")

        with Cluster("Workloads"):
            media = Custom("Media Stack", icon("jellyfin.png"))
            prod = Custom("Productivity", icon("n8n.png"))
            mon = Custom("Monitoring", icon("grafana.png"))
            web = Custom("Web", icon("glance.png"))

        with Cluster("Persistent Volumes"):
            cephfs = Server("CephFS PVCs")
            nfs_pvc = Server("NFS media-library-pvc")

    with Cluster("External Storage"):
        ceph0 = Ceph("Ceph OSD 1\n10.0.70.10")
        ceph1 = Ceph("Ceph OSD 2\n10.0.70.11")
        ceph2 = Ceph("Ceph OSD 3\n10.0.70.12")
        nfs = Storage("NFS Server\n10.0.40.2:/media")

    # Public / private ingress
    internet >> cloudflare
    cloudflare >> Edge(label="kubernetes tunnel") >> envoy_ext
    cloudflare >> Edge(label="public DNS") >> k8s_gw
    cloudflare >> Edge(label="Access policies") >> envoy_ext

    unifi >> Edge(label="internal DNS") >> k8s_gw
    k8s_gw >> envoy_int

    envoy_int >> media
    envoy_int >> prod
    envoy_int >> mon
    envoy_int >> web
    envoy_ext >> media
    envoy_ext >> prod
    envoy_ext >> mon
    envoy_ext >> web

    argo >> media
    argo >> prod
    argo >> mon
    argo >> web
    cilium >> media
    cilium >> prod
    cilium >> mon
    cilium >> web
    coredns >> media
    coredns >> prod
    coredns >> mon
    coredns >> web
    ext_dns >> Edge(label="writes records") >> cloudflare

    # Storage relationships
    media >> cephfs
    media >> nfs_pvc
    prod >> cephfs
    mon >> cephfs
    web >> cephfs

    cephfs >> ceph0
    cephfs >> ceph1
    cephfs >> ceph2
    nfs_pvc >> nfs

    # Proxmox hosts everything, including Ceph OSDs
    pve0 >> Edge(label="Ceph OSD") >> ceph0
    pve1 >> Edge(label="Ceph OSD") >> ceph1
    pve2 >> Edge(label="Ceph OSD") >> ceph2

    pve0 >> Edge(label="hosts VM") >> cp0
    pve1 >> Edge(label="hosts VM") >> cp1
    pve2 >> Edge(label="hosts VM") >> cp2

    pve0 >> Edge(label="hosts LXC") >> pbs
    pve1 >> Edge(label="hosts VM") >> docker0
    pve2 >> Edge(label="hosts VM") >> docker1

    internet >> Edge(label="Tailscale Services") >> docker0
    docker0 >> Edge(label="Portainer agent") >> docker1
    docker0 >> Edge(label="Beszel TCP 45876") >> docker1
    docker0 >> Edge(label="future management") >> physical
