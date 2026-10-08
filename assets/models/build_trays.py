#!/usr/bin/env python3
"""CableTray kit -> GLB for Godot 4.x. Meters, Y-up. Origin = tray centerline at the piece's input connection point.
Run direction of a piece = -Z (Godot forward). Grid: 1 m cells, connection points at cell-edge midpoints."""
import os, math, json, struct
_src = open("/home/claude/build_kit.py").read()
_a = _src.index("# ---------------------------------------------------------------- constants")
_b = _src.index("# ---------------------------------------------------------------- assets")
_c = _src.index("# ---------------------------------------------------------------- GLB writer")
_d = _src.index("# ---------------------------------------------------------------- export")
OUT = "/mnt/user-data/outputs/CableTrayKit"
os.makedirs(OUT + "/assets", exist_ok=True)
exec(_src[_a:_b].replace('OUT = "/mnt/user-data/outputs/VerticalKit"', ""))
_w = _src[_c:_d].replace("        if n.ry:\n", "        if getattr(n, 'rot', None): d['rotation'] = [round(c, 6) for c in n.rot]\n        elif n.ry:\n")
exec(_w)

MATS.clear()
MATS.update({
    "M_Tray_Steel": ((0.70, 0.72, 0.74, 1), 0.85, 0.45, None),
    "M_Tray_Dark":  ((0.17, 0.19, 0.21, 1), 0.60, 0.55, None),
    "M_Tray_Cover": ((0.52, 0.55, 0.58, 1), 0.70, 0.50, None),
})
S, D, C = "M_Tray_Steel", "M_Tray_Dark", "M_Tray_Cover"

# ---- cross-section (meters): width 0.30, height 0.10, rail 0.02, base/rung 0.012
HW, HH, RT, BASE = 0.15, 0.05, 0.02, 0.012

# ---- local frame (a=lateral, b=forward along run, h=open/up side) -> world axes
class Mp:
    def __init__(s, x, y, z): s.sp = (x, y, z)
    def p(s, a, b, h):
        v = (a, b, h); return tuple(sg*v[i] for i, sg in s.sp)
    def face(s, f):
        idx = {"a": 0, "b": 1, "h": 2}[f[0]]; sg = 1 if f[1] == "+" else -1
        for w, (i, sgn) in enumerate(s.sp):
            if i == idx: return ("+" if sg*sgn > 0 else "-") + "xyz"[w]
HZ   = Mp((0, 1), (2, 1), (1, -1))    # ceiling/floor: x=a, y=h(open up), z=-b
WALL = Mp((2, 1), (0, 1), (1, -1))    # horizontal on wall: x=h(open +X), y=a, z=-b
VERT = Mp((2, 1), (1, 1), (0, 1))     # vertical on wall: x=h(open +X), y=b, z=a

def B(m, mat, mp, a, b, h, skip=()):
    p0 = mp.p(a[0], b[0], h[0]); p1 = mp.p(a[1], b[1], h[1])
    mn = tuple(min(u, v) for u, v in zip(p0, p1)); mx = tuple(max(u, v) for u, v in zip(p0, p1))
    m.box(mat, mn, mx, tuple(mp.face(s) for s in skip))

def rail(m, mp, side, b0, b1):
    B(m, S, mp, (side*(HW-RT), side*HW), (b0, b1), (-HH, HH))
def rung(m, mp, bc):                     # rung across the width, centered at forward distance bc
    B(m, S, mp, (-HW+RT, HW-RT), (bc-0.02, bc+0.02), (-HH, -HH+BASE), ("a-", "a+"))
def rung_arm(m, mp, ac, b0, b1):         # rung in a side arm (runs along b, positioned along a)
    B(m, S, mp, (ac-0.02, ac+0.02), (b0, b1), (-HH, -HH+BASE), ("b-", "b+"))

def conn(mp, name, a, b, h, da, db, dh):
    return Node(name, t=mp.p(a, b, h), extras={"connection": name, "travel_dir": list(mp.p(da, db, dh))})

