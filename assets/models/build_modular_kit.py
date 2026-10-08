#!/usr/bin/env python3
"""
Modular building kit generator -> GLB (glTF 2.0 binary), Godot 4.x ready.
Pure Python, no dependencies.  Units: meters.  Y up, +Z toward viewer (glTF/Godot).

KIT CONSTANTS
  Grid            1.00 m
  Wall thickness  0.10 m   (walls are centered on grid LINES, floor/ceiling tiles on grid CELLS)
  Wall height     3.20 m   (floor level -> underside of next structural slab)
  Floor tile      0.05 m thick (top surface at y = 0.05)
  Ceiling plane   y = 3.00 (tile underside; piece origin placed at this height)
  Structural slab 0.30 m thick, placed at y = 3.20  -> storey pitch 3.50 m
"""
import json, struct, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "out"
os.makedirs(OUT, exist_ok=True)

GRID = 1.0
T = 0.10; h = T / 2
H = 3.20
PL = 0.10            # plinth band height
FT = 0.05            # floor tile thickness
OPEN_H = 2.15        # door clear height
HEAD = 0.05          # header trim band
JW = 0.05            # jamb width

# ---------------------------------------------------------------- materials
MATS = {
    "M_Wall":       dict(c=(0.80, 0.82, 0.84, 1.0), r=0.90, m=0.0),
    "M_Plinth":     dict(c=(0.24, 0.26, 0.29, 1.0), r=0.70, m=0.2),
    "M_Trim":       dict(c=(0.16, 0.18, 0.21, 1.0), r=0.60, m=0.3),
    "M_FloorFrame": dict(c=(0.22, 0.24, 0.27, 1.0), r=0.80, m=0.1),
    "M_FloorPanel": dict(c=(0.34, 0.36, 0.40, 1.0), r=0.75, m=0.1),
    "M_Hatch":      dict(c=(0.55, 0.58, 0.62, 1.0), r=0.50, m=0.5),
    "M_Door":       dict(c=(0.50, 0.55, 0.60, 1.0), r=0.55, m=0.3),
    "M_Concrete":   dict(c=(0.58, 0.58, 0.56, 1.0), r=0.95, m=0.0),
    "M_Ceiling":    dict(c=(0.90, 0.91, 0.92, 1.0), r=0.90, m=0.0),
    "M_Glass":      dict(c=(0.62, 0.80, 0.90, 0.25), r=0.20, m=0.0, blend=True),
}
MAT_ORDER = list(MATS)


# ---------------------------------------------------------------- geometry
def _sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


class Geo:
    def __init__(self):
        self.prims = {}

    def _p(self, m):
        return self.prims.setdefault(m, dict(p=[], n=[], uv=[], i=[]))

    def quad(self, m, pts, n, uvs):
        d = self._p(m)
        b = len(d["p"])
        for p, uv in zip(pts, uvs):
            d["p"].append(p); d["n"].append(n); d["uv"].append(uv)
        d["i"] += [b, b+1, b+2, b, b+2, b+3]

    def box(self, m, lo, hi, skip=()):
        """Axis-aligned box; faces named '-x','+x','-y','+y','-z','+z' can be skipped."""
        for ax in range(3):
            for sg in (-1, 1):
                if (("-" if sg < 0 else "+") + "xyz"[ax]) in skip:
                    continue
                a, b = {0: (2, 1), 1: (0, 2), 2: (0, 1)}[ax]
                c = lo[ax] if sg < 0 else hi[ax]
                pts = []
                for ia, ib in ((0, 0), (1, 0), (1, 1), (0, 1)):
                    v = [0.0, 0.0, 0.0]
                    v[ax] = c
                    v[a] = (lo, hi)[ia][a]
                    v[b] = (lo, hi)[ib][b]
                    pts.append(tuple(v))
                n = [0, 0, 0]; n[ax] = sg
                if _dot(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])), n) < 0:
                    pts = [pts[0], pts[3], pts[2], pts[1]]
                uvs = [(p[a], -p[b]) for p in pts]      # 1 UV unit = 1 m (tileable)
                self.quad(m, pts, tuple(n), uvs)


