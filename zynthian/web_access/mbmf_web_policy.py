"""Explicit private-network boundary for the MBMF Webconf entry point."""
import ipaddress

PRIVATE = tuple(ipaddress.ip_network(v) for v in ('127.0.0.0/8','10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','169.254.0.0/16','::1/128','fc00::/7','fe80::/10'))
def local_address(value):
    try:
        address=ipaddress.ip_address(value)
        if address.version==6 and address.ipv4_mapped:address=address.ipv4_mapped
        return any(address.version==network.version and address in network for network in PRIVATE)
    except ValueError:return False

