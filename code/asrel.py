"""CAIDA serial-1 AS-relationship loader + customer-cone queries."""
import bz2
class ASRel:
    def __init__(self, path):
        self.prov={}   # as -> set(providers)
        self.cust={}   # as -> set(customers)
        self.peer={}   # as -> set(peers)
        for line in bz2.open(path,"rt"):
            if line[0]=="#": continue
            a,b,r=line.strip().split("|")[:3]; a=int(a); b=int(b)
            if r=="-1":
                self.cust.setdefault(a,set()).add(b); self.prov.setdefault(b,set()).add(a)
            else:
                self.peer.setdefault(a,set()).add(b); self.peer.setdefault(b,set()).add(a)
        self._cone={}
    def rel(self,a,b):
        """relationship of b as seen from a: 'c' b is a's customer, 'p' provider, 'e' peer, None unknown"""
        if b in self.cust.get(a,()): return "c"
        if b in self.prov.get(a,()): return "p"
        if b in self.peer.get(a,()): return "e"
        return None
    def cone(self,a):
        c=self._cone.get(a)
        if c is None:
            c={a}; stack=[a]
            while stack:
                x=stack.pop()
                for y in self.cust.get(x,()):
                    if y not in c: c.add(y); stack.append(y)
            self._cone[a]=c
        return c
    def related(self,a,b):
        return a==b or self.rel(a,b) in ("c","p")
