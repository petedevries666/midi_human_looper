"""Small LUMAZ settings adapter. Reuse device-installed helpers; no GUI clone."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile

# Names/values from LUMAZ e148b7f; advanced crop/proxy workflows stay on touch.
SCALE_PROFILES = {
    'auto':dict(scale='bilinear',cscale='bilinear',dscale='mitchell',deband=False,interpolation=False),
    'fast':dict(scale='bilinear',cscale='bilinear',dscale='bilinear',deband=False,interpolation=False),
    'quality':dict(scale='lanczos',cscale='bicubic',dscale='mitchell',deband=False,interpolation=False),
}

class Settings:
    def __init__(self,mpv,root=Path('/root'),control='/tmp/lumaz-light-control.sock'):
        self.mpv=mpv;self.root=Path(root);self.config=self.root/'lumaz/config';self.control=control;self.modules={}
    def helper(self,name):
        if name not in ('audio_playback','midi_routing'):raise ValueError('Unknown LUMAZ helper')
        path=self.root/(name+'.py')
        if path.is_symlink() or not path.is_file():raise ValueError('LUMAZ helper unavailable: '+name)
        stat=path.stat()
        if stat.st_uid not in (0,os.geteuid()) or stat.st_mode & 0o022:raise ValueError('Untrusted LUMAZ helper')
        key=(name,stat.st_mtime_ns,stat.st_size)
        if key not in self.modules:
            spec=importlib.util.spec_from_file_location('az_device_'+name,path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            required=('load_audio_settings','save_audio_settings','available_outputs') if name=='audio_playback' else ('load_midi_settings','save_midi_settings','jack_physical_ports')
            if any(not callable(getattr(module,fn,None)) for fn in required):raise ValueError('Installed LUMAZ helper is incompatible: '+name)
            self.modules={k:v for k,v in self.modules.items() if k[0]!=name};self.modules[key]=module
        return self.modules[key]
    def path(self,name):
        path=self.config/name
        for parent in (self.root,self.root/'lumaz',self.config):
            if parent.is_symlink() or (parent.exists() and parent.stat().st_mode & 0o022):raise ValueError('Untrusted LUMAZ settings directory')
        if path.is_symlink():raise ValueError('Refusing settings symlink')
        if path.exists() and path.stat().st_size>2*1024*1024:raise ValueError('Oversized LUMAZ configuration')
        return path
    def revision(self):
        digest=hashlib.sha256()
        for name in ('scale-mode','audio-playback.json','midi-settings.json','slots.json'):
            path=self.path(name);digest.update(name.encode());digest.update(path.read_bytes() if path.exists() else b'<missing>')
        return digest.hexdigest()
    def read(self):
        revision=self.revision()
        for name in ('audio-playback.json','midi-settings.json','slots.json','hdmi-output-lock.json'):
            path=self.path(name)
            if path.exists() and not isinstance(json.loads(path.read_text()),dict):raise ValueError('Malformed LUMAZ configuration: '+name)
        audio=self.helper('audio_playback');midi=self.helper('midi_routing')
        scale=self.path('scale-mode');mode=scale.read_text().strip() if scale.exists() else 'auto'
        lock=self.path('hdmi-output-lock.json');hdmi=json.loads(lock.read_text()) if lock.exists() else None
        slots=self.path('slots.json');channel=json.loads(slots.read_text()).get('midi_channel',16) if slots.exists() else 16
        result={'revision':revision,
                'video':{'scale':mode,'hdmi':hdmi},
                'audio':audio.load_audio_settings(self.path('audio-playback.json')),
                'outputs':list(audio.available_outputs(self.mpv(['get_property','audio-device-list']))),
                'midi':midi.load_midi_settings(self.path('midi-settings.json')),
                'ports':midi.jack_physical_ports(),'channel':channel}
        if revision!=self.revision():raise ValueError('LUMAZ changed during reading; reopen the menu')
        return result
    def write(self,body):
        if body.get('revision')!=self.revision():raise ValueError('LUMAZ settings changed; reopen the menu before saving')
        category=body.get('category');value=body.get('value')
        if set(body)!={'action','category','value','revision'} or body.get('action')!='settings':raise ValueError('Invalid settings request')
        if category=='video':
            if not isinstance(value,str) or value not in SCALE_PROFILES:raise ValueError('Unknown scale mode')
            # Apply the original scaler profile; commit only after acknowledgement.
            for key,val in SCALE_PROFILES[value].items():self.mpv(['set_property',key,val])
            self.atomic('scale-mode',value+'\n');return 'Scale mode saved and applied'
        if category=='audio':
            audio=self.helper('audio_playback')
            if not isinstance(value,dict) or set(value)!=set(audio.VIEWS):raise ValueError('Invalid audio views')
            available=audio.available_outputs(self.mpv(['get_property','audio-device-list']))
            current=audio.load_audio_settings(self.path('audio-playback.json'))
            for view,setting in value.items():
                if not isinstance(setting,dict) or set(setting)!={'enabled','output'} or type(setting['enabled']) is not bool:
                    raise ValueError('Invalid audio setting')
                if setting['output'] is not None and not isinstance(setting['output'],str):raise ValueError('Invalid audio output')
                if setting['output'] is not None and setting['output'] not in available and setting['output']!=current[view]['output']:raise ValueError('Audio output unavailable')
            self.persist(audio.save_audio_settings,'audio-playback.json',value,body['revision'])
            return 'Audio settings saved; apply on the next playback in each view'
        if category=='midi':
            midi=self.helper('midi_routing');current=midi.load_midi_settings(self.path('midi-settings.json'))
            if not isinstance(value,dict) or set(value)!={'video_input_ports','light_input_ports','output_port','midi_through'}:
                raise ValueError('Invalid MIDI settings')
            ports=midi.jack_physical_ports()
            for key in ('video_input_ports','light_input_ports'):
                if not isinstance(value[key],list) or any(not isinstance(p,str) for p in value[key]):raise ValueError('Invalid MIDI input list')
                allowed={p['port'] for p in ports['inputs']}|set(current[key])
                if len(set(value[key]))!=len(value[key]) or any(p not in allowed for p in value[key]):raise ValueError('MIDI input unavailable')
            allowed={p['port'] for p in ports['outputs']}|{current['output_port'],''}
            if type(value['midi_through']) is not bool or not isinstance(value['output_port'],str) or value['output_port'] not in allowed:
                raise ValueError('MIDI output unavailable')
            # A failed datagram is not reported as an applied configuration.
            # Retain the previous bytes if the native reload request cannot send.
            path=self.path('midi-settings.json');previous=path.read_bytes() if path.exists() else None
            self.persist(midi.save_midi_settings,'midi-settings.json',value,body['revision'])
            try:
                with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as client:
                    client.settimeout(1);client.sendto(b'{"action":"reload_midi_routes"}',self.control)
            except OSError:
                if previous is None:path.unlink()
                else:self.atomic('midi-settings.json',previous.decode())
                raise ValueError('LUMAZ reload unavailable; prior MIDI settings restored')
            return 'MIDI settings saved; native route reload requested'
        raise ValueError('Unsupported settings category')
    def persist(self,save,name,value,revision):
        path=self.path(name);original=json.loads(path.read_text()) if path.exists() else {}
        if not isinstance(original,dict):raise ValueError('Malformed LUMAZ settings')
        if name=='midi-settings.json' and original.get('version',1) not in (1,2):raise ValueError('Unsupported LUMAZ MIDI settings version')
        self.config.mkdir(parents=True,exist_ok=True)
        # Let LUMAZ normalize through its own save helper, on a private staging
        # file. Retain fields outside the controls offered by this small portal.
        with tempfile.TemporaryDirectory(prefix='.az-settings-',dir=self.config) as stage:
            staged=Path(stage)/'settings.json';save(value,staged);normalized=json.loads(staged.read_text())
        merged=dict(original)
        for key,item in normalized.items():
            merged[key]={**original.get(key,{}),**item} if isinstance(item,dict) and isinstance(original.get(key,{}),dict) else item
        if revision!=self.revision():raise ValueError('LUMAZ changed before saving; reopen the menu')
        self.atomic(name,json.dumps(merged,indent=2)+'\n')

    def atomic(self,name,text):
        path=self.path(name);self.config.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name('.az-'+path.name+'.tmp')
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'w') as handle:handle.write(text);handle.flush();os.fsync(handle.fileno())
            os.replace(temporary,path)
        finally:
            if temporary.exists():temporary.unlink()
