#!/usr/bin/env python3
"""Generate the architecture diagram for home-dc/README.md.

Requires:
    pip install diagrams
    graphviz binary (e.g. nix-shell -p graphviz, apt install graphviz, brew install graphviz)
"""

from pathlib import Path

from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.network import Internet, Envoy, Traefik
from diagrams.generic.network import Firewall, Router
from diagrams.k8s.compute import Deploy
from diagrams.k8s.ecosystem import ExternalDns
from diagrams.k8s.storage import PVC
from diagrams.onprem.container import Docker
from diagrams.onprem.compute import Server
from diagrams.onprem.storage import Ceph
from diagrams.generic.storage import Storage

OUT = Path(__file__).parent / "architecture.png"

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
    k8s_gw = Server("k8s-gateway\n10.0.40.153")

    with Cluster("Docker Host — morpheus (10.0.40.19)"):
        traefik = Traefik("Traefik")
        docker_apps = Docker(
            "Arcane / Portainer / Kestra\n"
            "Uptime Kuma / Whoami / Beszel"
        )

    with Cluster("Proxmox VE Cluster"):
        pve0 = Server("pve-0\n10.0.40.10")
        pve1 = Server("pve-1\n10.0.40.11")
        pve2 = Server("pve-2\n10.0.40.12")

    with Cluster("Kubernetes — Talos Cluster"):
        with Cluster("Control Plane"):
            cp0 = Deploy("k8s-ctrl-01\n10.0.40.90")
            cp1 = Deploy("k8s-ctrl-02\n10.0.40.91")
            cp2 = Deploy("k8s-ctrl-03\n10.0.40.92")

        argo = Server("Argo CD")
        cilium = Server("Cilium")
        coredns = Server("CoreDNS")
        ext_dns = ExternalDns("external-dns")
        envoy_int = Envoy("envoy-internal\n10.0.40.102")
        envoy_ext = Envoy("envoy-external\n10.0.40.103")

        with Cluster("Workloads"):
            media = Server("Media Stack")
            prod = Server("Productivity")
            mon = Server("Monitoring")
            web = Server("Web")

    with Cluster("Storage"):
        ceph = Ceph("Ceph Cluster\n10.0.70.0/24")
        cephfs = PVC("CephFS PVCs")
        nfs = Storage("NFS 10.0.40.2:/media\nmedia-library-pvc")

    internet >> cloudflare
    cloudflare >> Edge(label="trinity tunnel") >> traefik
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

    media >> cephfs
    media >> nfs
    prod >> cephfs
    mon >> cephfs
    web >> cephfs
    cephfs >> ceph

    pve0 >> Edge(label="Ceph OSD") >> ceph
    pve1 >> ceph
    pve2 >> ceph

    pve0 >> Edge(label="hosts VM") >> cp0
    pve1 >> cp1
    pve2 >> cp2

    pve0 >> Edge(label="hosts VM") >> docker_apps
    traefik >> docker_apps
