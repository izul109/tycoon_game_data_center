#!/usr/bin/env python3
"""Vertical Infrastructure Kit generator -> glTF 2.0 binary (.glb), Godot 4.x ready.
Units: meters. Y-up. Forward = -Z (Godot convention). Grid 1x1 m.
"""
import json, math, os, struct

OUT = "/mnt/user-data/outputs/VerticalKit"
os.makedirs(OUT + "/assets", exist_ok=True)

# ---------------------------------------------------------------- constants
FLOOR_H = 4.0          # floor-to-floor
RISE, TREAD, STEPS = 0.20, 0.30, 10
STAIR_W = 1.0          # overall (treads 0.9 + 2 stringers 0.05)
CABIN_FLOOR_T = 0.08   # cabin platform thickness (cabin pivot sits this far below landing sill)

MATS = {
    "M_Concrete":      ((0.62, 0.62, 0.64, 1), 0.0, 0.90, None),
    "M_Steel_Dark":    ((0.16, 0.18, 0.20, 1), 0.7, 0.50, None),
    "M_Steel_Light":   ((0.66, 0.68, 0.70, 1), 0.8, 0.40, None),
    "M_Panel":         ((0.80, 0.82, 0.84, 1), 0.2, 0.60, None),
    "M_Tread":         ((0.22, 0.23, 0.25, 1), 0.3, 0.85, None),
    "M_Safety_Yellow": ((0.95, 0.74, 0.08, 1), 0.1, 0.60, None),
    "M_Accent_Blue":   ((0.08, 0.42, 0.85, 1), 0.0, 0.50, (0.05, 0.30, 0.70)),
}

