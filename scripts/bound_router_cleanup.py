"""Create a local JAR with a shorter existing normalization-loop safety cap.

Only BasicBoard's existing 2000-iteration normalization guards become 64.
Routing algorithms, clearances and DRC are unchanged. Native PCB DRC remains
mandatory. Preserve the official JAR and record the exact patched methods.
"""
import hashlib,json,struct,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'tools/freerouting/freerouting-2.4.1.jar'
out=src.with_name('freerouting-2.4.1-bounded.jar')
member='app/freerouting/board/facade/BasicBoard.class'
with zipfile.ZipFile(src) as z:
    original=z.read(member)
d=bytearray(original);cursor=8;cp={};patches=[]
def u2():
    global cursor
    n=struct.unpack_from('>H',d,cursor)[0];cursor+=2;return n
def u4():
    global cursor
    n=struct.unpack_from('>I',d,cursor)[0];cursor+=4;return n
n=u2();i=1
while i<n:
    tag=d[cursor];cursor+=1
    if tag==1:
        size=u2();cp[i]=bytes(d[cursor:cursor+size]).decode('utf8',errors='replace')
        if 'normalize' in cp[i] and '2000' in cp[i]:
            d[cursor:cursor+size]=d[cursor:cursor+size].replace(b'2000',b'0064')
        cursor+=size
    elif tag in (3,4):
        if tag==3 and struct.unpack_from('>i',d,cursor)[0]==2000:
            struct.pack_into('>i',d,cursor,64)
        cursor+=4
    elif tag in (5,6):cursor+=8;i+=1
    elif tag in (7,8,16,19,20):cursor+=2
    elif tag in (9,10,11,12,17,18):cursor+=4
    elif tag==15:cursor+=3
    else:raise ValueError(('unknown constant tag',tag))
    i+=1
cursor+=6
interface_count=u2();cursor+=2*interface_count
for kind in ('field','method'):
    for _ in range(u2()):
        access=u2();name=cp[u2()];descriptor=cp[u2()]
        for _ in range(u2()):
            attr=cp[u2()];size=u4();end=cursor+size
            if kind=='method' and attr=='Code':
                code_start=cursor+8;code_len=struct.unpack_from('>I',d,cursor+4)[0]
                code=bytes(d[code_start:code_start+code_len]);needle=bytes.fromhex('1107d0')
                at=0
                while (at:=code.find(needle,at))>=0:
                    assert name in ('normalizeTraces','normalizeAllTraces'),(name,descriptor)
                    struct.pack_into('>H',d,code_start+at+1,64)
                    patches.append({'method':name,'descriptor':descriptor,'code_offset':at})
                    at+=3
            cursor=end
assert len(patches)==2,patches
with zipfile.ZipFile(src) as source,zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as target:
    for item in source.infolist():target.writestr(item,bytes(d) if item.filename==member else source.read(item.filename))
report={'original_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
        'patched_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
        'normalization_iteration_cap':64,'patches':patches,
        'limitations':'Local cleanup timeout adjustment only. Native DRC required; not an upstream release.'}
out.with_suffix('.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