# ---------------------------------------------------------------- pieces
def straight(name, mp, kind):
    m = Mesh(name)
    rail(m, mp, -1, 0, 1); rail(m, mp, 1, 0, 1)
    if kind == "floor":
        B(m, S, mp, (-HW+RT, HW-RT), (0, 1), (-HH, -HH+BASE), ("a-", "a+"))      # solid trough base
    else:
        for bc in (0.125, 0.375, 0.625, 0.875): rung(m, mp, bc)
    if kind == "wall":                                                            # fixing ears
        for bc in (0.125, 0.875):
            for sd in (-1, 1): B(m, D, mp, (sd*HW, sd*(HW+0.04)), (bc-0.03, bc+0.03), (-HH, -HH+BASE), ("a-" if sd > 0 else "a+",))
    return Node(name, m, children=[conn(mp, "Conn_In", 0, 0, 0, 0, 1, 0), conn(mp, "Conn_Out", 0, 1, 0, 0, 1, 0)],
                extras={"run": 1.0, "section": "0.30 x 0.10", "kind": kind})

def junction(name, mp, kind):
    m = Mesh(name); c0, c1 = 0.35, 0.65
    for sd in (-1, 1): rail(m, mp, sd, 0, c0)                                      # stem
    rung(m, mp, 0.125)
    B(m, S, mp, (-HW+RT, HW-RT), (c0+RT, c1-RT), (-HH, -HH+BASE))                  # pad
    conns = [conn(mp, "Conn_In", 0, 0, 0, 0, 1, 0)]
    def arm(sd, with_north):
        B(m, S, mp, (sd*HW, sd*0.5), (c0, c0+RT), (-HH, HH))                       # south rail
        if with_north: B(m, S, mp, (sd*HW, sd*0.5), (c1-RT, c1), (-HH, HH))        # north rail
        rung_arm(m, mp, sd*0.375, c0+RT, c1-RT)
        B(m, S, mp, (sd*(HW-RT), sd*HW), (c0, c0+RT), (-HH, HH))                   # inner corner post (south)
        if with_north: B(m, S, mp, (sd*(HW-RT), sd*HW), (c1-RT, c1), (-HH, HH))    # inner corner post (north)
    if kind == "corner":
        B(m, S, mp, (HW-RT, HW), (c0, c1), (-HH, HH))                              # outer rail (right side)
        B(m, S, mp, (-0.5, HW), (c1-RT, c1), (-HH, HH))                            # far rail
        arm(-1, False)
        conns.append(conn(mp, "Conn_Out", -0.5, 0.5, 0, -1, 0, 0))
    elif kind == "tee":
        B(m, S, mp, (-0.5, 0.5), (c1-RT, c1), (-HH, HH))                           # far rail across the full 1 m
        arm(-1, False); arm(1, False)
        conns += [conn(mp, "Conn_Out_L", -0.5, 0.5, 0, -1, 0, 0), conn(mp, "Conn_Out_R", 0.5, 0.5, 0, 1, 0, 0)]
    else:
        arm(-1, True); arm(1, True)
        for sd in (-1, 1): rail(m, mp, sd, c1, 1.0)
        rung(m, mp, 0.875)
        conns += [conn(mp, "Conn_Out_L", -0.5, 0.5, 0, -1, 0, 0), conn(mp, "Conn_Out_R", 0.5, 0.5, 0, 1, 0, 0),
                  conn(mp, "Conn_Out_F", 0, 1, 0, 0, 1, 0)]
    return Node(name, m, children=conns, extras={"cell": "1x1 m", "kind": kind})

def cover():
    m = Mesh("CableTray_Cover")
    B(m, C, HZ, (-HW-0.01, HW+0.01), (0, 1), (HH, HH+0.01))
    for sd in (-1, 1): B(m, C, HZ, (sd*HW, sd*(HW+0.01)), (0, 1), (HH-0.02, HH), ("h+",))
    return Node("CableTray_Cover", m, extras={"run": 1.0, "note": "sits on top of a 1 m straight"})