# ---------------------------------------------------------------- vector utils
sub = lambda a, b: (a[0]-b[0], a[1]-b[1], a[2]-b[2])
add = lambda a, b: (a[0]+b[0], a[1]+b[1], a[2]+b[2])
mul = lambda a, k: (a[0]*k, a[1]*k, a[2]*k)
dot = lambda a, b: a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
cross = lambda a, b: (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    l = math.sqrt(dot(a, a)); return (a[0]/l, a[1]/l, a[2]/l)
def rnd(v): return tuple(round(c, 5) + 0.0 for c in v)

def uvf(p, n):
    r = (0, 1, 0) if abs(n[1]) < 0.9 else (1, 0, 0)
    u = norm(cross(n, r)); v = cross(n, u)
    return (round(dot(p, u), 5), round(dot(p, v), 5))

# ---------------------------------------------------------------- mesh
class Mesh:
    def __init__(self, name):
        self.name = name; self.p = {}
    def _prim(self, m):
        return self.p.setdefault(m, {"pos": [], "nor": [], "uv": [], "idx": []})
    def poly(self, mat, verts, n):
        verts = [rnd(v) for v in verts]
        cr = cross(sub(verts[1], verts[0]), sub(verts[2], verts[0]))
        if math.sqrt(dot(cr, cr)) < 1e-9: return
        if dot(cr, n) < 0: verts = verts[::-1]
        pr = self._prim(mat); b = len(pr["pos"])
        for v in verts:
            pr["pos"].append(v); pr["nor"].append(n); pr["uv"].append(uvf(v, n))
        for i in range(1, len(verts)-1): pr["idx"] += [b, b+i, b+i+1]
    def box(self, mat, mn, mx, skip=()):
        x0, y0, z0 = mn; x1, y1, z1 = mx
        F = {"+x": ((x1,y0,z0),(x1,y1,z0),(x1,y1,z1),(x1,y0,z1),(1,0,0)),
             "-x": ((x0,y0,z0),(x0,y0,z1),(x0,y1,z1),(x0,y1,z0),(-1,0,0)),
             "+y": ((x0,y1,z0),(x0,y1,z1),(x1,y1,z1),(x1,y1,z0),(0,1,0)),
             "-y": ((x0,y0,z0),(x1,y0,z0),(x1,y0,z1),(x0,y0,z1),(0,-1,0)),
             "+z": ((x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1),(0,0,1)),
             "-z": ((x0,y0,z0),(x0,y1,z0),(x1,y1,z0),(x1,y0,z0),(0,0,-1))}
        for k, f in F.items():
            if k in skip: continue
            self.poly(mat, f[:4], f[4])
    def cbox(self, mat, c, size, skip=()):
        h = [s/2 for s in size]
        self.box(mat, (c[0]-h[0], c[1]-h[1], c[2]-h[2]), (c[0]+h[0], c[1]+h[1], c[2]+h[2]), skip)
    def beam(self, mat, p0, p1, w, h):
        """Oriented bar between p0,p1 (in YZ plane), w across X, h perpendicular."""
        d = norm(sub(p1, p0)); side = (1, 0, 0)
        up = cross(d, side)
        if up[1] < 0: up = mul(up, -1)
        def c(e, sx, su): return add(add(e, mul(side, sx*w/2)), mul(up, su*h/2))
        A = [c(p0,-1,-1), c(p0,1,-1), c(p0,1,1), c(p0,-1,1)]
        B = [c(p1,-1,-1), c(p1,1,-1), c(p1,1,1), c(p1,-1,1)]
        self.poly(mat, [A[3], A[2], A[1], A[0]], mul(d, -1))
        self.poly(mat, B, d)
        self.poly(mat, [A[0], A[1], B[1], B[0]], mul(up, -1))
        self.poly(mat, [A[3], A[2], B[2], B[3]], up)
        self.poly(mat, [A[0], A[3], B[3], B[0]], mul(side, -1))
        self.poly(mat, [A[1], A[2], B[2], B[1]], side)
    def extrude_profile(self, mat, prof, x0, x1):
        """prof = [(s,y)...] polygon; s maps to -Z (forward). Extruded along X."""
        P = [(-s, y) for s, y in prof]  # (z,y)
        area = sum(P[i][0]*P[(i+1) % len(P)][1] - P[(i+1) % len(P)][0]*P[i][1] for i in range(len(P)))
        for tri in triangulate(P):
            for x, nx in ((x0, -1), (x1, 1)):
                self.poly(mat, [(x, P[i][1], P[i][0]) for i in tri], (nx, 0, 0))
        for i in range(len(P)):
            a, b = P[i], P[(i+1) % len(P)]
            dz, dy = b[0]-a[0], b[1]-a[1]
            if abs(dz)+abs(dy) < 1e-9: continue
            n = (0, -dz, dy) if area > 0 else (0, dz, -dy)   # outward
            n = norm(n)
            self.poly(mat, [(x0, a[1], a[0]), (x1, a[1], a[0]), (x1, b[1], b[0]), (x0, b[1], b[0])], n)

def triangulate(P):
    n = len(P); idx = list(range(n))
    area = sum(P[i][0]*P[(i+1) % n][1] - P[(i+1) % n][0]*P[i][1] for i in range(n))
    if area < 0: idx.reverse()
    def inside(p, a, b, c):
        d1 = (p[0]-b[0])*(a[1]-b[1]) - (a[0]-b[0])*(p[1]-b[1])
        d2 = (p[0]-c[0])*(b[1]-c[1]) - (b[0]-c[0])*(p[1]-c[1])
        d3 = (p[0]-a[0])*(c[1]-a[1]) - (c[0]-a[0])*(p[1]-a[1])
        return d1 > 1e-9 and d2 > 1e-9 and d3 > 1e-9
    tris = []
    while len(idx) > 3:
        for k in range(len(idx)):
            i0, i1, i2 = idx[k-1], idx[k], idx[(k+1) % len(idx)]
            a, b, c = P[i0], P[i1], P[i2]
            if (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0]) <= 1e-9: continue
            if any(inside(P[j], a, b, c) for j in idx if j not in (i0, i1, i2)): continue
            tris.append((i0, i1, i2)); idx.pop(k); break
        else:
            raise RuntimeError("ear clipping failed")
    tris.append(tuple(idx)); return tris

# ---------------------------------------------------------------- node
class Node:
    def __init__(self, name, mesh=None, t=(0, 0, 0), ry=0.0, children=None, extras=None):
        self.name, self.mesh, self.t, self.ry = name, mesh, t, ry
        self.children = children or []; self.extras = extras

# ---------------------------------------------------------------- assets
def stair_main():
    m = Mesh("Stair_Main")
    for i in range(1, STEPS+1):
        s0 = TREAD*(i-1); top = RISE*i
        m.box("M_Tread", (-0.45, top-0.05, -(s0+TREAD)), (0.45, top, -s0))                       # tread
        m.box("M_Steel_Dark", (-0.45, top-RISE, -(s0+0.03)), (0.45, top-0.05, -s0))                # riser
    return m

