import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'zynthian/web_access'))
import provision
import mbmf_web_mdns as mdns
import mbmf_web_policy as policy

class Provision(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.lib=self.root/'lib';self.data=self.root/'data';self.data.mkdir()
        self.web=self.root/'zynthian_webconf.py'
        self.web.write_text((ROOT/'tests/fixtures/webconf/zynthian_webconf.py.txt').read_text())
        (self.data/'install.json').write_text(json.dumps(dict(repository='/existing/repo',token_file=str(self.data/'editor.token'))))
        (self.data/'editor.token').write_text('retained token')
    def state(self):return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def apply(self,**kwargs):return provision.configure(self.web,self.lib,self.data,dependencies=False,trust_root=self.root,**kwargs)
    def test_check_install_repeat_auth_and_rollback(self):
        before=self.state();self.apply(check=True);self.assertEqual(self.state(),before)
        self.apply();installed=self.state();self.apply();self.assertEqual(self.state(),installed)
        self.assertEqual(json.loads((self.data/'web-access.json').read_text())['auth'],'none')
        self.apply(mode='token');self.apply()
        self.assertEqual(json.loads((self.data/'web-access.json').read_text())['auth'],'token')
        for p in ('editor.token','install.json'):self.assertEqual((self.data/p).read_bytes(),before['data/'+p])
        self.apply(rollback=True);self.assertEqual(self.web.read_bytes(),before['zynthian_webconf.py'])
        self.assertFalse((self.data/'web-access.json').exists())
    def test_hub_install_upgrade_repeat_disable_and_full_rollback(self):
        original=self.web.read_bytes();self.apply(mode='token')
        self.apply(hub=True);self.assertTrue(json.loads((self.data/'web-access.json').read_text())['hub'])
        before=self.state();self.apply();self.assertEqual(self.state(),before)
        self.assertEqual(json.loads((self.data/'web-access.json').read_text())['auth'],'token')
        self.assertEqual(self.web.read_bytes().count(b'BEGIN MBMF'),1)
        for f in provision.HUB_FILES:self.assertTrue((self.lib/f).is_file())
        self.apply(hub=False)
        self.assertNotIn('hub',json.loads((self.data/'web-access.json').read_text()))
        for f in provision.HUB_FILES:self.assertFalse((self.lib/f).exists())
        self.assertTrue((self.lib/'mbmf_web_entry.py').exists())
        self.apply(hub=True);self.apply(rollback=True);self.assertEqual(self.web.read_bytes(),original)
    def test_hub_fresh_install_and_transaction_failure(self):
        before=self.state();real=provision.owned.atomic
        def fail(path,data):
            if path==self.lib/'az-app.js':raise OSError('injected hub installation failure')
            return real(path,data)
        with patch.object(provision.owned,'atomic',side_effect=fail):
            with self.assertRaises(OSError):self.apply(hub=True)
        self.assertEqual(self.state(),before)
        self.apply(hub=True);before=self.state();self.apply(hub=True,check=True);self.assertEqual(self.state(),before)
        (self.lib/'az-app.js').write_text('modified by another installer');before=self.state()
        with self.assertRaises(ValueError):self.apply(hub=False)
        self.assertEqual(self.state(),before)

    def test_modified_owned_files_and_unknown_webconf_rejected(self):
        self.apply();self.web.write_text(self.web.read_text()+'# unrelated edit\n');before=self.state()
        for kwargs in ({'check':True},{},{'rollback':True}):
            with self.assertRaises(ValueError):self.apply(**kwargs)
            self.assertEqual(self.state(),before)
    def test_transaction_failure_preserves_installation(self):
        before=self.state();real=provision.owned.atomic
        def fail(path,data):
            if path==self.web:raise OSError('injected Webconf activation failure')
            return real(path,data)
        with patch.object(provision.owned,'atomic',side_effect=fail):
            with self.assertRaises(OSError):self.apply()
        self.assertEqual(self.state(),before)
    def test_writable_module_directory_rejected_without_mutation(self):
        self.lib.mkdir(mode=0o777);self.lib.chmod(0o777);before=self.state()
        with self.assertRaises(ValueError):self.apply(check=True)
        self.assertEqual(self.state(),before)
    def test_malformed_manifest_refused_without_mutation(self):
        self.apply();manifest=self.data/'web-access-installation.json'
        value=json.loads(manifest.read_text());value['files'][str(self.web)]['original']='../bad'
        manifest.write_text(json.dumps(value));before=self.state()
        with self.assertRaises(ValueError):self.apply(rollback=True)
        self.assertEqual(self.state(),before)

    def test_empty_token_option_refused_and_none_works(self):
        (self.data/'editor.token').write_text('');before=self.state()
        with self.assertRaises(ValueError):self.apply(mode='token')
        self.assertEqual(self.state(),before);self.apply(mode='none')
    def test_boundaries_and_address_changes(self):
        for ip in ('127.0.0.1','192.168.1.2','10.42.0.1','172.16.1.3','::1','fd00::1'):
            self.assertTrue(policy.local_address(ip))
        for ip in ('8.8.8.8','100.64.0.1','0.0.0.0','2001:4860::1','evil.example'):
            self.assertFalse(policy.local_address(ip))
        records=[dict(ifindex=2,ifname='eth0',addr_info=[dict(family='inet',local='192.168.1.2')]),
                 dict(ifindex=3,ifname='wlan0',addr_info=[dict(family='inet',local='10.42.0.1')]),
                 dict(ifindex=4,ifname='wan',addr_info=[dict(family='inet',local='8.8.8.8')])]
        self.assertEqual(mdns.addresses(records),[(2,'192.168.1.2'),(3,'10.42.0.1')])
        calls=[]
        class Group:
            def GetState(self,**kw):return 2
            def Reset(self,**kw):calls.append('reset')
            def AddAddress(self,*args,**kw):calls.append(args)
            def Commit(self,**kw):calls.append('commit')
            def Free(self,**kw):calls.append('free')
        group=Group()
        class Bus:
            def get_object(self,service,path):
                if path=='/':return type('Server',(),{'EntryGroupNew':lambda self,**kw:'/group'})()
                return group
        class Stop:
            n=0
            def is_set(self):return False
            def wait(self,interval):self.n+=1;return self.n==2
        batches=iter([[(2,'192.168.1.2')],[(3,'10.42.0.1')]])
        mdns.run(Stop(),Bus,lambda:next(batches))
        self.assertEqual(calls,['reset',(2,0,0,'mbmf.local','192.168.1.2'),'commit','reset',(3,0,0,'mbmf.local','10.42.0.1'),'commit','free'])
        calls.clear()
        mdns.run(Stop(),Bus,lambda:[(2,'192.168.1.2')],hostname='az.local')
        self.assertIn((2,0,0,'az.local','192.168.1.2'),calls)
        self.assertNotIn((2,0,0,'mbmf.local','192.168.1.2'),calls)


if __name__=='__main__':unittest.main()
