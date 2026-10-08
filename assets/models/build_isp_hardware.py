#!/usr/bin/env python3
"""
Fictional ISP connectivity hardware  ->  ISP_Modem / ISP_InternetGateway / ISP_FiberGateway / ISP_CPE (.glb)

Conventions (meters, Y-up, glTF 2.0)
  * Origin = bottom-centre of the enclosure footprint (feet rest on y=0).
  * FRONT = +Z (status LEDs). REAR = -Z (all ports + power).
  * Port anchors: empty nodes named ISP_IN / WAN / LAN / MGMT / Power_In, placed on the port face.
    Their local +Z points OUT of the port (cable direction). Metadata in node extras.
  * LEDs: one tiny MeshInstance per LED (LED_PWR, LED_ISP, LED_WAN, LED_LAN, LED_MGMT), sharing one
    quad mesh per colour. Swap the surface override material at runtime to change state.
  * Everything else is merged into ONE body mesh (5 surfaces max) for cheap instancing.
"""
import math, json, struct, zlib, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "."

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

def vent_texture():
    """Alpha-scissor vent slots: one slot per tile (9 of 16 rows opaque)."""
    S = 16
    px = [[(10, 11, 14, 255) if 3 <= y < 12 else (10, 11, 14, 0) for _ in range(2 * S)] for y in range(S)]
    px = [[(10, 11, 14, 255) if (3 <= y < 12 and 2 <= x < 2 * S - 2) else (10, 11, 14, 0) for x in range(2 * S)] for y in range(S)]
    return png_bytes(2 * S, S, px)

# ------------------------------------------------------------------ materials
MATS = {
    "M_Body_Graphite": dict(color=(0.030, 0.032, 0.038), metal=0.30, rough=0.55),
    "M_Body_Slate":    dict(color=(0.070, 0.085, 0.100), metal=0.30, rough=0.55),
    "M_Body_Light":    dict(color=(0.300, 0.320, 0.350), metal=0.15, rough=0.50),
    "M_Body_White":    dict(color=(0.620, 0.640, 0.670), metal=0.10, rough=0.50),
    "M_Metal":         dict(color=(0.450, 0.470, 0.500), metal=0.90, rough=0.35),
    "M_Dark":          dict(color=(0.006, 0.007, 0.009), metal=0.10, rough=0.65),
    "M_Trim":          dict(color=(1, 1, 1), metal=0.20, rough=0.50, vc=True),     # vertex-coloured
    "M_Vent":          dict(color=(1, 1, 1), metal=0.10, rough=0.70, tex="vent", mask=True),
    "M_LED_Off":       dict(color=(0.02, 0.02, 0.025), metal=0.0, rough=0.30),
    "M_LED_Green":     dict(color=(0.02, 0.15, 0.04), metal=0.0, rough=0.30, emis=(0.10, 1.00, 0.25)),
    "M_LED_Amber":     dict(color=(0.15, 0.09, 0.01), metal=0.0, rough=0.30, emis=(1.00, 0.60, 0.05)),
    "M_LED_Blue":      dict(color=(0.02, 0.06, 0.15), metal=0.0, rough=0.30, emis=(0.15, 0.45, 1.00)),
}
VC = {k for k, v in MATS.items() if v.get("vc")}
TEXTURED = {k for k, v in MATS.items() if "tex" in v}

TEAL  = (0.00, 0.20, 0.25, 1)
STRIP = (0.006, 0.008, 0.010, 1)
SLATE = (0.030, 0.045, 0.055, 1)
GREEN = (0.00, 0.50, 0.05, 1)
LABEL = {"ISP_IN": (0.90, 0.45, 0.00, 1), "WAN": (0.05, 0.25, 0.90, 1),
         "LAN": (0.05, 0.60, 0.10, 1), "MGMT": (0.45, 0.10, 0.70, 1)}