def stair_side():
    prof = [(0, 0), (0, RISE)]
    for i in range(1, STEPS+1):
        prof += [(TREAD*i, RISE*i)] + ([(TREAD*i, RISE*(i+1))] if i < STEPS else [])
    prof += [(TREAD*STEPS, RISE*STEPS-0.25), (0.375, 0.0)]
    m = Mesh("Stair_Side"); m.extrude_profile("M_Steel_Dark", prof, -0.025, 0.025); return m

def stair_landing():
    m = Mesh("Stair_Landing")
    m.box("M_Tread", (-0.5, 1.96, -0.5), (0.5, 2.0, 0.5))
    m.box("M_Steel_Dark", (-0.5, 1.9, 0.46), (0.5, 1.96, 0.5))
    m.box("M_Steel_Dark", (-0.5, 1.9, -0.5), (0.5, 1.96, -0.46))
    m.box("M_Steel_Dark", (0.46, 1.9, -0.46), (0.5, 1.96, 0.46))
    m.box("M_Steel_Dark", (-0.5, 1.9, -0.46), (-0.46, 1.96, 0.46))
    for sx in (-1, 1):
        for sz in (-1, 1):
            m.cbox("M_Steel_Dark", (sx*0.46, 0.95, sz*0.46), (0.08, 1.9, 0.08))
    return m

def stair_railing():
    m = Mesh("Stair_Railing")
    posts = [(1, 0.15), (5, 1.35), (10, 2.85)]
    for i, s in posts:
        y = RISE*i
        m.cbox("M_Steel_Dark", (0, y+0.4375, -s), (0.04, 0.875, 0.04))
    k = 2/3
    m.beam("M_Steel_Light", (0, k*0.0+1.0, 0.0), (0, k*3.0+1.0, -3.0), 0.05, 0.05)   # handrail
    m.beam("M_Steel_Light", (0, 0.2+0.45, -0.15), (0, 2.0+0.45, -2.85), 0.03, 0.03)  # mid rail
    return m

def elevator_shaft():
    m = Mesh("Elevator_Shaft"); C = "M_Concrete"
    m.box(C, (-1.5, 0, -1.5), (1.5, FLOOR_H, -1.3))                  # back
    m.box(C, (-1.5, 0, -1.3), (-1.3, FLOOR_H, 1.3))                  # left
    m.box(C, (1.3, 0, -1.3), (1.5, FLOOR_H, 1.3))                    # right
    m.box(C, (-1.5, 0, 1.3), (-0.8, FLOOR_H, 1.5))                   # front-left
    m.box(C, (0.8, 0, 1.3), (1.5, FLOOR_H, 1.5))                     # front-right
    m.box(C, (-0.8, 2.2, 1.3), (0.8, FLOOR_H, 1.5))                  # header
    for sx in (-1, 1):                                               # guide rails
        m.box("M_Steel_Dark", (1.24 if sx > 0 else -1.3, 0, -0.05), (1.3 if sx > 0 else -1.24, FLOOR_H, 0.05))
    return m

def elevator_cabin():
    m = Mesh("Elevator_Cabin"); W, P, T = "M_Panel", "M_Steel_Light", CABIN_FLOOR_T
    m.box("M_Tread", (-1.0, 0, -1.2), (1.0, T, 1.2))                 # platform
    m.box("M_Steel_Dark", (-1.0, 2.32, -1.2), (1.0, 2.4, 1.2))       # ceiling
    m.box(P, (-1.0, T, -1.2), (-0.94, 2.32, 1.2))                    # left wall
    m.box(P, (0.94, T, -1.2), (1.0, 2.32, 1.2))                      # right wall
    m.box(W, (-0.94, T, -1.2), (0.94, 2.32, -1.14))                  # back wall
    m.box(W, (-0.94, T, 1.14), (-0.7, 2.18, 1.2))                    # front jamb L
    m.box(W, (0.7, T, 1.14), (0.94, 2.18, 1.2))                      # front jamb R
    m.box(W, (-0.94, 2.18, 1.14), (0.94, 2.32, 1.2))                 # front header
    m.box("M_Steel_Dark", (-0.6, 0.9, -1.14), (0.6, 0.94, -1.10))    # back handrail
    return m

