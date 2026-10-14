"""Disposable production control/activation paths. Never operates systemd or hardware."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'headless')]
from test_headless_mvp import HeadlessTests
from test_movement_persistence import movement
from server import Control
import conductor

def update_race():
    spec=importlib.util.spec_from_file_location('audit_updater',ROOT/'scripts/zynthian-update.py');u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
    class Service:
        def __init__(self):self.calls=[]
        def service(self,action):self.calls.append(action)
        def healthy(self,config,expected):pass
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'install.json';old=dict(version=1,binary='old',repository='old',web_port_base=8765)
        u.atomic(path,old);candidate={**old,'binary':'new','repository':'new'}
        journal=dict(version=1,phase='pending',previous=old,candidate=candidate,expected={})
        u.atomic(path,{**old,'web_port_base':9000});service=Service();error=None
        try:u.activate(path,candidate,service,{},journal)
        except ValueError as failure:error=str(failure)
        return dict(scope='Actual file activation, service fixture only',error=error,finalPort=json.loads(path.read_text())['web_port_base'],serviceCalls=service.calls)

def unrelated_learn():
    HeadlessTests.setUpClass();api=HeadlessTests('runTest')
    try:
        api.command('panic');api.command('controller_source',sourceId=101)
        c=Control(api.sock);state=api.call();patch=c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        model=conductor.migrate(patch);source=movement();source['duration']=60
        model.update(version=2,movements=[source],ccRate=25);api.command('conductor_commit',conductor=model)
        api.command('movement_preview',movementId=source['id']);before=api.call()
        api.command('controller_learn',sourceId=101);api.command('midi_cc',channel=2,number=21,value=80);time.sleep(.02)
        after=api.call()
        return dict(scope='Actual native control/runtime state, not JACK wire capture',before=before['movements']['active'],after=after['movements']['active'],cancelledDelta=after['movements']['cancelled']-before['movements']['cancelled'])
    finally:HeadlessTests.tearDownClass()
if __name__=='__main__':print(json.dumps(dict(update=update_race(),learn=unrelated_learn()),indent=2))