# ---------------------------------------------------------------- helpers
def wslab(g, x0, x1, z0, z1, ya, yb, skip=()):
    """Wall volume with plinth band (flush, same thickness).  +/-Y faces always hidden."""
    s = tuple(skip) + ("-y", "+y")
    if ya < PL:
        g.box("M_Plinth", (x0, ya, z0), (x1, min(PL, yb), z1), s)
        ya = PL
    if yb > ya:
        g.box("M_Wall", (x0, ya, z0), (x1, yb, z1), s)


def frame(g, half):
    ci = half - JW
    g.box("M_Trim", (-half, 0, -h), (-ci, OPEN_H + HEAD, h), ("-y", "+y", "-x"))
    g.box("M_Trim", (ci, 0, -h), (half, OPEN_H + HEAD, h), ("-y", "+y", "+x"))
    g.box("M_Trim", (-ci, OPEN_H, -h), (ci, OPEN_H + HEAD, h), ("-x", "+x", "+y"))
    wslab(g, -half, half, -h, h, OPEN_H + HEAD, H, ("-x", "+x"))


# ---------------------------------------------------------------- assets
ASSETS = []


def asset(name, geo=None, children=None, t=(0, 0, 0), extras=None):
    ASSETS.append(dict(name=name, geo=geo, children=children or [], t=t, extras=extras or {}))


# 1 Floor_1x1
g = Geo()
g.box("M_FloorFrame", (-0.5, 0, -0.5), (0.5, FT - 0.005, 0.5), ("-y",))
g.box("M_FloorPanel", (-0.48, FT - 0.005, -0.48), (0.48, FT, 0.48), ("-y",))
asset("Floor_1x1", g, extras=dict(footprint=[1, 1], height=FT, pivot="bottom-center, cell center"))

# 2 Floor_AccessPanel_1x1
g = Geo()
g.box("M_FloorFrame", (-0.5, 0, -0.5), (0.5, FT - 0.005, 0.5), ("-y",))
g.box("M_FloorPanel", (-0.48, FT - 0.005, -0.48), (0.48, FT, 0.48), ("-y",))
R = 0.004
g.box("M_Trim", (-0.27, FT, 0.23), (0.27, FT + R, 0.27), ("-y",))
g.box("M_Trim", (-0.27, FT, -0.27), (0.27, FT + R, -0.23), ("-y",))
g.box("M_Trim", (0.23, FT, -0.23), (0.27, FT + R, 0.23), ("-y", "-z", "+z"))
g.box("M_Trim", (-0.27, FT, -0.23), (-0.23, FT + R, 0.23), ("-y", "-z", "+z"))
g.box("M_Hatch", (-0.23, FT, -0.23), (0.23, FT + 0.002, 0.23), ("-y",))
g.box("M_Trim", (-0.06, FT + 0.002, -0.015), (0.06, FT + 0.006, 0.015), ("-y",))
asset("Floor_AccessPanel_1x1", g, extras=dict(footprint=[1, 1], height=FT + R, pivot="bottom-center, cell center"))

# 3 Wall_Straight_1m
g = Geo(); wslab(g, -0.5, 0.5, -h, h, 0, H, ("-x", "+x"))
asset("Wall_Straight_1m", g, extras=dict(length=1.0, thickness=T, height=H, pivot="bottom-center, on grid line"))

# 4 Wall_Straight_Short (0.5 m)
g = Geo(); wslab(g, -0.25, 0.25, -h, h, 0, H, ("-x", "+x"))
asset("Wall_Straight_Short", g, extras=dict(length=0.5, thickness=T, height=H, pivot="bottom-center, on grid line"))

# 5 Wall_End (0.5 m with finished trim cap on -X end)
g = Geo()
g.box("M_Trim", (-0.25, 0, -h), (-0.20, H, h), ("-y", "+y", "+x"))
wslab(g, -0.20, 0.25, -h, h, 0, H, ("-x", "+x"))
asset("Wall_End", g, extras=dict(length=0.5, thickness=T, height=H, cap="-X end", pivot="bottom-center, on grid line"))

# 6 Wall_Corner_Inner  (origin on grid vertex, arms 0.5 m toward +X and +Z)
g = Geo()
wslab(g, h, 0.5, -h, h, 0, H, ("-x", "+x"))
wslab(g, -h, h, h, 0.5, 0, H, ("-z", "+z"))
wslab(g, -h, h, -h, h, 0, H, ("+x", "+z"))
asset("Wall_Corner_Inner", g, extras=dict(arms=[0.5, 0.5], thickness=T, height=H, pivot="bottom-center on grid vertex; arms toward +X,+Z"))