def elevator_door_panel():
    m = Mesh("Elevator_Door_Panel")
    m.box("M_Steel_Light", (-0.345, 0.02, -0.02), (0.345, 2.08, 0.02))
    return m

def elevator_frame():
    m = Mesh("Elevator_Frame")
    m.box("M_Steel_Dark", (-0.8, 0, -0.1), (-0.7, 2.2, 0.1))
    m.box("M_Steel_Dark", (0.7, 0, -0.1), (0.8, 2.2, 0.1))
    m.box("M_Steel_Dark", (-0.7, 2.1, -0.1), (0.7, 2.2, 0.1))
    return m

def elevator_control():
    m = Mesh("Elevator_Control")
    m.box("M_Steel_Dark", (-0.11, 0, 0), (0.11, 0.5, 0.04))
    m.box("M_Accent_Blue", (-0.07, 0.40, 0.04), (0.07, 0.45, 0.045))   # floor display
    for r in range(3):
        for c in (-1, 1):
            m.cbox("M_Steel_Light", (c*0.045, 0.30 - r*0.08, 0.0475), (0.04, 0.04, 0.015))
    return m

def utility_riser():
    m = Mesh("Utility_Riser"); S, R = "M_Panel", "M_Safety_Yellow"
    m.box(S, (-0.5, 0, -0.5), (0.5, FLOOR_H, -0.45))                  # back
    m.box(S, (-0.5, 0, -0.45), (-0.45, FLOOR_H, 0.5))                 # left
    m.box(S, (0.45, 0, -0.45), (0.5, FLOOR_H, 0.5))                   # right
    m.box(S, (-0.45, 0, 0.45), (0.45, 0.2, 0.5))                      # plinth
    m.box(S, (-0.45, 3.8, 0.45), (0.45, FLOOR_H, 0.5))                # lintel
    m.box(S, (-0.45, 0.2, 0.45), (-0.35, 3.8, 0.5))                   # front post L
    m.box(S, (0.35, 0.2, 0.45), (0.45, 3.8, 0.5))                     # front post R
    for sx in (-1, 1):                                                # cable ladder rails
        m.box(R, (0.26 if sx > 0 else -0.30, 0, -0.45), (0.30 if sx > 0 else -0.26, FLOOR_H, -0.40))
    for k in range(8):                                                # rungs
        y = 0.25 + 0.5*k
        m.box(R, (-0.26, y-0.015, -0.45), (0.26, y+0.015, -0.42))
    return m

def floor_threshold():
    m = Mesh("Floor_Threshold")
    m.box("M_Steel_Light", (-0.5, 0, -0.15), (0.5, 0.03, 0.15))
    for z in (-0.07, 0.07):
        m.box("M_Steel_Dark", (-0.45, 0.03, z-0.02), (0.45, 0.035, z+0.02))
    return m

def guard_rail():
    m = Mesh("Guard_Rail"); S = "M_Steel_Light"
    for x0, x1, p0, p1 in ((-0.5, -0.45, -0.5, -0.38), (0.45, 0.5, 0.38, 0.5)):
        m.box("M_Steel_Dark", (p0, 0, -0.06), (p1, 0.01, 0.06))      # base plate
        m.box(S, (x0, 0.01, -0.025), (x1, 1.1, 0.025))               # post
    m.box(S, (-0.45, 1.05, -0.025), (0.45, 1.10, 0.025))              # top rail
    m.box(S, (-0.45, 0.50, -0.02), (0.45, 0.54, 0.02))                # mid rail
    m.box("M_Safety_Yellow", (-0.45, 0.01, -0.01), (0.45, 0.11, 0.01))  # toe board
    return m

def safety_barrier():
    m = Mesh("Safety_Barrier")
    for sx in (-1, 1):
        x0, x1 = (0.34, 0.5) if sx > 0 else (-0.5, -0.34)
        m.box("M_Steel_Dark", (x0, 0, -0.2), (x1, 0.02, 0.2))                    # foot plate
        c = sx*0.42
        m.box("M_Steel_Dark", (c-0.05, 0.02, -0.05), (c+0.05, 1.0, 0.05))        # post
    m.box("M_Safety_Yellow", (-0.37, 0.45, -0.04), (0.37, 0.53, 0.04))
    m.box("M_Safety_Yellow", (-0.37, 0.87, -0.04), (0.37, 0.95, 0.04))
    return m

