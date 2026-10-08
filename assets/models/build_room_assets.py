#!/usr/bin/env python3
"""
Data-center room environment kit  ->  12 GLB files (glTF 2.0, meters, Y-up)

GLOBAL CONVENTIONS
  * Grid = 1.0 m. Raised-floor finished surface = FLOOR_H (0.30 m) above the slab (y=0 = slab).
  * FRONT / exposed side = +Z.  Right = +X.  Rotate assets about Y in 90-degree steps
    (Godot: rotation.y = +90deg maps +Z -> +X).
  * Floor assets (panel / edge / corner / access): origin = bottom-centre of the 1x1 m cell, at slab level.
  * Props (platform, carts, bench, cabinet, bin): origin = bottom-centre of footprint, floor surface = local y=0.
    Place them at y = FLOOR_H when standing on the raised floor.
  * Wall panels: origin = centre of the BACK (mounting) face; panel extends +Z (outward). Place at y = height/2.
  * Each asset carries one 'Collision-convcolonly' box node (Godot turns it into a StaticBody3D + convex shape).
"""
import math, json, struct, zlib, os, sys, random

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
GRID, FLOOR_H = 1.0, 0.30

# ------------------------------------------------------------------ helpers
def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def norm(a):
    l = math.sqrt(dot(a, a)); return (a[0]/l, a[1]/l, a[2]/l)

def png_bytes(w, h, px):
    raw = b"".join(b"\x00" + bytes(c for p in row for c in p) for row in px)
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))

def floor_texture():
    """One tile = one 1m cell. 1px dark outer seam + 1px light inner bevel; subtle speckle."""
    S, rnd = 128, random.Random(7)
    px = []
    for y in range(S):
        row = []
        for x in range(S):
            e = min(x, y, S - 1 - x, S - 1 - y)
            if e == 0:   c = (74, 78, 84)
            elif e == 1: c = (178, 181, 186)
            else:
                v = 158 + rnd.randint(-5, 5); c = (v, v + 3, v + 7)
            row.append((*c, 255))
        px.append(row)
    return png_bytes(S, S, px)

def vent_texture():
    S = 16
    px = [[(10, 11, 14, 255) if (3 <= y < 12 and 2 <= x < 2 * S - 2) else (10, 11, 14, 0)
           for x in range(2 * S)] for y in range(S)]
    return png_bytes(2 * S, S, px)

TEXTURES = {"floor": floor_texture, "vent": vent_texture}

# ------------------------------------------------------------------ materials
MATS = {
    "M_Floor":       dict(color=(1, 1, 1), metal=0.10, rough=0.60, tex="floor"),
    "M_FloorAccess": dict(color=(0.70, 0.78, 0.86), metal=0.10, rough=0.60, tex="floor"),
    "M_FloorSide":   dict(color=(0.080, 0.085, 0.090), metal=0.10, rough=0.80),
    "M_Metal":       dict(color=(0.450, 0.470, 0.500), metal=0.90, rough=0.35),
    "M_Frame":       dict(color=(0.035, 0.038, 0.045), metal=0.70, rough=0.50),
    "M_Dark":        dict(color=(0.006, 0.007, 0.009), metal=0.10, rough=0.65),
    "M_Trim":        dict(color=(1, 1, 1), metal=0.20, rough=0.50, vc=True),
    "M_Wall":        dict(color=(0.420, 0.440, 0.470), metal=0.10, rough=0.60),
    "M_Deck":        dict(color=(0.180, 0.200, 0.220), metal=0.20, rough=0.55),
    "M_Cabinet":     dict(color=(0.070, 0.085, 0.100), metal=0.40, rough=0.50),
    "M_Acoustic":    dict(color=(0.025, 0.060, 0.070), metal=0.00, rough=1.00),
    "M_Bin":         dict(color=(0.045, 0.050, 0.055), metal=0.05, rough=0.60),
    "M_Vent":        dict(color=(1, 1, 1), metal=0.10, rough=0.70, tex="vent", mask=True),
}
VC = {k for k, v in MATS.items() if v.get("vc")}
TEXTURED = {k for k, v in MATS.items() if "tex" in v}

TEAL   = (0.00, 0.20, 0.25, 1)
YELLOW = (0.80, 0.52, 0.00, 1)
ESD    = (0.015, 0.110, 0.055, 1)
GREENB = (0.02, 0.45, 0.10, 1)
DARKC  = (0.010, 0.012, 0.015, 1)

