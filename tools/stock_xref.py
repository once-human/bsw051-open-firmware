import re,struct
d=open('logs/flash_dump.bin','rb').read(); base=0x800000; D=0x678204
ins=[]
for l in open(f"{__import__('sys').argv[1]}/stock.dis"):
    m=re.match(r'\s*([0-9a-f]+):\s+(.*)',l)
    if m: ins.append((int(m[1],16),m[2].strip()))
idx={a:i for i,(a,_) in enumerate(ins)}
def callers(t):
    out=[]
    for a,x in ins:
        m=re.match(r'bl?x?\s+0x([0-9a-f]+)',x)
        if m and x.startswith('bl'):
            g=int(m[1],16)
            if g==t or g==t-D or g-D==t or g-D==t-D: out.append(a)
    return out
def lits(v):
    r=[];b=struct.pack('<I',v);i=-1
    while True:
        i=d.find(b,i+1)
        if i<0:break
        if 0x39000<=i<0xA9000:r.append(hex(base+i))
    return r
for n,t in [('SPIC2 pin setup',0x882F60),('cmd writer RAM',0x883054),('quad start',0x88309E),('flash cmd writer',0x862614),('LCD power/reset',0x8602CC),('init list',0x83BBF4),('P0_1 fn',0x854f00),]:
    print(n,hex(t),'callers',[hex(x) for x in callers(t)],'ptr',lits(t|1)+lits((t-D)|1))
print('SPIC2 base literal at',lits(0x400A0000))
print('SPIC1 base literal',lits(0x40080000)[:8])
print('SPI0/1 base', lits(0x40013000)[:8], lits(0x40013400)[:8])