# ---------------------------------------------------------------- build node library
stair_main_mesh = stair_main(); stair_side_mesh = stair_side()
M = {
    "Stair_Main": stair_main_mesh, "Stair_Landing": stair_landing(), "Stair_Railing": stair_railing(),
    "Stair_Side": stair_side_mesh, "Elevator_Shaft": elevator_shaft(), "Elevator_Cabin": elevator_cabin(),
    "Elevator_Frame": elevator_frame(), "Elevator_Control": elevator_control(),
    "Utility_Riser": utility_riser(), "Floor_Threshold": floor_threshold(),
    "Guard_Rail": guard_rail(), "Safety_Barrier": safety_barrier(),
}
door_panel = elevator_door_panel()

def make_door(name="Elevator_Door"):
    return Node(name, children=[
        Node("Door_Left", door_panel, t=(-0.35, 0, 0), extras={"slide_open_x": -0.7, "closed_x": -0.35}),
        Node("Door_Right", door_panel, t=(0.35, 0, 0), extras={"slide_open_x": 0.7, "closed_x": 0.35})],
        extras={"anim": "slide Door_Left/Door_Right along local X by slide_open_x (hidden in wall pocket)"})

def asset_nodes():
    d = {k: Node(k, v) for k, v in M.items()}
    d["Elevator_Door"] = make_door()
    d["Elevator_Cabin"].extras = {"stop_offset_y": -CABIN_FLOOR_T,
                                  "note": "place at landing_floor_y + stop_offset_y so cabin floor top is flush with sill"}
    return d

# ---------------------------------------------------------------- GLB writer
def write_glb(path, roots, scene="Scene"):
    mats = list(MATS); matidx = {m: i for i, m in enumerate(mats)}
    meshes, mesh_ids = [], {}
    nodes = []; blob = bytearray(); views, accs = [], []

    def add_view(data, target):
        while len(blob) % 4: blob.append(0)
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), "target": target})
        blob.extend(data); return len(views)-1

    def mesh_index(me):
        if id(me) in mesh_ids: return mesh_ids[id(me)]
        prims = []
        for mat, pr in me.p.items():
            pos, nor, uv, idx = pr["pos"], pr["nor"], pr["uv"], pr["idx"]
            pv = add_view(struct.pack("<%df" % (3*len(pos)), *[c for v in pos for c in v]), 34962)
            nv = add_view(struct.pack("<%df" % (3*len(nor)), *[c for v in nor for c in v]), 34962)
            tv = add_view(struct.pack("<%df" % (2*len(uv)), *[c for v in uv for c in v]), 34962)
            big = len(pos) > 65535
            iv = add_view(struct.pack(("<%dI" if big else "<%dH") % len(idx), *idx), 34963)
            mn = [min(v[i] for v in pos) for i in range(3)]; mx = [max(v[i] for v in pos) for i in range(3)]
            a0 = len(accs)
            accs.append({"bufferView": pv, "componentType": 5126, "count": len(pos), "type": "VEC3", "min": mn, "max": mx})
            accs.append({"bufferView": nv, "componentType": 5126, "count": len(nor), "type": "VEC3"})
            accs.append({"bufferView": tv, "componentType": 5126, "count": len(uv), "type": "VEC2"})
            accs.append({"bufferView": iv, "componentType": 5125 if big else 5123, "count": len(idx), "type": "SCALAR"})
            prims.append({"attributes": {"POSITION": a0, "NORMAL": a0+1, "TEXCOORD_0": a0+2}, "indices": a0+3,
                          "material": matidx[mat], "mode": 4})
        meshes.append({"name": me.name, "primitives": prims}); mesh_ids[id(me)] = len(meshes)-1
        return mesh_ids[id(me)]

    def emit(n):
        d = {"name": n.name}
        if n.mesh is not None: d["mesh"] = mesh_index(n.mesh)
        if any(n.t): d["translation"] = [round(c, 5) for c in n.t]
        if n.ry:
            h = math.radians(n.ry)/2; d["rotation"] = [0, round(math.sin(h), 6), 0, round(math.cos(h), 6)]
        if n.extras: d["extras"] = n.extras
        i = len(nodes); nodes.append(d)
        ch = [emit(c) for c in n.children]
        if ch: d["children"] = ch
        return i

    root_ids = [emit(r) for r in roots]
    gm = []
    for name in mats:
        c, metal, rough, em = MATS[name]
        mm = {"name": name, "pbrMetallicRoughness": {"baseColorFactor": list(c), "metallicFactor": metal, "roughnessFactor": rough},
              "doubleSided": False}
        if em: mm["emissiveFactor"] = list(em)
        gm.append(mm)
    while len(blob) % 4: blob.append(0)
    gltf = {"asset": {"version": "2.0", "generator": "VerticalKit generator"},
            "scene": 0, "scenes": [{"name": scene, "nodes": root_ids}], "nodes": nodes, "meshes": meshes,
            "materials": gm, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    js = json.dumps(gltf, separators=(",", ":")).encode()
    while len(js) % 4: js += b" "
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A)); f.write(js)
        f.write(struct.pack("<II", len(blob), 0x004E4942)); f.write(bytes(blob))