def end_cap():
    m = Mesh("CableTray_End")
    B(m, S, HZ, (-HW, HW), (0, 0.012), (-HH, HH))
    return Node("CableTray_End", m, extras={"note": "local +Z faces the tray; plate extends along -Z"})

def support():
    m = Mesh("CableTray_Support"); top = 0.55
    B(m, D, HZ, (-0.176, 0.176), (-0.02, 0.02), (-HH-BASE, -HH))                    # strap under tray
    for sd in (-1, 1):
        B(m, D, HZ, (sd*0.164, sd*0.176), (-0.006, 0.006), (-HH, top-0.01))         # rod
        B(m, D, HZ, (sd*0.14, sd*0.20), (-0.03, 0.03), (top-0.01, top))             # ceiling plate
    return Node("CableTray_Support", m, extras={"ceiling_offset_y": top, "note": "trapeze hanger; place anywhere along a ceiling tray"})

def ring(m, mat, x_or_y_outer, x_or_y_inner, zr, plane):   # helper unused placeholder
    pass

def pass_vertical(name, up):
    m = Mesh(name); s = 1 if up else -1; O, K, F = 0.17, 0.19, 0.25; fh = 0.01; kh = 0.05 if up else 0.04
    def Y(a, b): return (min(s*a, s*b), max(s*a, s*b))
    def bx(mat, x, y, z): m.box(mat, (x[0], y[0], z[0]), (x[1], y[1], z[1]))
    for mat, (lo, hi), (y0, y1) in ((S, (K, F), (0, fh)),):
        bx(mat, (-F, F), Y(y0, y1), (K, F)); bx(mat, (-F, F), Y(y0, y1), (-F, -K))
        bx(mat, (-F, -K), Y(y0, y1), (-K, K)); bx(mat, (K, F), Y(y0, y1), (-K, K))
    bx(D, (-K, K), Y(0, kh), (O, K)); bx(D, (-K, K), Y(0, kh), (-K, -O))
    bx(D, (-K, -O), Y(0, kh), (-O, O)); bx(D, (O, K), Y(0, kh), (-O, O))
    return Node(name, m, extras={"opening": "0.34 x 0.34", "origin": "center of opening on the slab surface"})

def pass_wall():
    m = Mesh("CablePass_Wall"); xo, yo, xk, yk, xf, yf, T = 0.17, 0.07, 0.19, 0.09, 0.25, 0.15, 0.20
    def bx(mat, x, y, z): m.box(mat, (x[0], y[0], z[0]), (x[1], y[1], z[1]))
    for z0, z1 in ((0, 0.01), (-T-0.01, -T)):
        bx(S, (-xf, xf), (yk, yf), (z0, z1)); bx(S, (-xf, xf), (-yf, -yk), (z0, z1))
        bx(S, (-xf, -xk), (-yk, yk), (z0, z1)); bx(S, (xk, xf), (-yk, yk), (z0, z1))
    bx(D, (-xk, xk), (yo, yk), (-T, 0)); bx(D, (-xk, xk), (-yk, -yo), (-T, 0))
    bx(D, (-xk, -xo), (-yo, yo), (-T, 0)); bx(D, (xo, xk), (-yo, yo), (-T, 0))
    return Node("CablePass_Wall", m, extras={"opening": "0.34 x 0.14", "wall_thickness": T,
                                             "origin": "opening center on the room-side wall face; wall extends to -Z"})