# ------------------------------------------------------------------ mesh builder
class Mesh:
    def __init__(self, name):
        self.name, self.prims = name, {}

    def poly(self, mat, pts, n, uv=None, col=None):
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

    def tris(self): return sum(len(d["i"]) // 3 for d in self.prims.values())

class Node:
    def __init__(s, name, mesh=None, t=(0, 0, 0), q=(0, 0, 0, 1), extras=None):
        s.name, s.mesh, s.t, s.q, s.extras, s.kids = name, mesh, t, q, extras, []

# shared LED lens quads (face +Z, centred on origin)
def led_mesh(mat):
    m = Mesh("LED_Lens_" + mat.split("_")[-1]); h = 0.00275
    m.poly(mat, [(-h,-h,0),(h,-h,0),(h,h,0),(-h,h,0)], (0, 0, 1))
    return m
LED_MESHES = {c: led_mesh("M_LED_" + c) for c in ("Off", "Green", "Amber", "Blue")}

# ------------------------------------------------------------------ device builder
class Dev:
    def __init__(s, name, W, D, H, split, body):
        s.m = Mesh(name); s.root = Node(name, s.m)
        s.W, s.D, s.H, s.sp, s.body = W, D, H, split, body
        s.Dh = D / 2 - 0.001                       # chassis rear/front plane
        s.port_info, s.led_info = [], []

    # rear-port space: pd = distance outward (towards -Z) from chassis rear wall
    def pz(s, pd): return -(s.Dh + pd)
    def pbox(s, mat, x0, y0, p0, x1, y1, p1, col=None):
        za, zb = sorted((s.pz(p0), s.pz(p1))); s.m.box(mat, x0, y0, za, x1, y1, zb, col=col)
    def pquad(s, mat, x0, y0, x1, y1, pd, col=None):
        z = s.pz(pd); s.m.poly(mat, [(x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z)], (0, 0, -1), None, col)
    def pcyl(s, mat, x, y, r, p0, p1, sides=8, col=None):
        za, zb = sorted((s.pz(p0), s.pz(p1)))
        s.m.cyl(mat, "z", (x, y), r, za, zb, sides=sides, cap0=True, cap1=False, col=col)   # cap0 = outer (-Z) end

    def enclosure(s):
        m, W, D, H, sp = s.m, s.W, s.D, s.H, s.sp
        for sx in (-1, 1):
            for sz in (-1, 1):
                cx, cz = sx * (W / 2 - 0.018), sz * (D / 2 - 0.016)
                m.box("M_Dark", cx - 0.006, 0, cz - 0.005, cx + 0.006, 0.003, cz + 0.005)
        m.box(s.body, -W/2 + 0.001, 0.003, -s.Dh, W/2 - 0.001, sp, s.Dh, skip=("+y",))
        m.box(s.body, -W/2, sp, -D/2, W/2, H, D/2)
        z = s.Dh + 0.0003                                                  # teal accent line, chassis front
        m.poly("M_Trim", [(-W/2+0.012, sp-0.0055, z), (W/2-0.012, sp-0.0055, z),
                          (W/2-0.012, sp-0.0035, z), (-W/2+0.012, sp-0.0035, z)], (0, 0, 1), None, TEAL)

    def leds(s, items, spacing=0.016):
        n = len(items); sw = n * spacing + 0.010
        z = s.D / 2 + 0.0003; y0, y1 = s.sp + 0.003, s.H - 0.003
        s.m.poly("M_Trim", [(-sw/2,y0,z),(sw/2,y0,z),(sw/2,y1,z),(-sw/2,y1,z)], (0, 0, 1), None, STRIP)
        for i, (nm, color) in enumerate(items):
            x = (i - (n - 1) / 2) * spacing
            s.root.kids.append(Node("LED_" + nm, LED_MESHES[color], (x, (y0 + y1) / 2, s.D / 2 + 0.0007),
                                    extras=dict(led=nm, default=color)))
            s.led_info.append(nm)

    def vent_top(s, x0, x1, z0, z1, p=0.008):
        y = s.H + 0.0003
        pts = [(x0,y,z1),(x1,y,z1),(x1,y,z0),(x0,y,z0)]
        s.m.poly("M_Vent", pts, (0, 1, 0), [(x/p, z/p) for x, _, z in pts])

    def vent_side(s, sign, z0, z1, y0, y1, p=0.008):
        x = sign * (s.W / 2 + 0.0003)
        pts = [(x,y0,z0),(x,y0,z1),(x,y1,z1),(x,y1,z0)]
        s.m.poly("M_Vent", pts, (sign, 0, 0), [(z/p, y/p) for _, y, z in pts])

    def add_port(s, name, x, yc, ptype, role):
        s.root.kids.append(Node(name, None, (x, yc, s.pz(0)), (0, 1, 0, 0),
                                dict(port=name, type=ptype, role=role, direction="+Z is outward")))
        s.port_info.append((name, ptype))

    def label(s, role, x, ytop):
        s.pquad("M_Trim", x - 0.0045, ytop, x + 0.0045, ytop + 0.0015, 0.0003, LABEL[role])

    def rj45(s, name, x, yc):
        w, h, t, dp = 0.0150, 0.0130, 0.0012, 0.0035
        s.pbox("M_Metal", x-w/2, yc+h/2-t, 0, x+w/2, yc+h/2, dp)
        s.pbox("M_Metal", x-w/2, yc-h/2, 0, x+w/2, yc-h/2+t, dp)
        s.pbox("M_Metal", x-w/2, yc-h/2+t, 0, x-w/2+t, yc+h/2-t, dp)
        s.pbox("M_Metal", x+w/2-t, yc-h/2+t, 0, x+w/2, yc+h/2-t, dp)
        s.pquad("M_Dark", x-w/2+t, yc-h/2+t, x+w/2-t, yc+h/2-t, 0.0004)
        s.label(name, x, yc + h/2 + 0.0015)
        s.add_port(name, x, yc, "RJ45", name)

    def coax(s, name, x, yc):
        s.pcyl("M_Metal", x, yc, 0.0075, 0, 0.004, sides=6)
        s.pcyl("M_Metal", x, yc, 0.0052, 0.004, 0.013, sides=8)
        s.pcyl("M_Dark", x, yc, 0.0026, 0.013, 0.0133, sides=6)
        s.label(name, x, yc + 0.0090)
        s.add_port(name, x, yc, "COAX_F", name)

    def sc(s, name, x, yc):
        s.pbox("M_Metal", x-0.0125, yc-0.0105, 0, x+0.0125, yc+0.0105, 0.0015)
        s.pbox("M_Metal", x-0.0070, yc-0.0060, 0.0015, x+0.0070, yc+0.0060, 0.0100)
        s.pbox("M_Trim", x-0.0048, yc-0.0048, 0.0100, x+0.0048, yc+0.0048, 0.0165, col=GREEN)   # dust cap
        s.label(name, x, yc + 0.0115)
        s.add_port(name, x, yc, "SC_APC", name)

    def barrel(s, x, yc):
        s.pcyl("M_Metal", x, yc, 0.0050, 0, 0.004, sides=8)
        s.pcyl("M_Dark", x, yc, 0.0030, 0.004, 0.0043, sides=8)
        s.add_port("Power_In", x, yc, "DC_BARREL", "POWER")

    def iec(s, x, yc):
        w, h, t, dp = 0.0290, 0.0200, 0.0020, 0.0060
        s.pbox("M_Metal", x-w/2, yc+h/2-t, 0, x+w/2, yc+h/2, dp)
        s.pbox("M_Metal", x-w/2, yc-h/2, 0, x+w/2, yc-h/2+t, dp)
        s.pbox("M_Metal", x-w/2, yc-h/2+t, 0, x-w/2+t, yc+h/2-t, dp)
        s.pbox("M_Metal", x+w/2-t, yc-h/2+t, 0, x+w/2, yc+h/2-t, dp)
        s.pquad("M_Dark", x-w/2+t, yc-h/2+t, x+w/2-t, yc+h/2-t, 0.0004)
        for px in (-0.008, 0.008):
            s.pbox("M_Metal", x+px-0.0008, yc-0.004, 0.0004, x+px+0.0008, yc+0.004, 0.0040)
        s.add_port("Power_In", x, yc, "IEC_C14", "POWER")

    def finish(s):
        s.root.extras = dict(device=s.root.name, size_m=[s.W, s.H, s.D], front="+Z", ports_rear="-Z",
                             leds=s.led_info, ports=[p[0] for p in s.port_info],
                             shelf_compatible=True)
        return s.root

# ------------------------------------------------------------------ the four devices
def build_modem():
    d = Dev("ISP_Modem", 0.180, 0.130, 0.045, 0.026, "M_Body_Slate"); d.enclosure()
    d.leds([("PWR", "Green"), ("ISP", "Blue"), ("LAN", "Green")])
    d.vent_top(-0.060, 0.060, -0.045, 0.030)
    d.coax("ISP_IN", -0.050, 0.0135); d.rj45("LAN", 0.010, 0.0135); d.barrel(0.058, 0.0135)
    return d.finish()

def build_gateway():
    d = Dev("ISP_InternetGateway", 0.300, 0.220, 0.050, 0.030, "M_Body_Graphite"); d.enclosure()
    d.leds([("PWR", "Green"), ("WAN", "Blue"), ("LAN", "Green"), ("MGMT", "Amber")])
    d.vent_top(-0.125, -0.020, -0.085, 0.060); d.vent_top(0.020, 0.125, -0.085, 0.060)
    d.vent_side(-1, -0.080, 0.060, 0.034, 0.046); d.vent_side(1, -0.080, 0.060, 0.034, 0.046)
    d.rj45("WAN", -0.095, 0.0165); d.rj45("LAN", -0.060, 0.0165); d.rj45("MGMT", -0.025, 0.0165)
    d.pcyl("M_Metal", 0.040, 0.0165, 0.0035, 0, 0.002, sides=6)           # ground stud
    d.iec(0.095, 0.0165)
    return d.finish()

def build_fiber():
    d = Dev("ISP_FiberGateway", 0.200, 0.150, 0.060, 0.034, "M_Body_Light"); d.enclosure()
    d.leds([("PWR", "Green"), ("ISP", "Blue"), ("LAN", "Green")])
    d.vent_side(-1, -0.050, 0.040, 0.040, 0.054); d.vent_side(1, -0.050, 0.040, 0.040, 0.054)
    m, H = d.m, d.H                                                       # fiber-management hatch
    m.box("M_Trim", -0.055, H, -0.060, 0.055, H + 0.004, 0.015, col=SLATE)
    for sx in (-1, 1):
        for z in (-0.054, 0.009):
            m.cyl("M_Metal", "y", (sx * 0.049, z), 0.0035, H + 0.004, H + 0.0055, sides=6, cap0=False)
    d.sc("ISP_IN", -0.055, 0.0185); d.rj45("LAN", 0.000, 0.0185); d.barrel(0.058, 0.0185)
    return d.finish()

def build_cpe():
    d = Dev("ISP_CPE", 0.120, 0.090, 0.032, 0.018, "M_Body_White"); d.enclosure()
    d.leds([("PWR", "Green"), ("WAN", "Blue"), ("LAN", "Green")], spacing=0.014)
    d.vent_top(-0.030, 0.030, -0.025, 0.020)
    d.rj45("WAN", -0.032, 0.0105); d.rj45("LAN", -0.003, 0.0105); d.barrel(0.036, 0.0105)
    return d.finish()

# ------------------------------------------------------------------ GLB writer
def write_glb(root, path):
    # collect meshes
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

    images = [dict(bufferView=view(vent_texture()), mimeType="image/png") for _ in tex_used]
    materials = []
    for k in used:
        s = MATS[k]
        pbr = dict(baseColorFactor=[*s["color"], 1.0], metallicFactor=s["metal"], roughnessFactor=s["rough"])
        if "tex" in s: pbr["baseColorTexture"] = dict(index=tex_used.index(s["tex"]))
        mt = dict(name=k, pbrMetallicRoughness=pbr)
        if "emis" in s: mt["emissiveFactor"] = list(s["emis"])
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

    gltf = dict(asset=dict(version="2.0", generator="build_isp_hardware.py"), scene=0, scenes=[dict(nodes=[0])],
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

DEVICES = [build_modem, build_gateway, build_fiber, build_cpe]

if __name__ == "__main__":
    for fn in DEVICES:
        root = fn()
        meshes, size = write_glb(root, os.path.join(OUT, root.name + ".glb"))
        for m in meshes.values():                      # winding sanity
            for dd in m.prims.values():
                for k in range(0, len(dd["i"]), 3):
                    a, b, c = (dd["p"][j] for j in dd["i"][k:k+3])
                    assert dot(cross(vsub(b, a), vsub(c, a)), dd["n"][dd["i"][k]]) > 0, m.name
        body = root.mesh
        ex = root.extras
        print(f"{root.name:<22}{size/1024:6.1f} KB  body {body.tris():>4} tris / {len(body.prims)} surfaces   "
              f"size WxHxD = {ex['size_m'][0]*1000:.0f} x {ex['size_m'][1]*1000:.0f} x {ex['size_m'][2]*1000:.0f} mm   "
              f"ports {ex['ports']}  leds {ex['leds']}")
