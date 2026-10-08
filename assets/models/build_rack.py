#!/usr/bin/env python3
"""
Fictional 42U / 19-inch rack system generator  ->  Rack_42U.glb  (glTF 2.0, meters, Y-up)

Conventions (also in Rack_Spec.md / RackSpec.gd)
  * Rack origin: bottom-centre of the footprint (on the floor).
  * FRONT of the rack faces +Z (glTF/Blender standard). Up = +Y. Right (seen from front) = +X.
  * Front rail mounting plane  z = +ZF  (equipment ear BACK face sits here, ears extend toward +Z)
  * Rear  rail mounting plane  z = -ZR  (interior-facing face)
  * U1 bottom edge = Y_U0.  U n bottom = Y_U0 + (n-1)*U.
  * Fixed parts (frame, rails, panels, base, top, feet): identity transform, geometry in rack space.
  * Placeable modules (blanks, shelf, horizontal manager): origin = bottom-centre of their lowest U
    at the FRONT MOUNTING PLANE (x=0, y=slot bottom, z=0), body extends toward -Z.
  * Doors: origin = hinge axis at the door's bottom edge; door extends along local +X, outward = local +Z.
"""
import math, json, struct, zlib, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "."

# ------------------------------------------------------------------ spec (metres)
U        = 0.04445            # 1U
N_U      = 42
RACK_W   = 0.800
RACK_D   = 1.100
FOOT_H   = 0.070
BASE_TOP = 0.120
Y_U0     = 0.150              # bottom of U1
Y_UTOP   = Y_U0 + N_U * U     # 2.0169
OPEN_W   = 0.45085            # 17.75" clear opening between rails
PANEL_W  = 0.4826             # 19" panel width
HOLE_X   = 0.23255            # 18.312"/2 hole centre
FLANGE_W = 0.030
RAIL_IN  = OPEN_W / 2         # 0.225425
RAIL_OUT = RAIL_IN + FLANGE_W
ZF, ZR   = 0.430, -0.430      # rail mounting planes
PX0, PX1 = 0.354, 0.394       # corner post x range
PZ0, PZ1 = 0.510, 0.550       # corner post z range
TOP_BEAM = (2.030, 2.070)
TOP_PLATE = (2.070, 2.090)
DOOR_T, DOOR_W, DOOR_H = 0.030, 0.780, 1.930

# ------------------------------------------------------------------ small vector helpers
def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def norm(a):
    l = math.sqrt(dot(a, a)); return (a[0]/l, a[1]/l, a[2]/l)

# ------------------------------------------------------------------ materials
MATS = {
    "M_Frame":  dict(color=(0.035, 0.038, 0.045), metal=0.85, rough=0.50),
    "M_Panel":  dict(color=(0.020, 0.022, 0.026), metal=0.60, rough=0.55),
    "M_Rail":   dict(color=(1, 1, 1), metal=0.90, rough=0.40, tex="rail"),
    "M_Mesh":   dict(color=(1, 1, 1), metal=0.60, rough=0.60, tex="mesh", mask=True),
    "M_Accent": dict(color=(0.0, 0.18, 0.22), metal=0.20, rough=0.50),
    "M_Dark":   dict(color=(0.008, 0.009, 0.011), metal=0.10, rough=0.70),
}
TEXTURED = {k for k, v in MATS.items() if "tex" in v}

# ------------------------------------------------------------------ textures (pure-python PNG)
def png_bytes(w, h, px):
    raw = b"".join(b"\x00" + bytes(c for p in row for c in p) for row in px)
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))

def rail_texture():
    """One tile = exactly 1U tall x flange wide. EIA-310 hole pattern, square holes, U boundary line."""
    W, H = 32, 128
    base, dark, line = (176, 181, 186, 255), (22, 24, 28, 255), (84, 90, 98, 255)
    px = [[base] * W for _ in range(H)]
    for hc in (6.35, 22.225, 38.1):                     # mm from U bottom
        cy = H - hc / 44.45 * H
        hh = 9.5 / 44.45 * H / 2
        cx = 7.12 / 30.0 * W                            # inner edge -> hole centre
        hw = 9.5 / 30.0 * W / 2
        for y in range(H):
            for x in range(W):
                if abs(y + .5 - cy) <= hh and abs(x + .5 - cx) <= hw:
                    px[y][x] = dark
    for y in (0, 1, H-2, H-1):
        for x in range(W):
            px[y][x] = line
    return png_bytes(W, H, px)