# 7 Wall_Corner_Outer  (same footprint, trim corner post on the convex edge)
g = Geo()
wslab(g, h, 0.5, -h, h, 0, H, ("-x", "+x"))
wslab(g, -h, h, h, 0.5, 0, H, ("-z", "+z"))
g.box("M_Trim", (-h, 0, -h), (h, H, h), ("-y", "+y", "+x", "+z"))
asset("Wall_Corner_Outer", g, extras=dict(arms=[0.5, 0.5], thickness=T, height=H, pivot="bottom-center on grid vertex; arms toward +X,+Z"))

# 8 Door_Frame (1 m slot, clear opening 0.90 x 2.15)
g = Geo(); frame(g, 0.5)
asset("Door_Frame", g, extras=dict(width=1.0, clear_width=0.9, clear_height=OPEN_H, thickness=T, height=H, pivot="bottom-center, on grid line"))

# 9 Door_Single (origin = hinge, bottom). Place at frame.x - 0.45.
g = Geo()
g.box("M_Door", (0.01, 0.06, -0.02), (0.89, 2.12, 0.02))
for s in (1, -1):
    z0, z1 = (0.02, 0.045) if s > 0 else (-0.045, -0.02)
    g.box("M_Trim", (0.80, 0.97, z0), (0.83, 1.03, z1))
    zz0, zz1 = (0.035, 0.045) if s > 0 else (-0.045, -0.035)
    g.box("M_Trim", (0.74, 0.995, zz0), (0.83, 1.015, zz1))
asset("Door_Single", g, extras=dict(leaf_width=0.88, leaf_height=2.06, thickness=0.04,
                                    pivot="hinge, bottom (rotate about Y); place at frame x-0.45"))

# 10 Door_Double (origin = bottom-center of 2 m opening; two hinged leaf nodes)
def leaf(sign):
    gl = Geo()
    if sign > 0:   # left leaf hinged at local x=0, extends +X
        gl.box("M_Door", (0.005, 0.06, -0.02), (0.945, 2.12, 0.02))
        xs = (0.88, 0.91, 0.80, 0.91)
    else:
        gl.box("M_Door", (-0.945, 0.06, -0.02), (-0.005, 2.12, 0.02))
        xs = (-0.91, -0.88, -0.91, -0.80)
    for s in (1, -1):
        z0, z1 = (0.02, 0.045) if s > 0 else (-0.045, -0.02)
        gl.box("M_Trim", (xs[0], 0.97, z0), (xs[1], 1.03, z1))
        zz0, zz1 = (0.035, 0.045) if s > 0 else (-0.045, -0.035)
        gl.box("M_Trim", (xs[2], 0.995, zz0), (xs[3], 1.015, zz1))
    return gl

asset("Door_Double", None, children=[
    dict(name="Leaf_L", geo=leaf(+1), t=(-0.95, 0, 0), extras=dict(pivot="hinge, rotate about Y")),
    dict(name="Leaf_R", geo=leaf(-1), t=(0.95, 0, 0), extras=dict(pivot="hinge, rotate about Y"))],
    extras=dict(width=2.0, clear_width=1.9, pivot="bottom-center of 2 m opening; leaf nodes are hinge pivots"))

# 11 Window_Frame (1 m slot, clear opening 0.90 x 1.10, sill 0.95)
g = Geo()
SILL, HEADY = 0.90, 2.10
wslab(g, -0.5, 0.5, -h, h, 0, SILL, ("-x", "+x"))
wslab(g, -0.5, 0.5, -h, h, HEADY, H, ("-x", "+x"))
g.box("M_Trim", (-0.5, SILL, -h), (-0.45, HEADY, h), ("-x", "-y", "+y"))
g.box("M_Trim", (0.45, SILL, -h), (0.5, HEADY, h), ("+x", "-y", "+y"))
g.box("M_Trim", (-0.45, SILL, -h), (0.45, SILL + 0.05, h), ("-x", "+x", "-y"))
g.box("M_Trim", (-0.45, HEADY - 0.05, -h), (0.45, HEADY, h), ("-x", "+x", "+y"))
asset("Window_Frame", g, extras=dict(width=1.0, clear_width=0.9, clear_height=1.1, sill=SILL + 0.05, thickness=T, height=H,
                                     pivot="bottom-center, on grid line"))