# ------------------------------------------------------------------ mesh builder
class Mesh:
    def __init__(self, name):
        self.name, self.prims = name, {}

    def poly(self, mat, pts, n=None, uv=None, col=None):
        if n is None:                                    # derive normal; caller guarantees outward winding via hint
            raise ValueError("normal required")
        g = cross(vsub(pts[1], pts[0]), vsub(pts[2], pts[0]))
        if dot(g, n) < 0:
            pts = pts[::-1]; uv = uv[::-1] if uv else None
        d = self.prims.setdefault(mat, dict(p=[], n=[], uv=[], c=[], i=[]))
        b = len(d["p"])
        d["p"] += pts; d["n"] += [n] * len(pts)
        d["uv"] += uv if uv else [(0.5, 0.5)] * len(pts)
        d["c"] += [col or (1, 1, 1, 1)] * len(pts)
        for k in range(1, len(pts) - 1):
            d["i"] += [b, b + k, b + k + 1]

    def quad_up(self, mat, x0, z0, x1, z1, y, uvf=None, col=None):
        pts = [(x0,y,z1),(x1,y,z1),(x1,y,z0),(x0,y,z0)]
        self.poly(mat, pts, (0, 1, 0), [uvf(p) for p in pts] if uvf else None, col)

    def box(self, mat, x0, y0, z0, x1, y1, z1, skip=(), col=None):
        F = {
            "+x": ([(x1,y0,z1),(x1,y0,z0),(x1,y1,z0),(x1,y1,z1)], (1,0,0)),
            "-x": ([(x0,y0,z0),(x0,y0,z1),(x0,y1,z1),(x0,y1,z0)], (-1,0,0)),
            "+y": ([(x0,y1,z1),(x1,y1,z1),(x1,y1,z0),(x0,y1,z0)], (0,1,0)),
            "-y": ([(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)], (0,-1,0)),
            "+z": ([(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)], (0,0,1)),
            "-z": ([(x1,y0,z0),(x0,y0,z0),(x0,y1,z0),(x1,y1,z0)], (0,0,-1)),
        }
        for k, (p, n) in F.items():
            if k not in skip: self.poly(mat, p, n, None, col)

    def cyl(self, mat, axis, c, r, h0, h1, sides=8, cap0=True, cap1=True, col=None):
        def P(a, h):
            ca, sa = r * math.cos(a), r * math.sin(a)
            if axis == "y": return (c[0] + ca, h, c[1] + sa)
            if axis == "z": return (c[0] + ca, c[1] + sa, h)
            return (h, c[0] + ca, c[1] + sa)
        def A(h):
            if axis == "y": return (c[0], h, c[1])
            if axis == "z": return (c[0], c[1], h)
            return (h, c[0], c[1])
        ax = {"x": (1,0,0), "y": (0,1,0), "z": (0,0,1)}[axis]
        st = 2 * math.pi / sides
        for i in range(sides):
            a0, a1 = i * st, (i + 1) * st
            self.poly(mat, [P(a0,h0), P(a1,h0), P(a1,h1), P(a0,h1)], norm(vsub(P((a0+a1)/2, h0), A(h0))), None, col)
        if cap1: self.poly(mat, [P(i*st, h1) for i in range(sides)], ax, None, col)
        if cap0: self.poly(mat, [P(i*st, h0) for i in range(sides)], (-ax[0], -ax[1], -ax[2]), None, col)

    def slanted(self, mat, pts, hint, col=None):
        """Quad/tri with computed normal, flipped to agree with hint direction."""
        n = norm(cross(vsub(pts[1], pts[0]), vsub(pts[2], pts[0])))
        if dot(n, hint) < 0: n = (-n[0], -n[1], -n[2])
        self.poly(mat, pts, n, None, col)

    def frustum(self, mat, yb, yt, hb, ht, z_off=0.0):
        """Square tapered body: half-size hb at yb, ht at yt (sides only)."""
        B = [(-hb,yb,-hb),(hb,yb,-hb),(hb,yb,hb),(-hb,yb,hb)]
        T = [(-ht,yt,-ht),(ht,yt,-ht),(ht,yt,ht),(-ht,yt,ht)]
        for i in range(4):
            j = (i + 1) % 4
            mid = ((B[i][0]+B[j][0])/2, 0, (B[i][2]+B[j][2])/2)
            self.slanted(mat, [B[i], B[j], T[j], T[i]], mid)

    def tris(self): return sum(len(d["i"]) // 3 for d in self.prims.values())

    def bbox(self):
        P = [p for d in self.prims.values() for p in d["p"]]
        return [min(p[i] for p in P) for i in range(3)], [max(p[i] for p in P) for i in range(3)]

class Node:
    def __init__(s, name, mesh=None, t=(0, 0, 0), q=(0, 0, 0, 1), extras=None):
        s.name, s.mesh, s.t, s.q, s.extras, s.kids = name, mesh, t, q, extras, []

def finish(root, pivot, extra=None, custom_col=None):
    """Attach collision box (from visual bbox) and metadata."""
    bb0, bb1 = root.mesh.bbox() if root.mesh else ((0,0,0),(0,0,0))
    for k in root.kids:                                       # include animated children in bbox
        if k.mesh:
            a, b = k.mesh.bbox()
            bb0 = [min(bb0[i], a[i] + k.t[i]) for i in range(3)]; bb1 = [max(bb1[i], b[i] + k.t[i]) for i in range(3)]
    bb0 = [bb0[0], min(bb0[1], 0.0), bb0[2]]                  # collision always reaches slab/floor level
    if custom_col:
        for nm, cm in custom_col: root.kids.append(Node(nm, cm))
    else:
        cm = Mesh(root.name + "_CollisionMesh")
        cm.box("M_Dark", bb0[0], bb0[1], bb0[2], bb1[0], bb1[1], bb1[2])
        root.kids.append(Node("Collision-convcolonly", cm))
    root.extras = dict(asset=root.name, size_m=[round(bb1[i] - bb0[i], 4) for i in (0, 1, 2)],
                       bbox_min=[round(v, 4) for v in bb0], bbox_max=[round(v, 4) for v in bb1],
                       pivot=pivot, front="+Z", grid_m=GRID, **(extra or {}))
    return root

# ================================================================== FLOOR (1 m grid)
UVF = lambda p: (p[0] + 0.5, p[2] + 0.5)          # world-continuous tile UV (u from x, v from z)
TRIM_W = 0.04

def build_floor_panel():
    m = Mesh("Floor_Panel_1m")
    m.quad_up("M_Floor", -0.5, -0.5, 0.5, 0.5, FLOOR_H, UVF)
    return finish(Node("Floor_Panel_1m", m), "bottom-centre of 1x1 m cell, slab level; top surface y=0.30",
                  dict(note="top-surface only (hollow by design); seams are in the texture"))

def build_floor_edge():
    m = Mesh("Floor_Edge_1m"); t = TRIM_W; H = FLOOR_H
    m.quad_up("M_Floor", -0.5, -0.5, 0.5, 0.5 - t, H, UVF)
    m.box("M_Metal", -0.5, H - 0.008, 0.5 - t, 0.5, H + 0.002, 0.5, skip=("-x", "+x", "-y"))
    m.poly("M_FloorSide", [(-0.5, 0, 0.5), (0.5, 0, 0.5), (0.5, H - 0.008, 0.5), (-0.5, H - 0.008, 0.5)], (0, 0, 1))
    return finish(Node("Floor_Edge_1m", m), "bottom-centre of 1x1 m cell; exposed side faces +Z",
                  dict(exposed=["+Z"]))

def build_floor_corner():
    m = Mesh("Floor_Corner_1m"); t = TRIM_W; H = FLOOR_H
    m.quad_up("M_Floor", -0.5, -0.5, 0.5 - t, 0.5 - t, H, UVF)
    m.box("M_Metal", -0.5, H - 0.008, 0.5 - t, 0.5, H + 0.002, 0.5, skip=("-x", "-y"))          # +Z trim (with corner cap)
    m.box("M_Metal", 0.5 - t, H - 0.008, -0.5, 0.5, H + 0.002, 0.5 - t, skip=("-z", "+z", "-y"))  # +X trim
    m.poly("M_FloorSide", [(-0.5, 0, 0.5), (0.5, 0, 0.5), (0.5, H - 0.008, 0.5), (-0.5, H - 0.008, 0.5)], (0, 0, 1))
    m.poly("M_FloorSide", [(0.5, 0, -0.5), (0.5, 0, 0.5), (0.5, H - 0.008, 0.5), (0.5, H - 0.008, -0.5)], (1, 0, 0))
    return finish(Node("Floor_Corner_1m", m), "bottom-centre of 1x1 m cell; exposed sides face +Z and +X",
                  dict(exposed=["+Z", "+X"]))

def build_floor_access():
    m = Mesh("Floor_AccessPanel_1m"); H = FLOOR_H; fw = 0.03; top = H + 0.0004
    # recessed lift-out insert + raised metal frame
    m.quad_up("M_FloorAccess", -0.5 + fw, -0.5 + fw, 0.5 - fw, 0.5 - fw, H - 0.0005, UVF)
    m.box("M_Metal", -0.5, H - 0.004, 0.5 - fw, 0.5, top, 0.5, skip=("-y",))
    m.box("M_Metal", -0.5, H - 0.004, -0.5, 0.5, top, -0.5 + fw, skip=("-y",))
    m.box("M_Metal", -0.5, H - 0.004, -0.5 + fw, -0.5 + fw, top, 0.5 - fw, skip=("-y",))
    m.box("M_Metal", 0.5 - fw, H - 0.004, -0.5 + fw, 0.5, top, 0.5 - fw, skip=("-y",))
    for sx in (-1, 1):                                              # two recessed lift cups
        m.cyl("M_Metal", "y", (sx * 0.28, 0.0), 0.040, H - 0.003, top + 0.0002, sides=8, cap0=False)
        m.cyl("M_Dark", "y", (sx * 0.28, 0.0), 0.028, top + 0.0002, top + 0.0004, sides=8, cap0=False)
    return finish(Node("Floor_AccessPanel_1m", m), "bottom-centre of 1x1 m cell, slab level; top surface y=0.30",
                  dict(note="lift-out insert with frame and two lift cups; swap with Floor_Panel_1m to 'remove'"))

# ================================================================== WALL PANELS (origin = back-face centre)
def build_wall_technical():
    m = Mesh("WallPanel_Technical"); H2 = 1.5; D = 0.07
    m.box("M_Wall", -0.5, -H2, 0, 0.5, H2, D, skip=("-z",))
    for x0, x1 in ((-0.5, -0.496), (0.496, 0.5)):                                   # vertical joint grooves
        m.poly("M_Dark", [(x0, -H2 + 0.15, D + 0.0003), (x1, -H2 + 0.15, D + 0.0003),
                          (x1, H2 - 0.04, D + 0.0003), (x0, H2 - 0.04, D + 0.0003)], (0, 0, 1))
    m.box("M_Frame", -0.5, -H2, 0, 0.5, -H2 + 0.15, D + 0.015, skip=("-z", "-y", "-x", "+x"))   # plinth
    m.box("M_Frame", -0.5, H2 - 0.04, 0, 0.5, H2, D + 0.010, skip=("-z", "+y", "-x", "+x"))     # top trim
    m.box("M_Metal", -0.5, -0.35, D, 0.5, -0.25, D + 0.030, skip=("-z", "-x", "+x"))            # cable trunking
    m.poly("M_Dark", [(-0.5, -0.303, D + 0.0303), (0.5, -0.303, D + 0.0303),
                      (0.5, -0.297, D + 0.0303), (-0.5, -0.297, D + 0.0303)], (0, 0, 1))
    for sx in (-1, 1):                                                                # fixing bolts
        for y in (-1.0, 0.9):
            m.cyl("M_Metal", "z", (sx * 0.42, y), 0.012, D, D + 0.004, sides=6, cap0=False)
    return finish(Node("WallPanel_Technical", m), "centre of back (mounting) face; panel extends +Z; place at y=1.5 for floor-to-3m",
                  dict(modular_width_m=1.0, height_m=3.0))

def build_wall_acoustic():
    m = Mesh("WallPanel_Acoustic"); H2 = 1.0; D = 0.07; fw = 0.03
    m.box("M_Frame", -0.5, -H2, 0, 0.5, -H2 + fw, D, skip=("-z",))
    m.box("M_Frame", -0.5, H2 - fw, 0, 0.5, H2, D, skip=("-z",))
    m.box("M_Frame", -0.5, -H2 + fw, 0, -0.5 + fw, H2 - fw, D, skip=("-z", "-y", "+y"))
    m.box("M_Frame", 0.5 - fw, -H2 + fw, 0, 0.5, H2 - fw, D, skip=("-z", "-y", "+y"))
    n, x0, w = 12, -0.5 + fw, (1.0 - 2 * fw) / 12
    y0, y1, zb, za = -H2 + fw, H2 - fw, 0.02, 0.06
    for i in range(n):                                                                 # triangular absorber wedges
        a, b = x0 + i * w, x0 + (i + 1) * w
        for (p, q, hint) in ((a, (a + b) / 2, (-1, 0, 1)), ((a + b) / 2, b, (1, 0, 1))):
            m.slanted("M_Acoustic", [(p, y0, zb if p == a else za), (q, y0, za if p == a else zb),
                                     (q, y1, za if p == a else zb), (p, y1, zb if p == a else za)], hint)
    return finish(Node("WallPanel_Acoustic", m), "centre of back (mounting) face; panel extends +Z; place at y=1.0+height above floor",
                  dict(modular_width_m=1.0, height_m=2.0))

# ================================================================== STAGING PLATFORM (2 x 1 m)
def build_staging_platform():
    m = Mesh("Staging_Platform"); L, Dp, top = 1.0, 0.5, 0.20
    m.box("M_Deck", -L, top - 0.04, -Dp, L, top, Dp)
    for sz in (-1, 1):                                                                 # apron beams
        z0, z1 = (Dp - 0.05, Dp) if sz > 0 else (-Dp, -Dp + 0.05)
        m.box("M_Frame", -L, 0.08, z0, L, top - 0.04, z1, skip=("+y",))
    for sx in (-1, 1):
        x0, x1 = (L - 0.05, L) if sx > 0 else (-L, -L + 0.05)
        m.box("M_Frame", x0, 0.08, -Dp + 0.05, x1, top - 0.04, Dp - 0.05, skip=("+y",))
    for x in (-L + 0.04, 0.0, L - 0.04):
        for sz in (-1, 1):
            z = sz * (Dp - 0.04)
            m.box("M_Frame", x - 0.04, 0, z - 0.04, x + 0.04, 0.08, z + 0.04, skip=("-y", "+y"))
    for (x0, z0, x1, z1) in ((-L + 0.03, -Dp + 0.03, L - 0.03, -Dp + 0.09), (-L + 0.03, Dp - 0.09, L - 0.03, Dp - 0.03),
                             (-L + 0.03, -Dp + 0.09, -L + 0.09, Dp - 0.09), (L - 0.09, -Dp + 0.09, L - 0.03, Dp - 0.09)):
        m.quad_up("M_Trim", x0, z0, x1, z1, top + 0.0008, None, YELLOW)                 # hazard border
    m.quad_up("M_Trim", -L + 0.09, -Dp + 0.09, L - 0.09, Dp - 0.09, top + 0.0006, None, DARKC)   # mat
    ramp_len = 0.75                                                                     # +Z loading ramp (width 1 m)
    zr = Dp + ramp_len
    m.slanted("M_Deck", [(-0.5, top, Dp), (0.5, top, Dp), (0.5, 0, zr), (-0.5, 0, zr)], (0, 1, 0))
    for sx in (-1, 1):
        m.slanted("M_Frame", [(sx * 0.5, 0, Dp), (sx * 0.5, 0, zr), (sx * 0.5, top, Dp)], (sx, 0, 0))
    deck = Mesh("Staging_Deck_CollisionMesh"); deck.box("M_Dark", -L, 0, -Dp, L, top, Dp)
    rw = Mesh("Staging_Ramp_CollisionMesh")                                             # closed wedge
    rw.slanted("M_Dark", [(-0.5, top, Dp), (0.5, top, Dp), (0.5, 0, zr), (-0.5, 0, zr)], (0, 1, 0))
    rw.poly("M_Dark", [(-0.5, 0, Dp), (0.5, 0, Dp), (0.5, 0, zr), (-0.5, 0, zr)], (0, -1, 0))
    rw.poly("M_Dark", [(-0.5, 0, Dp), (0.5, 0, Dp), (0.5, top, Dp), (-0.5, top, Dp)], (0, 0, -1))
    for sx in (-1, 1):
        rw.slanted("M_Dark", [(sx * 0.5, 0, Dp), (sx * 0.5, 0, zr), (sx * 0.5, top, Dp)], (sx, 0, 0))
    return finish(Node("Staging_Platform", m), "bottom-centre of the 2x1 m deck footprint; ramp extends +Z beyond footprint",
                  dict(deck_height_m=top, ramp_axis="+Z", ramp_length_m=ramp_len, footprint_m=[2.0, 1.0]),
                  custom_col=[("Collision_Deck-convcolonly", deck), ("Collision_Ramp-convcolonly", rw)])

# ================================================================== CARTS
def casters(m, xs, zs, r, mount_y0, mount_y1):
    for cx in xs:
        for cz in zs:
            m.box("M_Frame", cx - 0.025, mount_y0, cz - 0.025, cx + 0.025, mount_y1, cz + 0.025, skip=("-y",))
            m.cyl("M_Dark", "x", (r, cz), r, cx - 0.015, cx + 0.015, sides=8)

def build_cart_small():
    m = Mesh("Cart_Small"); W, L = 0.55, 0.90
    m.box("M_Deck", -W/2, 0.14, -L/2, W/2, 0.17, L/2)
    m.box("M_Deck", -W/2, 0.70, -L/2, W/2, 0.73, L/2)
    for (a, b, c, d) in ((-W/2, -L/2, W/2, -L/2 + 0.01), (-W/2, L/2 - 0.01, W/2, L/2),
                         (-W/2, -L/2 + 0.01, -W/2 + 0.01, L/2 - 0.01), (W/2 - 0.01, -L/2 + 0.01, W/2, L/2 - 0.01)):
        m.box("M_Frame", a, 0.73, b, c, 0.755, d, skip=("-y",))                          # tray lips
    for sx in (-1, 1):
        for sz in (-1, 1):
            cx, cz = sx * (W/2 - 0.025), sz * (L/2 - 0.025)
            m.box("M_Frame", cx - 0.015, 0.17, cz - 0.015, cx + 0.015, 0.70, cz + 0.015, skip=("-y", "+y"))
    for sx in (-1, 1):                                                                   # push handle at rear (-Z)
        m.box("M_Frame", sx * 0.22 - 0.015, 0.73, -L/2 + 0.010, sx * 0.22 + 0.015, 0.92, -L/2 + 0.040, skip=("-y",))
    m.box("M_Trim", -0.235, 0.89, -L/2 + 0.005, 0.235, 0.92, -L/2 + 0.045, col=TEAL)
    casters(m, (-(W/2 - 0.04), W/2 - 0.04), (-(L/2 - 0.07), L/2 - 0.07), 0.05, 0.10, 0.14)
    return finish(Node("Cart_Small", m), "bottom-centre of wheelbase footprint; handle at -Z, front +Z",
                  dict(deck_height_m=0.73, deck_size_m=[0.55, 0.90]))

def build_trolley_server():
    m = Mesh("Trolley_Server")
    for sx in (-1, 1):                                                                   # base H-frame
        x0, x1 = (0.30, 0.35) if sx > 0 else (-0.35, -0.30)
        m.box("M_Frame", x0, 0.10, -0.45, x1, 0.16, 0.55)
    m.box("M_Frame", -0.30, 0.10, -0.45, 0.30, 0.16, -0.38)
    m.box("M_Frame", -0.30, 0.10, 0.45, 0.30, 0.16, 0.55)
    for cx in (-0.325, 0.325):                                                           # casters r=0.06 under base
        for cz in (-0.40, 0.50):
            m.box("M_Frame", cx - 0.03, 0.12 - 0.02, cz - 0.03, cx + 0.03, 0.10, cz + 0.03, skip=("-y",))
            m.cyl("M_Dark", "x", (0.06, cz), 0.06, cx - 0.015, cx + 0.015, sides=8)
    for sx in (-1, 1):                                                                   # mast uprights
        x0, x1 = (0.225, 0.275) if sx > 0 else (-0.275, -0.225)
        m.box("M_Frame", x0, 0.16, -0.43, x1, 1.55, -0.37, skip=("-y",))
    m.box("M_Frame", -0.275, 1.49, -0.43, 0.275, 1.55, -0.37)
    m.box("M_Frame", -0.275, 0.16, -0.43, 0.275, 0.24, -0.37)
    m.cyl("M_Metal", "x", (0.95, -0.40), 0.012, 0.275, 0.375, sides=6)                    # crank
    m.box("M_Trim", 0.360, 0.89, -0.415, 0.378, 0.99, -0.385, col=TEAL)
    plat = Mesh("Trolley_Platform")
    plat.box("M_Deck", -0.31, 0.0, -0.35, 0.31, 0.03, 0.55)
    for sx in (-1, 1):
        x0, x1 = (0.29, 0.31) if sx > 0 else (-0.31, -0.29)
        plat.box("M_Frame", x0, 0.03, -0.35, x1, 0.07, 0.55, skip=("-y",))
    plat.box("M_Frame", -0.25, -0.10, -0.38, 0.25, 0.18, -0.35, skip=("+z",))             # carriage on mast
    plat.quad_up("M_Trim", -0.28, -0.30, 0.28, 0.50, 0.0308, None, DARKC)
    plat.quad_up("M_Trim", -0.28, 0.50, 0.28, 0.54, 0.0310, None, YELLOW)
    root = Node("Trolley_Server", m)
    root.kids.append(Node("Trolley_Platform", plat, (0, 0.75, 0),
                          extras=dict(slide_axis="Y", min_y=0.20, max_y=1.35, default_y=0.75,
                                      deck_size_m=[0.62, 0.90], clear_width_m=0.58)))
    return finish(root, "bottom-centre of base footprint; platform is a child node that slides on local Y; mast at -Z",
                  dict(platform_clear_width_m=0.58, platform_depth_m=0.90, fits="19in (482.6 mm) rack hardware up to ~800 mm deep"))

# ================================================================== MAINTENANCE
def build_workbench():
    m = Mesh("Workbench_Maintenance"); W2, D2 = 0.90, 0.375
    m.box("M_Deck", -W2, 0.86, -D2, W2, 0.90, D2)
    m.quad_up("M_Trim", -0.85, -0.30, 0.85, 0.28, 0.9006, None, ESD)                       # ESD mat
    for x in (-0.84,):
        for sz in (-1, 1):
            z = sz * 0.32
            m.box("M_Frame", x - 0.03, 0, z - 0.03, x + 0.03, 0.86, z + 0.03, skip=("-y", "+y"))
    m.box("M_Frame", -0.87, 0.80, -0.35, -0.81, 0.86, 0.35, skip=("+y",))
    m.box("M_Frame", -0.87, 0.18, -0.35, 0.28, 0.21, 0.35)                                  # lower shelf
    m.box("M_Frame", 0.28, 0.0, -0.36, 0.88, 0.86, 0.36, skip=("-y", "+y"))                 # drawer unit
    for (y0, y1) in ((0.14, 0.34), (0.36, 0.56), (0.58, 0.82)):
        m.box("M_Cabinet", 0.29, y0, 0.36, 0.87, y1, 0.366)
        m.box("M_Metal", 0.50, (y0 + y1) / 2 - 0.008, 0.366, 0.66, (y0 + y1) / 2 + 0.008, 0.382)
    m.box("M_Frame", -W2, 0.90, -D2, W2, 1.35, -D2 + 0.02, skip=("-y",))                    # back riser
    m.box("M_Frame", -0.80, 1.10, -D2 + 0.02, 0.80, 1.115, -0.28)                           # riser ledge
    return finish(Node("Workbench_Maintenance", m), "bottom-centre of footprint; front +Z, back riser at -Z",
                  dict(top_height_m=0.90))

def build_tool_cabinet():
    m = Mesh("Cabinet_Tool"); W2, D2 = 0.45, 0.25
    m.box("M_Frame", -0.43, 0, -0.23, 0.43, 0.06, 0.23, skip=("-y", "+y"))
    m.box("M_Cabinet", -W2, 0.06, -D2, W2, 1.80, D2, skip=("-y",))
    for (a, b) in ((-0.447, -0.003), (0.003, 0.447)):
        m.box("M_Cabinet", a, 0.09, D2, b, 1.77, D2 + 0.004, skip=("-z",))
    for x in (-0.03, 0.03):
        m.box("M_Metal", x - 0.008, 0.80, D2 + 0.004, x + 0.008, 1.20, D2 + 0.022, skip=("-z",))
    for x0, x1 in ((-0.38, -0.08), (0.08, 0.38)):                                           # vent slots
        pts = [(x0, 1.62, D2 + 0.0043), (x1, 1.62, D2 + 0.0043), (x1, 1.72, D2 + 0.0043), (x0, 1.72, D2 + 0.0043)]
        m.poly("M_Vent", pts, (0, 0, 1), [(p[0] / 0.008, p[1] / 0.008) for p in pts])
    m.poly("M_Trim", [(-0.447, 1.50, D2 + 0.0043), (0.447, 1.50, D2 + 0.0043),
                      (0.447, 1.52, D2 + 0.0043), (-0.447, 1.52, D2 + 0.0043)], (0, 0, 1), None, TEAL)
    return finish(Node("Cabinet_Tool", m), "bottom-centre of footprint; doors face +Z")

def build_waste_container():
    m = Mesh("Container_TechWaste")
    m.frustum("M_Bin", 0.06, 0.80, 0.26, 0.30)
    m.box("M_Frame", -0.31, 0.80, -0.31, 0.31, 0.84, 0.31)                                   # lid
    m.quad_up("M_Trim", -0.20, 0.08, 0.20, 0.16, 0.8408, None, DARKC)                       # board slot
    m.cyl("M_Trim", "y", (0.0, -0.12), 0.08, 0.8402, 0.8409, sides=8, cap0=False, col=DARKC)  # round opening
    zf = lambda y: 0.26 + (y - 0.06) / 0.74 * 0.04 + 0.002                                   # colour band on tapered front
    m.poly("M_Trim", [(-0.27, 0.52, zf(0.52)), (0.27, 0.52, zf(0.52)), (0.27, 0.62, zf(0.62)), (-0.27, 0.62, zf(0.62))],
           (0, 0.05, 1), None, GREENB)
    for sx in (-1, 1):
        m.cyl("M_Dark", "x", (0.05, -0.26), 0.05, sx * 0.30 - 0.015, sx * 0.30 + 0.015, sides=8)   # rear wheels
        m.box("M_Frame", sx * 0.22 - 0.03, 0.0, 0.20, sx * 0.22 + 0.03, 0.06, 0.26, skip=("+y",))  # front feet
    return finish(Node("Container_TechWaste", m), "bottom-centre of footprint; slot/lid face +Z, wheels at -Z")

# ------------------------------------------------------------------ GLB writer
def write_glb(root, path):
    meshes = {}
    def collect(n):
        if n.mesh: meshes[n.mesh.name] = n.mesh
        for k in n.kids: collect(k)
    collect(root)
    used = [k for k in MATS if any(k in m.prims for m in meshes.values())]
    tex_used = sorted({MATS[k]["tex"] for k in used if "tex" in MATS[k]})
    binb = bytearray(); views, accs = [], []
    def view(data, target=None):
        while len(binb) % 4: binb.append(0)
        views.append(dict(buffer=0, byteOffset=len(binb), byteLength=len(data), **({"target": target} if target else {})))
        binb.extend(data); return len(views) - 1
    def acc(v, ct, cnt, typ, mn=None, mx=None):
        a = dict(bufferView=v, componentType=ct, count=cnt, type=typ)
        if mn is not None: a["min"], a["max"] = mn, mx
        accs.append(a); return len(accs) - 1
    glm = {}
    for m in meshes.values():
        prims = []
        for mat, d in m.prims.items():
            P = d["p"]
            mn = [min(p[i] for p in P) for i in range(3)]; mx = [max(p[i] for p in P) for i in range(3)]
            at = {"POSITION": acc(view(b"".join(struct.pack("<3f", *p) for p in P), 34962), 5126, len(P), "VEC3", mn, mx),
                  "NORMAL":   acc(view(b"".join(struct.pack("<3f", *n) for n in d["n"]), 34962), 5126, len(P), "VEC3")}
            if mat in TEXTURED:
                at["TEXCOORD_0"] = acc(view(b"".join(struct.pack("<2f", *u) for u in d["uv"]), 34962), 5126, len(P), "VEC2")
            if mat in VC:
                at["COLOR_0"] = acc(view(b"".join(struct.pack("<4f", *c) for c in d["c"]), 34962), 5126, len(P), "VEC4")
            I = d["i"]; assert len(P) < 65536
            ia = acc(view(struct.pack(f"<{len(I)}H", *I), 34963), 5123, len(I), "SCALAR")
            prims.append(dict(attributes=at, indices=ia, material=used.index(mat), mode=4))
        glm[m.name] = dict(name=m.name, primitives=prims)
    mesh_idx = {k: i for i, k in enumerate(glm)}
    images = [dict(bufferView=view(TEXTURES[t]()), mimeType="image/png") for t in tex_used]
    materials = []
    for k in used:
        s = MATS[k]
        pbr = dict(baseColorFactor=[*s["color"], 1.0], metallicFactor=s["metal"], roughnessFactor=s["rough"])
        if "tex" in s: pbr["baseColorTexture"] = dict(index=tex_used.index(s["tex"]))
        mt = dict(name=k, pbrMetallicRoughness=pbr)
        if s.get("mask"): mt.update(alphaMode="MASK", alphaCutoff=0.5, doubleSided=True)
        materials.append(mt)
    flat = []
    def walk(n):
        i = len(flat); flat.append(None)
        kids = [walk(k) for k in n.kids]
        d = dict(name=n.name)
        if n.mesh: d["mesh"] = mesh_idx[n.mesh.name]
        if any(n.t): d["translation"] = [round(v, 6) for v in n.t]
        if n.q != (0, 0, 0, 1): d["rotation"] = list(n.q)
        if kids: d["children"] = kids
        if n.extras: d["extras"] = n.extras
        flat[i] = d; return i
    walk(root)
    gltf = dict(asset=dict(version="2.0", generator="build_room_assets.py"), scene=0, scenes=[dict(nodes=[0])],
                nodes=flat, meshes=list(glm.values()), materials=materials, accessors=accs, bufferViews=views,
                buffers=[dict(byteLength=len(binb))])
    if images:
        gltf["images"] = images
        gltf["textures"] = [dict(sampler=0, source=i) for i in range(len(images))]
        gltf["samplers"] = [dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)]
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4); binb += b"\x00" * (-len(binb) % 4)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(binb)))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(binb), b"BIN\x00")); f.write(binb)
    return meshes, os.path.getsize(path)

ASSETS = [build_floor_panel, build_floor_edge, build_floor_corner, build_floor_access,
          build_wall_technical, build_wall_acoustic, build_staging_platform,
          build_cart_small, build_trolley_server, build_workbench, build_tool_cabinet, build_waste_container]

if __name__ == "__main__":
    for fn in ASSETS:
        root = fn()
        meshes, size = write_glb(root, os.path.join(OUT, root.name + ".glb"))
        for m in meshes.values():
            for dd in m.prims.values():
                for k in range(0, len(dd["i"]), 3):
                    a, b, c = (dd["p"][j] for j in dd["i"][k:k+3])
                    assert dot(cross(vsub(b, a), vsub(c, a)), dd["n"][dd["i"][k]]) > 0, m.name
        tr = sum(m.tris() for m in meshes.values() if not m.name.endswith("_CollisionMesh"))
        sz = root.extras["size_m"]
        print(f"{root.name:<24}{size/1024:6.1f} KB {tr:>5} tris  {len(root.mesh.prims)} surf   "
              f"{sz[0]:.3f} x {sz[1]:.3f} x {sz[2]:.3f} m")
