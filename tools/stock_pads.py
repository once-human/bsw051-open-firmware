import re,sys
L=open(sys.argv[1]).read().splitlines()
D=0x678204
PC=0x842CF0
names={**{i:f"P0_{i}" for i in range(8)},**{8+i:f"P1_{i}" for i in range(8)},**{16+i:f"P2_{i}" for i in range(8)},**{24+i:f"P3_{i}" for i in range(7)},32:"P4_0",33:"P4_1",34:"P4_2",35:"P4_3",36:"H_0",37:"H_1",38:"H_2"}
pull={0:"UP",1:"DOWN",2:"NONE"}
ins=[]
for l in L:
    m=re.match(r'\s*([0-9a-f]+):\s+(.*)',l)
    if m: ins.append((int(m[1],16),m[2]))
rows=[]
for i,(a,t) in enumerate(ins):
    m=re.match(r'bl\s+0x([0-9a-f]+)',t)
    if not m: continue
    tg=int(m[1],16)
    if tg!=PC and tg-D!=PC: continue
    reg={}; stack={}; regval={}
    for a2,t2 in reversed(ins[max(0,i-14):i]):
        if re.match(r'(bl|bx|pop|b\.|b\s)',t2): break
        m2=re.match(r'movs?(?:\.w)?\s+(r\d),\s*#(\d+)',t2)
        if m2 and m2[1] not in reg: reg[m2[1]]=int(m2[2]); continue
        m3=re.match(r'str\s+(r\d),\s*\[sp(?:,\s*#(\d+))?\]',t2)
        if m3:
            o=int(m3[2] or 0)
            if o not in stack: stack[o]=m3[1]
    g=lambda r:reg.get(r,'?')
    rows.append((a,g('r0'),g('r1'),g('r2'),g('r3'),g(stack.get(0,'-')) if 0 in stack else '?',g(stack.get(4,'-')) if 4 in stack else '?'))
print(len(rows),'Pad_Config calls')
for a,p,mode,pw,pu,oe,o in rows:
    print(f"{a:#x} pin={names.get(p,p)!s:5} mode={'SW' if mode==0 else 'PINMUX' if mode==1 else mode} pwr={pw} pull={pull.get(pu,pu)} OE={oe} out={o}")