# 12 Window (single double-sided quad, 2 tris)
g = Geo()
gx, y0, y1 = 0.46, SILL + 0.04, HEADY - 0.04
g.quad("M_Glass", [(-gx, y0, 0), (gx, y0, 0), (gx, y1, 0), (-gx, y1, 0)], (0, 0, 1),
       [(0, 1), (1, 1), (1, 0), (0, 0)])
asset("Window", g, extras=dict(width=0.92, height=y1 - y0, pivot="bottom-center (same origin as Window_Frame)",
                               note="double-sided alpha-blend quad, no reflections"))

# 13 Ceiling_1x1 (origin bottom-center of tile; place at y=3.00)
def ceiling_tile(g, z_lo, z_hi):
    # perimeter rails (T-bar look), recessed panel
    RW, RH, REC = 0.03, 0.04, 0.012
    x0, x1 = -0.5, 0.5
    # rails (outer faces / top hidden)
    for (a, b, sk) in (
        ((x0, 0, z_hi - RW), (x1, RH, z_hi), ("+x", "-x", "+y", "+z")),
        ((x0, 0, z_lo), (x1, RH, z_lo + RW), ("+x", "-x", "+y", "-z")),
    ):
        g.box("M_Trim", a, b, sk)
    g.box("M_Trim", (x1 - RW, 0, z_lo + RW), (x1, RH, z_hi - RW), ("+x", "+y", "-z", "+z"))
    g.box("M_Trim", (x0, 0, z_lo + RW), (x0 + RW, RH, z_hi - RW), ("-x", "+y", "-z", "+z"))
    g.box("M_Ceiling", (x0 + RW, REC, z_lo + RW), (x1 - RW, 0.03, z_hi - RW),
          ("+x", "-x", "+y", "+z", "-z"))

g = Geo(); ceiling_tile(g, -0.5, 0.5)
asset("Ceiling_1x1", g, extras=dict(footprint=[1, 1], thickness=0.04, place_y=3.0,
                                    pivot="bottom-center, cell center; node 'Socket_Center' = future light/tray anchor"))
ASSETS[-1]["sockets"] = ["Socket_Center"]

# 14 Ceiling_Edge: perimeter tile that stops at the wall face (-Z side), wall on cell boundary z=-0.5
g = Geo(); ceiling_tile(g, -0.45, 0.5)
asset("Ceiling_Edge", g, extras=dict(footprint=[1, 0.95], thickness=0.04, place_y=3.0, wall_side="-Z",
                                     pivot="bottom-center of the 1x1 cell (rotate in 90 deg steps)"))
ASSETS[-1]["sockets"] = ["Socket_Center"]

# 15 Structural_Floor (slab; place at y=3.20)
g = Geo()
g.box("M_Concrete", (-0.5, 0.20, -0.5), (0.5, 0.30, 0.5), ())
RB = 0.05
g.box("M_Concrete", (-0.5, 0, 0.5 - RB), (0.5, 0.20, 0.5), ("+y", "-y", "-z"))
g.box("M_Concrete", (-0.5, 0, -0.5), (0.5, 0.20, -0.5 + RB), ("+y", "-y", "+z"))
g.box("M_Concrete", (0.5 - RB, 0, -0.5 + RB), (0.5, 0.20, 0.5 - RB), ("+y", "-y", "-z", "+z", "-x"))
g.box("M_Concrete", (-0.5, 0, -0.5 + RB), (-0.5 + RB, 0.20, 0.5 - RB), ("+y", "-y", "-z", "+z", "+x"))
asset("Structural_Floor", g, extras=dict(footprint=[1, 1], thickness=0.30, place_y=H, storey_pitch=H + 0.30,
                                         pivot="bottom-center, cell center"))