# ---------------------------------------------------------------- export
A = asset_nodes()
ORDER = ["Stair_Main", "Stair_Landing", "Stair_Railing", "Stair_Side", "Elevator_Shaft", "Elevator_Cabin",
         "Elevator_Door", "Elevator_Frame", "Elevator_Control", "Utility_Riser", "Floor_Threshold",
         "Guard_Rail", "Safety_Barrier"]
for n in ORDER:
    write_glb(f"{OUT}/assets/{n}.glb", [A[n]], n)

# kit sheet (display only, assets laid out in a row; every root keeps its exact asset name)
SHEET_X = {"Stair_Main": 0.5, "Stair_Landing": 2.5, "Stair_Railing": 4.5, "Stair_Side": 6.5, "Elevator_Shaft": 10,
           "Elevator_Cabin": 15, "Elevator_Door": 18, "Elevator_Frame": 20, "Elevator_Control": 22,
           "Utility_Riser": 24, "Floor_Threshold": 26, "Guard_Rail": 28, "Safety_Barrier": 30}
sheet = []
for n in ORDER:
    A2 = asset_nodes()[n]; A2.t = (SHEET_X[n], 0, 0); sheet.append(A2)
write_glb(f"{OUT}/Kit_Sheet.glb", sheet, "Kit_Sheet")

# ---------------------------------------------------------------- assembly test
def inst(name, key, t, ry=0.0):
    return Node(name, M[key], t=t, ry=ry)

asm = []
# Stair stack: flight1 (ground -> +2.0), landing x2, flight2 (U-turn, +2.0 -> +4.0)
f1 = Node("Stair_F1", t=(0.5, 0, 0), children=[
    inst("Stair_Main", "Stair_Main", (0, 0, 0)),
    inst("Stair_Side_L", "Stair_Side", (-0.475, 0, 0)), inst("Stair_Side_R", "Stair_Side", (0.475, 0, 0)),
    inst("Stair_Railing_L", "Stair_Railing", (-0.475, 0, 0)), inst("Stair_Railing_R", "Stair_Railing", (0.475, 0, 0))])
f2 = Node("Stair_F2", t=(1.5, 2.0, -3.0), ry=180, children=[
    inst("Stair_Main", "Stair_Main", (0, 0, 0)),
    inst("Stair_Side_L", "Stair_Side", (-0.475, 0, 0)), inst("Stair_Side_R", "Stair_Side", (0.475, 0, 0)),
    inst("Stair_Railing_Outer", "Stair_Railing", (-0.475, 0, 0))])
asm += [f1, f2, inst("Stair_Landing_A", "Stair_Landing", (0.5, 0, -3.5)), inst("Stair_Landing_B", "Stair_Landing", (1.5, 0, -3.5))]
# guard rails around upper opening (floor y=4)
for i, z in enumerate((-3.5, -2.5, -1.5, -0.5)):
    asm.append(inst(f"Guard_Rail_W{i}", "Guard_Rail", (0.0, FLOOR_H, z), 90))
for i, x in enumerate((0.5, 1.5)):
    asm.append(inst(f"Guard_Rail_N{i}", "Guard_Rail", (x, FLOOR_H, -4.0)))
