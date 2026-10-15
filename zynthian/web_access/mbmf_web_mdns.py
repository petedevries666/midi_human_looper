"""Publish only MBMF's alias through the existing Avahi daemon; no OS hostname edit."""
import json
import logging
import subprocess
import threading
import time
from mbmf_web_policy import local_address

def addresses(data):
    return sorted({(item['ifindex'],a['local']) for item in data if item.get('ifname')!='lo' and (not item.get('flags') or 'MULTICAST' in item['flags'])
                   for a in item.get('addr_info',[]) if a.get('family')=='inet' and local_address(a.get('local',''))})

def run(stop=None,bus_factory=None,read_addresses=None,interval=5):
    if bus_factory is None:
        import dbus
        bus_factory=dbus.SystemBus
    if read_addresses is None:
        def read_addresses():
            return addresses(json.loads(subprocess.check_output(['/usr/sbin/ip','-j','-4','address','show','up'],timeout=2)))
    group=None;previous=None;last_error=None
    while stop is None or not stop.is_set():
        try:
            if group is None:
                bus=bus_factory();server=bus.get_object('org.freedesktop.Avahi','/')
                path=server.EntryGroupNew(dbus_interface='org.freedesktop.Avahi.Server')
                group=bus.get_object('org.freedesktop.Avahi',path)
            current=read_addresses()
            state=int(group.GetState(dbus_interface='org.freedesktop.Avahi.EntryGroup'))
            if state in (3,4):raise RuntimeError('mbmf.local alias collision/failure; use /mbmf/ fallback')
            if current!=previous:
                group.Reset(dbus_interface='org.freedesktop.Avahi.EntryGroup')
                added=False
                for interface,address in current:
                    try:
                        group.AddAddress(interface,0,0,'mbmf.local',address,dbus_interface='org.freedesktop.Avahi.EntryGroup');added=True
                    except Exception:
                        logging.warning('MBMF mDNS interface %s unavailable; other interfaces retained',interface)
                if added:group.Commit(dbus_interface='org.freedesktop.Avahi.EntryGroup')
                previous=current
            last_error=None
        except Exception as error:
            text=str(error)
            if text!=last_error:logging.warning('MBMF mDNS: %s',text);last_error=text
            # Reconnect if Avahi restarted; never rename the host on collision.
            if not isinstance(error,RuntimeError):group=None;previous=None
        if stop is None:time.sleep(interval)
        elif stop.wait(interval):break
    if group:
        try:group.Free(dbus_interface='org.freedesktop.Avahi.EntryGroup')
        except Exception:pass

def start():
    thread=threading.Thread(target=run,name='mbmf-mdns',daemon=True);thread.start();return thread