# ---------------------------------------------------------------- library
LIB = {
    "CableTray_Ceiling_Straight": straight("CableTray_Ceiling_Straight", HZ, "ceiling"),
    "CableTray_Wall_Straight":    straight("CableTray_Wall_Straight", WALL, "wall"),
    "CableTray_Floor_Straight":   straight("CableTray_Floor_Straight", HZ, "floor"),
    "CableTray_Vertical":         straight("CableTray_Vertical", VERT, "vertical"),
    "CableTray_Corner90":         junction("CableTray_Corner90", HZ, "corner"),
    "CableTray_T":                junction("CableTray_T", HZ, "tee"),
    "CableTray_Cross":            junction("CableTray_Cross", HZ, "cross"),
    "CableTray_Transition":       junction("CableTray_Transition", VERT, "corner"),
    "CableTray_Support":          support(),
    "CableTray_Cover":            cover(),
    "CableTray_End":              end_cap(),
    "CablePass_Floor":            pass_vertical("CablePass_Floor", True),
    "CablePass_Wall":             pass_wall(),
    "CablePass_Ceiling":          pass_vertical("CablePass_Ceiling", False),
}
ORDER = list(LIB)
def fresh(k):   # new Node wrapper sharing the mesh (so exports don't share Node objects)
    n = LIB[k]; return Node(n.name, n.mesh, children=list(n.children), extras=n.extras)
for k in ORDER: write_glb(f"{OUT}/assets/{k}.glb", [fresh(k)], k)

