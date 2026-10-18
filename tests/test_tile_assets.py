import sys,pathlib,tempfile,threading,unittest,urllib.request,urllib.error,json,hashlib
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'));import server
class TileAssets(unittest.TestCase):
 def test_all_original_crops_are_present_unique_and_bounded(self):
  folder=ROOT/'headless/web/assets/tiles';data=json.loads((folder/'manifest.json').read_text(encoding='utf-8'));self.assertEqual(len(data['tiles']),32);hashes=set()
  for tile in data['tiles']:
   self.assertEqual(pathlib.Path(tile['file']).name,tile['file']);raw=(folder/tile['file']).read_bytes();digest=hashlib.sha256(raw).hexdigest();self.assertEqual(digest,tile['sha256']);self.assertEqual(len(raw),tile['bytes']);self.assertEqual(raw[:4],b'RIFF');self.assertEqual(raw[8:12],b'WEBP');self.assertGreater(tile['width'],350);self.assertGreater(tile['height'],190);hashes.add(digest)
  self.assertEqual(len(hashes),32)
 def test_asset_route_cannot_escape_and_api_stays_authenticated(self):
  with tempfile.TemporaryDirectory() as temp:
   root=pathlib.Path(temp);(root/'assets').mkdir();(root/'assets/a.webp').write_bytes(b'RIFF-test-WEBP');(root/'private.txt').write_text('not an asset')
   with patch.object(server,'ROOT',root):
    http=server.make_server('127.0.0.1',0,str(root/'absent.sock'),token='test-only-token',patch_dir=root/'patches');thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();url='http://127.0.0.1:'+str(http.server_port)
    try:
     with urllib.request.urlopen(url+'/assets/a.webp') as response:self.assertEqual(response.headers['Content-Type'],'image/webp');self.assertEqual(response.read(),b'RIFF-test-WEBP')
     for path,status in [('/assets/../private.txt',404),('/assets/%2e%2e/private.txt',404),('/assets/missing.webp',404),('/api/v1/state',401)]:
      with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(url+path)
      self.assertEqual(caught.exception.code,status)
    finally:http.shutdown();http.server_close();thread.join()
if __name__=='__main__':unittest.main()
