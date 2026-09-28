p = "engine/level/parallax.emp"
s = open(p).read()
o = """        tst.b   Parallax_Shadow_Split+2             // (Parallax_Shadow_Split+2).w
        beq     .anchor_kept_sel
        sf      Parallax_Shadow_Split+2
        clr.b   Parallax_Band_Sel_Valid             // (Parallax_Band_Sel_Valid).w
    .anchor_kept_sel:
"""
assert s.count(o) == 1
s = s.replace(o, "")
o2 = """        st      Parallax_Shadow_Split+2             // (Parallax_Shadow_Split+2).w
"""
assert s.count(o2) == 1
s = s.replace(o2, "")
open(p, "w").write(s)