def mesh_texture():
    """Perforation tile with alpha holes (alpha-scissor)."""
    S = 32
    col, hole = (40, 44, 50, 255), (40, 44, 50, 0)
    px = [[col] * S for _ in range(S)]
    for cx, cy in ((8, 8), (24, 24)):
        for y in range(S):
            for x in range(S):
                if (x + .5 - cx) ** 2 + (y + .5 - cy) ** 2 <= 5.2 ** 2:
                    px[y][x] = hole
    return png_bytes(S, S, px)

# ------------------------------------------------------------------ mesh builder
class Mesh:
    def __init__(self, name):
        self.name, self.prims = name, {}

    def poly(self, mat, pts, n, uv=None):
        g = cross(vsub(pts[1], pts[0]), vsub(pts[2], pts[0]))
        if dot(g, n) < 0:                                   # enforce CCW-front winding
            pts = pts[::-1]; uv = uv[::-1] if uv else None
        d = self.prims.setdefault(mat, dict(p=[], n=[], uv=[], i=[]))
        b = len(d["p"])
        d["p"] += pts; d["n"] += [n] * len(pts)
        d["uv"] += uv if uv else [(0.9, 0.5)] * len(pts)    # (0.9,0.5) = plain area of rail tex
        for k in range(1, len(pts) - 1):
            d["i"] += [b, b + k, b + k + 1]

    def box(self, mat, x0, y0, z0, x1, y1, z1, skip=(), uvf=None):
        F = {
            "+x": ([(x1,y0,z1),(x1,y0,z0),(x1,y1,z0),(x1,y1,z1)], (1,0,0)),
            "-x": ([(x0,y0,z0),(x0,y0,z1),(x0,y1,z1),(x0,y1,z0)], (-1,0,0)),
            "+y": ([(x0,y1,z1),(x1,y1,z1),(x1,y1,z0),(x0,y1,z0)], (0,1,0)),
            "-y": ([(x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1)], (0,-1,0)),
            "+z": ([(x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)], (0,0,1)),
            "-z": ([(x1,y0,z0),(x0,y0,z0),(x0,y1,z0),(x1,y1,z0)], (0,0,-1)),
        }
        for k, (p, n) in F.items():
            if k in skip: continue
            self.poly(mat, p, n, uvf(p) if (uvf and k == "+z") else None)

    def cyl(self, mat, axis, c, r, h0, h1, sides=8, cap0=True, cap1=True):
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
            self.poly(mat, [P(a0,h0), P(a1,h0), P(a1,h1), P(a0,h1)], norm(vsub(P((a0+a1)/2, h0), A(h0))))
        if cap1: self.poly(mat, [P(i*st, h1) for i in range(sides)], ax)
        if cap0: self.poly(mat, [P(i*st, h0) for i in range(sides)], (-ax[0], -ax[1], -ax[2]))

    def tris(self): return sum(len(d["i"]) // 3 for d in self.prims.values())

# ------------------------------------------------------------------ parts (rack space)
def build_frame():
    m = Mesh("Rack_42U")
    for sx in (-1, 1):
        for sz in (-1, 1):
            x0, x1 = (PX0, PX1) if sx > 0 else (-PX1, -PX0)
            z0, z1 = (PZ0, PZ1) if sz > 0 else (-PZ1, -PZ0)
            m.box("M_Frame", x0, BASE_TOP, z0, x1, TOP_BEAM[0], z1)           # posts
    y0, y1 = TOP_BEAM
    for sz in (-1, 1):                                                         # top ring
        z0, z1 = (PZ0, PZ1) if sz > 0 else (-PZ1, -PZ0)
        m.box("M_Frame", -PX1, y0, z0, PX1, y1, z1)
    for sx in (-1, 1):
        x0, x1 = (PX0, PX1) if sx > 0 else (-PX1, -PX0)
        m.box("M_Frame", x0, y0, -PZ0, x1, y1, PZ0)
    for sx in (-1, 1):                                                         # rail brackets
        xa, xb = (RAIL_OUT, PX0) if sx > 0 else (-PX0, -RAIL_OUT)
        for zp in (ZF, ZR):
            m.box("M_Frame", xa, BASE_TOP, zp - 0.04, xb, Y_U0, zp)
            m.box("M_Frame", xa, Y_UTOP, zp - 0.04, xb, TOP_BEAM[0], zp)
    return m

def build_base():
    m = Mesh("Rack_Base"); y0, y1 = FOOT_H, BASE_TOP
    for sz in (-1, 1):
        z0, z1 = (0.49, 0.55) if sz > 0 else (-0.55, -0.49)
        m.box("M_Frame", -0.40, y0, z0, 0.40, y1, z1)
    for sx in (-1, 1):
        x0, x1 = (0.34, 0.40) if sx > 0 else (-0.40, -0.34)
        m.box("M_Frame", x0, y0, -0.49, x1, y1, 0.49)
    m.box("M_Panel", -0.34, y1 - 0.006, 0.30, 0.34, y1, 0.49)                  # floor strips, centre open
    m.box("M_Panel", -0.34, y1 - 0.006, -0.49, 0.34, y1, -0.30)
    return m

def build_foot():
    m = Mesh("Rack_Foot")
    for sx in (-1, 1):
        for sz in (-1, 1):
            c = (sx * 0.374, sz * 0.530)
            m.cyl("M_Dark", "y", c, 0.045, 0.0, 0.015)
            m.cyl("M_Frame", "y", c, 0.020, 0.015, FOOT_H, cap0=False)
    return m

def build_top():
    m = Mesh("Rack_Top"); y0, y1 = TOP_PLATE
    m.box("M_Panel", -0.40, y0, -0.55, -0.15, y1, 0.55)
    m.box("M_Panel",  0.15, y0, -0.55,  0.40, y1, 0.55)
    m.box("M_Panel", -0.15, y0, -0.36,  0.15, y1, 0.55)
    m.box("M_Panel", -0.15, y0, -0.55,  0.15, y1, -0.50)                       # rear cable slot between
    return m

def build_side(sign, name):
    m = Mesh(name); y0, y1 = BASE_TOP, TOP_BEAM[1]
    xa, xb = (0.394, 0.400) if sign > 0 else (-0.400, -0.394)
    m.box("M_Panel", xa, y0, -0.55, xb, y1, 0.55)
    xo = 0.400 * sign
    for y in (0.30, 1.89):
        for z in (-0.48, 0.48):
            h0, h1 = (xo, xo + 0.004 * sign)
            m.cyl("M_Dark", "x", (y, z), 0.012, min(h0, h1), max(h0, h1), sides=6, cap0=False)
    return m

def build_rail(sign, zp, name):
    m = Mesh(name)
    if sign > 0:
        fx = (RAIL_IN, RAIL_OUT); wx = (RAIL_OUT - 0.003, RAIL_OUT)
        uvf = lambda pts: [((x - RAIL_IN) / FLANGE_W, 1 - (y - Y_U0) / U) for x, y, z in pts]
    else:
        fx = (-RAIL_OUT, -RAIL_IN); wx = (-RAIL_OUT, -RAIL_OUT + 0.003)
        uvf = lambda pts: [((-RAIL_IN - x) / FLANGE_W, 1 - (y - Y_U0) / U) for x, y, z in pts]
    m.box("M_Rail", fx[0], Y_U0, zp - 0.003, fx[1], Y_UTOP, zp, uvf=uvf)
    m.box("M_Rail", wx[0], Y_U0, zp - 0.030, wx[1], Y_UTOP, zp - 0.003)
    return m

# ------------------------------------------------------------------ doors (hinge-origin local space)
def door_common(m):
    t = DOOR_T / 2
    m.box("M_Frame", 0, 0, -t, 0.04, DOOR_H, t)
    m.box("M_Frame", DOOR_W - 0.04, 0, -t, DOOR_W, DOOR_H, t)
    m.box("M_Frame", 0.04, 0, -t, DOOR_W - 0.04, 0.04, t)
    m.box("M_Frame", 0.04, DOOR_H - 0.04, -t, DOOR_W - 0.04, DOOR_H, t)
    m.box("M_Accent", DOOR_W - 0.030, 0.85, t, DOOR_W - 0.012, 1.15, t + 0.018)       # handle
    for y in (0.20, 0.92, 1.64):
        m.box("M_Dark", -0.008, y, -0.012, 0.012, y + 0.08, 0.012)                      # hinge blocks

def mesh_quad(m, x0, y0, x1, y1, pitch):
    p = [(x0,y0,0),(x1,y0,0),(x1,y1,0),(x0,y1,0)]
    m.poly("M_Mesh", p, (0,0,1), [(x/pitch, y/pitch) for x, y, z in p])

def build_front_door():
    m = Mesh("Rack_FrontDoor"); door_common(m)
    mesh_quad(m, 0.04, 0.04, DOOR_W - 0.04, DOOR_H - 0.04, 0.020)
    return m

def build_rear_door():
    m = Mesh("Rack_RearDoor"); door_common(m)
    sx0, sx1, sy0, sy1, p = 0.20, 0.58, 0.10, 0.20, 0.014                 # cable-access slot
    mesh_quad(m, 0.04, 0.04, DOOR_W - 0.04, sy0, p)
    mesh_quad(m, 0.04, sy1, DOOR_W - 0.04, DOOR_H - 0.04, p)
    mesh_quad(m, 0.04, sy0, sx0, sy1, p)
    mesh_quad(m, sx1, sy0, DOOR_W - 0.04, sy1, p)
    m.box("M_Dark", sx0, sy0, -0.010, sx1, sy0 + 0.014, 0.010)             # brush strips
    m.box("M_Dark", sx0, sy1 - 0.014, -0.010, sx1, sy1, 0.010)
    return m

# ------------------------------------------------------------------ cable management
def build_vman(sign, name):
    """Vertical finger duct. Local origin: duct centre-x, U1 bottom, FRONT end; body extends -Z 0.20.
    Web on the outer (post) side, open toward rack centre, slat 'fingers' every 2U."""
    m = Mesh(name); D, hw = 0.20, 0.045
    ox = sign * hw
    web = (ox - 0.003, ox) if sign > 0 else (ox, ox + 0.003)
    m.box("M_Frame", web[0], 0, -D, web[1], N_U * U, 0)
    m.box("M_Frame", -hw, 0, -0.003, hw, N_U * U, 0)                      # front flange
    m.box("M_Frame", -hw, 0, -D, hw, N_U * U, -D + 0.003)                 # rear flange
    ix = -sign * hw
    fx = (ix - 0.006, ix) if sign > 0 else (ix, ix + 0.006)
    for k in range(N_U // 2 + 1):
        y = min(k * 2 * U, N_U * U - 0.006)
        m.box("M_Accent", fx[0], y, -D + 0.003, fx[1], y + 0.006, -0.003)
    return m

def bolts(m, n, sx_list=(-1, 1)):
    for sx in sx_list:
        for y in (0.00635, (n - 1) * U + 0.0381):
            m.cyl("M_Dark", "z", (sx * HOLE_X, y), 0.005, 0.003, 0.0045, sides=6, cap0=False)

def build_hman():
    m = Mesh("Rack_CableManager_Horizontal"); h = U - 0.0008; y0 = 0.0004
    m.box("M_Panel", -PANEL_W/2, y0, 0, PANEL_W/2, y0 + h, 0.003)
    m.box("M_Dark", -0.215, y0, 0.003, 0.215, y0 + 0.003, 0.063)
    m.box("M_Dark", -0.215, y0 + h - 0.003, 0.003, 0.215, y0 + h, 0.063)
    for i in range(12):
        x = -0.2 + i * (0.4 / 11)
        m.box("M_Accent", x - 0.0015, y0 + 0.003, 0.003, x + 0.0015, y0 + h - 0.003, 0.063)
    bolts(m, 1)
    return m

# ------------------------------------------------------------------ rack-mount modules
def build_blank(n):
    m = Mesh(f"Rack_Blank_{n}U"); h = n * U - 0.0008; y0 = 0.0004
    m.box("M_Panel", -PANEL_W/2, y0, 0, PANEL_W/2, y0 + h, 0.003)
    m.box("M_Panel", -0.215, y0, -0.012, 0.215, y0 + 0.003, 0)
    m.box("M_Panel", -0.215, y0 + h - 0.003, -0.012, 0.215, y0 + h, 0)
    bolts(m, n)
    return m

def build_shelf():
    m = Mesh("Rack_Shelf"); h = U - 0.0008; y0 = 0.0004
    m.box("M_Panel", -PANEL_W/2, y0, 0, PANEL_W/2, y0 + h, 0.003)           # 1U front plate
    m.box("M_Panel", -0.220, 0.002, -0.840, 0.220, 0.005, 0.0)              # tray (top surface y=0.005)
    for s in (-1, 1):
        a, b = (0.217, 0.220) if s > 0 else (-0.220, -0.217)
        m.box("M_Panel", a, 0.005, -0.857, b, 0.030, 0.0)                    # side walls
        ta, tb = (0.217, RAIL_OUT) if s > 0 else (-RAIL_OUT, -0.217)
        m.box("M_Panel", ta, 0.002, -0.860, tb, 0.034, -0.857)               # rear tabs -> rear rail plane
    m.box("M_Panel", -0.220, 0.005, -0.857, 0.220, 0.025, -0.854)            # back stop
    bolts(m, 1)
    return m

def build_collision():
    m = Mesh("Rack_Collision-convcolonly")
    m.box("M_Dark", -0.40, 0.0, -0.585, 0.40, TOP_PLATE[1], 0.585)
    return m

# ------------------------------------------------------------------ scene graph
class Node:
    def __init__(s, name, mesh=None, t=(0, 0, 0), q=(0, 0, 0, 1), kids=None):
        s.name, s.mesh, s.t, s.q, s.kids = name, mesh, t, q, kids or []

def slot_y(u): return Y_U0 + (u - 1) * U

def build_scene():
    frame = build_frame()
    root = Node("Rack_42U", frame)
    meshes = [frame]
    def add(node_name, mesh, t=(0, 0, 0), q=(0, 0, 0, 1)):
        meshes.append(mesh); root.kids.append(Node(node_name, mesh, t, q))
    add("Rack_Base", build_base())
    add("Rack_Foot", build_foot())
    add("Rack_Top", build_top())
    add("Rack_SidePanel_L", build_side(-1, "Rack_SidePanel_L"))
    add("Rack_SidePanel_R", build_side(+1, "Rack_SidePanel_R"))
    add("Rack_Rail_Front_L", build_rail(-1, ZF, "Rack_Rail_Front_L"))
    add("Rack_Rail_Front_R", build_rail(+1, ZF, "Rack_Rail_Front_R"))
    add("Rack_Rail_Rear_L",  build_rail(-1, ZR, "Rack_Rail_Rear_L"))
    add("Rack_Rail_Rear_R",  build_rail(+1, ZR, "Rack_Rail_Rear_R"))
    add("Rack_FrontDoor", build_front_door(), (-DOOR_W / 2, BASE_TOP, 0.568))
    add("Rack_RearDoor",  build_rear_door(),  (+DOOR_W / 2, BASE_TOP, -0.568), (0, 1, 0, 0))
    add("Rack_CableManager_Vertical",   build_vman(-1, "Rack_CableManager_Vertical"),   (-0.305, Y_U0, -0.28))
    add("Rack_CableManager_Vertical_R", build_vman(+1, "Rack_CableManager_Vertical_R"), (+0.305, Y_U0, -0.28))
    # --- sample module placement (delete / replace with hardware)
    add("Rack_Shelf",                   build_shelf(),  (0, slot_y(1), ZF))
    add("Rack_CableManager_Horizontal", build_hman(),   (0, slot_y(35), ZF))
    add("Rack_Blank_4U", build_blank(4), (0, slot_y(36), ZF))
    add("Rack_Blank_2U", build_blank(2), (0, slot_y(40), ZF))
    add("Rack_Blank_1U", build_blank(1), (0, slot_y(42), ZF))
    # --- reference anchors
    root.kids.append(Node("Rack_Mount_Front", None, (0, Y_U0, ZF)))
    root.kids.append(Node("Rack_Mount_Rear",  None, (0, Y_U0, ZR)))
    add("Rack_Collision-convcolonly", build_collision())
    return root, meshes

# ------------------------------------------------------------------ GLB writer
def write_glb(root, meshes, path):
    binb = bytearray(); views, accs = [], []
    def view(data, target=None):
        while len(binb) % 4: binb.append(0)
        views.append(dict(buffer=0, byteOffset=len(binb), byteLength=len(data), **({"target": target} if target else {})))
        binb.extend(data); return len(views) - 1
    def acc(v, ct, cnt, typ, mn=None, mx=None):
        a = dict(bufferView=v, componentType=ct, count=cnt, type=typ)
        if mn is not None: a["min"], a["max"] = mn, mx
        accs.append(a); return len(accs) - 1

    mat_names = list(MATS)
    gl_meshes = {}
    for m in meshes:
        prims = []
        for mat, d in m.prims.items():
            P = d["p"]
            mn = [min(p[i] for p in P) for i in range(3)]; mx = [max(p[i] for p in P) for i in range(3)]
            at = {"POSITION": acc(view(b"".join(struct.pack("<3f", *p) for p in P), 34962), 5126, len(P), "VEC3", mn, mx),
                  "NORMAL":   acc(view(b"".join(struct.pack("<3f", *n) for n in d["n"]), 34962), 5126, len(P), "VEC3")}
            if mat in TEXTURED:
                at["TEXCOORD_0"] = acc(view(b"".join(struct.pack("<2f", *u) for u in d["uv"]), 34962), 5126, len(P), "VEC2")
            I = d["i"]; assert len(P) < 65536
            ia = acc(view(struct.pack(f"<{len(I)}H", *I), 34963), 5123, len(I), "SCALAR")
            prims.append(dict(attributes=at, indices=ia, material=mat_names.index(mat), mode=4))
        gl_meshes[m.name] = dict(name=m.name, primitives=prims)
    mesh_list = list(gl_meshes.values()); mesh_idx = {k: i for i, k in enumerate(gl_meshes)}

    images = []
    for t in (rail_texture(), mesh_texture()):
        images.append(dict(bufferView=view(t), mimeType="image/png"))
    tex_idx = {"rail": 0, "mesh": 1}
    materials = []
    for name, s in MATS.items():
        pbr = dict(baseColorFactor=[*s["color"], 1.0], metallicFactor=s["metal"], roughnessFactor=s["rough"])
        if "tex" in s: pbr["baseColorTexture"] = dict(index=tex_idx[s["tex"]])
        mt = dict(name=name, pbrMetallicRoughness=pbr)
        if s.get("mask"): mt.update(alphaMode="MASK", alphaCutoff=0.5, doubleSided=True)
        materials.append(mt)

    flat = []
    def walk(n):
        i = len(flat); flat.append(None)
        kid_ids = [walk(k) for k in n.kids]
        d = dict(name=n.name)
        if n.mesh: d["mesh"] = mesh_idx[n.mesh.name]
        if any(n.t): d["translation"] = list(n.t)
        if n.q != (0, 0, 0, 1): d["rotation"] = list(n.q)
        if kid_ids: d["children"] = kid_ids
        flat[i] = d; return i
    walk(root)

    gltf = dict(asset=dict(version="2.0", generator="build_rack.py"), scene=0, scenes=[dict(nodes=[0])],
                nodes=flat, meshes=mesh_list, materials=materials, accessors=accs, bufferViews=views,
                buffers=[dict(byteLength=len(binb))], images=images, textures=[dict(sampler=0, source=0), dict(sampler=0, source=1)],
                samplers=[dict(magFilter=9729, minFilter=9987, wrapS=10497, wrapT=10497)])
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4); binb += b"\x00" * (-len(binb) % 4)
    total = 12 + 8 + len(js) + 8 + len(binb)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(binb), b"BIN\x00")); f.write(binb)
    return total

# ------------------------------------------------------------------ main
if __name__ == "__main__":
    root, meshes = build_scene()
    # sanity: every triangle winding agrees with its stored normal
    for m in meshes:
        for d in m.prims.values():
            for k in range(0, len(d["i"]), 3):
                a, b, c = (d["p"][j] for j in d["i"][k:k+3])
                assert dot(cross(vsub(b, a), vsub(c, a)), d["n"][d["i"][k]]) > 0, m.name
    size = write_glb(root, meshes, os.path.join(OUT, "Rack_42U.glb"))
    print(f"Rack_42U.glb  {size/1024:.1f} KB")
    total = 0
    for m in meshes:
        total += m.tris(); print(f"  {m.name:<34}{m.tris():>5} tris")
    print(f"  TOTAL (incl. collision proxy) {total}")
    print(f"U-space: y {Y_U0:.4f} -> {Y_UTOP:.4f}  ({Y_UTOP-Y_U0:.4f} m = {N_U}U)   overall height {TOP_PLATE[1]:.3f} m")