# 16 Structural_Column (stands on floor surface; slab underside at y=3.20)
g = Geo()
g.box("M_Trim", (-0.20, FT, -0.20), (0.20, FT + 0.05, 0.20), ("-y",))
g.box("M_Concrete", (-0.15, FT + 0.05, -0.15), (0.15, H - 0.05, 0.15), ("-y", "+y"))
g.box("M_Trim", (-0.20, H - 0.05, -0.20), (0.20, H, 0.20), ("+y",))
asset("Structural_Column", g, extras=dict(size=0.30, height=H, pivot="bottom-center at floor-slab level (shaft starts at floor top, y=0.05)"))

# 17 Wall_Opening (2 m cased opening, clear 1.90 x 2.15 - fits Door_Double or open passage)
g = Geo(); frame(g, 1.0)
asset("Wall_Opening", g, extras=dict(width=2.0, clear_width=1.9, clear_height=OPEN_H, thickness=T, height=H,
                                     pivot="bottom-center, on grid line"))


# ---------------------------------------------------------------- GLB writer
def write_glb(a, path):
    bin_ = bytearray(); views = []; accs = []; meshes = []; mats = []; nodes = []
    matidx = {n: i for i, n in enumerate(MAT_ORDER)}
    for n in MAT_ORDER:
        d = MATS[n]
        m = dict(name=n, pbrMetallicRoughness=dict(baseColorFactor=list(d["c"]), metallicFactor=d["m"], roughnessFactor=d["r"]),
                 doubleSided=bool(d.get("blend")))
        if d.get("blend"):
            m["alphaMode"] = "BLEND"
        mats.append(m)

    def add_view(data, target):
        while len(bin_) % 4: bin_.append(0)
        views.append(dict(buffer=0, byteOffset=len(bin_), byteLength=len(data), target=target))
        bin_.extend(data)
        return len(views) - 1

    def add_mesh(name, geo):
        prims = []
        for mname, d in geo.prims.items():
            pos = d["p"]
            mn = [min(p[k] for p in pos) for k in range(3)]
            mx = [max(p[k] for p in pos) for k in range(3)]
            pv = add_view(b"".join(struct.pack("<3f", *p) for p in pos), 34962)
            nv = add_view(b"".join(struct.pack("<3f", *p) for p in d["n"]), 34962)
            uv = add_view(b"".join(struct.pack("<2f", *p) for p in d["uv"]), 34962)
            iv = add_view(b"".join(struct.pack("<H", i) for i in d["i"]), 34963)
            base = len(accs)
            accs.append(dict(bufferView=pv, componentType=5126, count=len(pos), type="VEC3", min=mn, max=mx))
            accs.append(dict(bufferView=nv, componentType=5126, count=len(pos), type="VEC3"))
            accs.append(dict(bufferView=uv, componentType=5126, count=len(pos), type="VEC2"))
            accs.append(dict(bufferView=iv, componentType=5123, count=len(d["i"]), type="SCALAR"))
            prims.append(dict(attributes=dict(POSITION=base, NORMAL=base+1, TEXCOORD_0=base+2), indices=base+3,
                              material=matidx[mname], mode=4))
        meshes.append(dict(name=name, primitives=prims))
        return len(meshes) - 1

    def add_node(spec, root=False):
        node = dict(name=spec["name"])
        if spec["t"] != (0, 0, 0):
            node["translation"] = list(spec["t"])
        if spec.get("extras"):
            node["extras"] = spec["extras"]
        idx = len(nodes); nodes.append(node)
        if spec.get("geo") is not None:
            node["mesh"] = add_mesh(spec["name"] + "_mesh", spec["geo"])
        kids = [add_node(c) for c in spec.get("children", [])]
        for s in spec.get("sockets", []):
            kids.append(len(nodes)); nodes.append(dict(name=s))
        if kids:
            node["children"] = kids
        return idx

    add_node(a, True)
    j = dict(asset=dict(version="2.0", generator="ModularKit procedural v1"), scene=0, scenes=[dict(nodes=[0])],
             nodes=nodes, meshes=meshes, materials=mats, accessors=accs, bufferViews=views,
             buffers=[dict(byteLength=len(bin_))])
    js = json.dumps(j, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    while len(bin_) % 4: bin_.append(0)
    total = 12 + 8 + len(js) + 8 + len(bin_)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(bin_), b"BIN\0")); f.write(bin_)


if __name__ == "__main__":
    for a in ASSETS:
        write_glb(a, os.path.join(OUT, a["name"] + ".glb"))
    print("wrote", len(ASSETS), "assets to", OUT)