sheet = []
for i, k in enumerate(ORDER):
    n = fresh(k); n.t = ((i % 7)*1.8, 0, -(i//7)*2.2); sheet.append(n)
write_glb(f"{OUT}/Kit_Sheet.glb", sheet, "Kit_Sheet")

# ---------------------------------------------------------------- assembly test
def qy(d): h = math.radians(d)/2; return (0, math.sin(h), 0, math.cos(h))
def qz(d): h = math.radians(d)/2; return (0, 0, math.sin(h), math.cos(h))
asm = []; REC = {}
def inst(label, key, t, ry=0, rot=None):
    n = Node(label, LIB[key].mesh, t=t, ry=ry)
    if rot: n.rot = rot
    asm.append(n); REC[label] = (key, t, ry)
def wconn(label, cname):
    key, t, ry = REC[label]
    for c in LIB[key].children:
        if c.name == cname:
            p, d = c.t, c.extras["travel_dir"]; h = math.radians(ry); cs, sn = math.cos(h), math.sin(h)
            rot = lambda v: (v[0]*cs+v[2]*sn, v[1], -v[0]*sn+v[2]*cs)
            P = rot(p); Dv = rot(d)
            return (P[0]+t[0], P[1]+t[1], P[2]+t[2]), Dv
    raise KeyError((label, cname))

Y = 3.5
inst("Cross", "CableTray_Cross", (0, Y, 1.0))
inst("Ceil_A", "CableTray_Ceiling_Straight", (0, Y, 0.0))
inst("Corner", "CableTray_Corner90", (0, Y, -1.0))
inst("Ceil_B", "CableTray_Ceiling_Straight", (-0.5, Y, -1.5), 90)
inst("Tee", "CableTray_T", (-1.5, Y, -1.5), 90)
for lab, pos, ry in (("End_CrossIn", (0, Y, 1.0), 180), ("End_CrossL", (-0.5, Y, 0.5), 90), ("End_CrossR", (0.5, Y, 0.5), -90),
                     ("End_TeeL", (-2.0, Y, -1.0), 180), ("End_TeeR", (-2.0, Y, -2.0), 0)):
    inst(lab, "CableTray_End", pos, ry)
inst("Cover_A", "CableTray_Cover", (0, Y, 0.0)); inst("Cover_B", "CableTray_Cover", (-0.5, Y, -1.5), 90)
inst("Support_A", "CableTray_Support", (0, Y, -0.5)); inst("Support_B", "CableTray_Support", (-1.0, Y, -1.5), 90)
# floor run
inst("Floor_A", "CableTray_Floor_Straight", (-4, 0.05, 0.0)); inst("Floor_B", "CableTray_Floor_Straight", (-4, 0.05, -1.0))
inst("End_Floor0", "CableTray_End", (-4, 0.05, 0.0), 180); inst("End_Floor1", "CableTray_End", (-4, 0.05, -2.0))
# wall run (wall face x=3, centerline x=3.05)
wx = 3.05
inst("Vert_A", "CableTray_Vertical", (wx, 0, 0)); inst("Vert_B", "CableTray_Vertical", (wx, 1, 0))
inst("Trans", "CableTray_Transition", (wx, 2, 0))
inst("Wall_A", "CableTray_Wall_Straight", (wx, 2.5, -0.5))
inst("End_Wall", "CableTray_End", (wx, 2.5, -1.5), 0, qz(-90))
# riser through floor and ceiling
for i in range(4): inst(f"Riser_{i}", "CableTray_Vertical", (6, i, 0))
inst("Pass_Floor", "CablePass_Floor", (6, 0, 0)); inst("Pass_Ceil", "CablePass_Ceiling", (6, 3.0, 0))
# through-wall run (wall plane z=0)
inst("Wall_Run", "CableTray_Ceiling_Straight", (8, 1.5, 0.5)); inst("Pass_Wall", "CablePass_Wall", (8, 1.5, 0))
write_glb(f"{OUT}/Assembly_Test.glb", asm, "Assembly_Test")

# ---------------------------------------------------------------- validation
def bounds(me):
    P = [v for pr in me.p.values() for v in pr["pos"]]
    return [min(v[i] for v in P) for i in range(3)], [max(v[i] for v in P) for i in range(3)]
def tris(me): return sum(len(pr["idx"])//3 for pr in me.p.values())
def badn(me):
    n = 0
    for pr in me.p.values():
        for i in range(0, len(pr["idx"]), 3):
            a, b, c = [pr["pos"][k] for k in pr["idx"][i:i+3]]
            if dot(cross(sub(b, a), sub(c, a)), pr["nor"][pr["idx"][i]]) <= 0: n += 1
    return n
def vol(me):
    t = 0
    for pr in me.p.values():
        for i in range(0, len(pr["idx"]), 3):
            a, b, c = [pr["pos"][k] for k in pr["idx"][i:i+3]]; t += dot(a, cross(b, c))/6
    return t
print(f"{'asset':28}{'min':>26}{'max':>26}{'tris':>6}{'mats':>5} bad vol")
tot = 0
for k in ORDER:
    me = LIB[k].mesh; mn, mx = bounds(me); tot += tris(me)
    print(f"{k:28}{str(tuple(round(c,3) for c in mn)):>26}{str(tuple(round(c,3) for c in mx)):>26}{tris(me):>6}{len(me.p):>5} {badn(me)} {'OK' if vol(me)>0 else 'NEG'}")
print("total tris:", tot)
pairs = [("Cross", "Conn_Out_F", "Ceil_A", "Conn_In"), ("Ceil_A", "Conn_Out", "Corner", "Conn_In"),
         ("Corner", "Conn_Out", "Ceil_B", "Conn_In"), ("Ceil_B", "Conn_Out", "Tee", "Conn_In"),
         ("Floor_A", "Conn_Out", "Floor_B", "Conn_In"), ("Vert_A", "Conn_Out", "Vert_B", "Conn_In"),
         ("Vert_B", "Conn_Out", "Trans", "Conn_In"), ("Trans", "Conn_Out", "Wall_A", "Conn_In")]
for i in range(3): pairs.append((f"Riser_{i}", "Conn_Out", f"Riser_{i+1}", "Conn_In"))
worst = 0
for a, ca, b, cb in pairs:
    pa, da = wconn(a, ca); pb, db = wconn(b, cb)
    dist = math.dist(pa, pb); same = all(abs(x-y) < 1e-6 for x, y in zip(da, db)); worst = max(worst, dist)
    print(f"  {a}.{ca} -> {b}.{cb}: gap={dist:.6f} m  direction match={same}")
print("worst connection gap:", worst)