asm += [inst("Guard_Rail_E0", "Guard_Rail", (2.0, FLOOR_H, -3.5), 90), inst("Guard_Rail_S0", "Guard_Rail", (0.5, FLOOR_H, 0.0))]
# elevator (center 5.5,-1.5; door faces +Z)
ex, ez = 5.5, -1.5
asm += [inst("Elevator_Shaft", "Elevator_Shaft", (ex, 0, ez)),
        inst("Elevator_Cabin", "Elevator_Cabin", (ex, -CABIN_FLOOR_T, ez)),
        inst("Elevator_Frame", "Elevator_Frame", (ex, 0, ez+1.4)),
        Node("Elevator_Door_Hoistway", children=make_door().children, t=(ex, 0, ez+1.4)),
        Node("Elevator_Door_Cabin", children=make_door().children, t=(ex, 0, ez+1.17)),
        inst("Elevator_Control", "Elevator_Control", (ex+0.94, 0.9, ez+0.8), -90),
        inst("Floor_Threshold_A", "Floor_Threshold", (ex-0.5, 0, ez+1.4)),
        inst("Floor_Threshold_B", "Floor_Threshold", (ex+0.5, 0, ez+1.4))]
# riser + barriers
asm += [inst("Utility_Riser", "Utility_Riser", (8.5, 0, -2.5)),
        inst("Safety_Barrier_A", "Safety_Barrier", (8.0, 0, -1.4)), inst("Safety_Barrier_B", "Safety_Barrier", (9.0, 0, -1.4))]
# reference slabs (NOT part of kit)
ref = Mesh("REF_Slabs")
ref.box("M_Concrete", (-2, -0.2, -6), (10, 0, 3))
holes = {(x, z) for x in (0, 1) for z in (-4, -3, -2, -1)} | {(x, z) for x in (4, 5, 6) for z in (-3, -2, -1)} | {(8, -3)}
for x in range(-2, 10):
    for z in range(-6, 3):
        if (x, z) not in holes: ref.box("M_Concrete", (x, FLOOR_H-0.2, z), (x+1, FLOOR_H, z+1))
asm.append(Node("REF_Slabs", ref))
write_glb(f"{OUT}/Assembly_Test.glb", asm, "Assembly_Test")

# ---------------------------------------------------------------- validation report
def bounds(me):
    P = [v for pr in me.p.values() for v in pr["pos"]]
    return [min(v[i] for v in P) for i in range(3)], [max(v[i] for v in P) for i in range(3)]
def tris(me): return sum(len(pr["idx"])//3 for pr in me.p.values())
def verts(me): return sum(len(pr["pos"]) for pr in me.p.values())
def volume(me):
    t = 0
    for pr in me.p.values():
        for i in range(0, len(pr["idx"]), 3):
            a, b, c = [pr["pos"][k] for k in pr["idx"][i:i+3]]; t += dot(a, cross(b, c))/6
    return t
def bad_tris(me):
    n = 0
    for pr in me.p.values():
        for i in range(0, len(pr["idx"]), 3):
            a, b, c = [pr["pos"][k] for k in pr["idx"][i:i+3]]
            g = cross(sub(b, a), sub(c, a)); nn = pr["nor"][pr["idx"][i]]
            if dot(g, nn) <= 0: n += 1
    return n

report = []
allm = dict(M); allm["Elevator_Door(panel)"] = door_panel
print(f"{'asset':22}{'min(x,y,z)':>26}{'max(x,y,z)':>26}{'size':>22}{'tris':>6}{'verts':>7}{'vol+':>6}{'badN':>5}")
for k, me in allm.items():
    mn, mx = bounds(me); sz = [round(b-a, 3) for a, b in zip(mn, mx)]
    print(f"{k:22}{str(tuple(round(c,3) for c in mn)):>26}{str(tuple(round(c,3) for c in mx)):>26}{str(tuple(sz)):>22}"
          f"{tris(me):>6}{verts(me):>7}{('OK' if volume(me)>0 else 'NEG'):>6}{bad_tris(me):>5}")
    report.append((k, mn, mx, sz, tris(me), verts(me)))
json.dump([(r[0], r[1], r[2], r[3], r[4], r[5]) for r in report], open("/home/claude/report.json", "w"))
print("total tris (kit):", sum(r[4] for r in report))
