p = "engine/level/parallax.emp"
s = open(p).read()
o = """        clr.w   Parallax_Shadow_Split               // (Parallax_Shadow_Split).w
    .cap_anchors_split_rebuild_end:"""
assert s.count(o) == 1
s = s.replace(o, """    .cap_anchors_split_rebuild_end:""")
open(p, "w").write(s)
