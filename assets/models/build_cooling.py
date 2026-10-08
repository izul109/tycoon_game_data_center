#!/usr/bin/env python3
"""
Fictional modular cooling family -> GLB (glTF 2.0), Godot 4.x ready.  Pure Python.
Design units: millimeters, exported in meters.  Y up, +Z = front/outward of every unit.

Pivots
  Cooling_Floor, Cooling_Compact : bottom-center
  Cooling_Wall, Cooling_ControlPanel : center of the back (mounting) plane, unit protrudes +Z
  Cooling_Ceiling : center of the mounting plane at the ceiling (y=0), unit hangs toward -Y

Each asset = 2 surfaces: M_Cooling (shared 256x256 atlas) + M_Status (LED quads, shader-driven).
Gameplay anchors are empty Node3D children; their local +Z axis points along the air/interaction direction.
"""
import json, struct, zlib, os, sys

S = 0.001
N_LED = 16
PAL = {
    "chassis": (205, 208, 212), "chassis_dk": (120, 125, 132), "dark": (14, 15, 18), "accent": (50, 160, 215),
    "panel": (46, 50, 57), "button": (88, 94, 104), "warn": (250, 200, 40), "plinth": (60, 64, 70),
}
PAL_ORDER = list(PAL)
AW = AH = 256
SW = 32
GL = {"0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"], "2": ["111", "001", "111", "100", "111"],
      "3": ["111", "001", "111", "001", "111"], "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
      "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "001", "010", "010"], "8": ["111", "101", "111", "101", "111"],
      "9": ["111", "101", "111", "001", "111"], ".": ["0", "0", "0", "0", "1"], "C": ["111", "100", "100", "100", "111"]}
DISP = (0, 0, 128, 64)                       # display graphic region in the atlas (px)


def make_atlas():
    px = bytearray(AW * AH * 3)

    def fill(x0, y0, w, h, c):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                o = (y * AW + x) * 3; px[o:o + 3] = bytes(c)
    fill(0, 0, AW, AH, PAL["dark"])
    for k, n in enumerate(PAL_ORDER):
        fill((k % 8) * SW, 128 + (k // 8) * SW, SW, SW, PAL[n])
    fill(0, 0, 128, 64, (8, 34, 40))
    sc = 6; x = 13
    for ch in "22.5C":
        g = GL[ch]; w = len(g[0])
        for gy, row in enumerate(g):
            for gx, b in enumerate(row):
                if b == "1": fill(x + gx * sc, 6 + gy * sc, sc, sc, (90, 235, 240))
        x += w * sc + sc
    for i in range(10):                      # load bar graph
        h = 4 + i * 1
        fill(8 + i * 12, 56 - h, 8, h, (60, 210, 120) if i < 7 else (40, 70, 70))
    return bytes(px)


def png_bytes(w, h, rgb):
    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def ch(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + ch(b"IDAT", zlib.compress(raw, 9)) + ch(b"IEND", b"")


def sw(name):
    k = PAL_ORDER.index(name)
    return [(((k % 8) * SW + SW / 2) / AW, (128 + (k // 8) * SW + SW / 2) / AH)] * 4


def disp_uv():
    x0, y0, w, h = DISP
    return [(x0 / AW, (y0 + h) / AH), ((x0 + w) / AW, (y0 + h) / AH), ((x0 + w) / AW, y0 / AH), (x0 / AW, y0 / AH)]


def led_uv(i): return [((i + .5) / N_LED, .5)] * 4


def _sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


class Mesh:
    def __init__(self):
        self.prims = {"main": dict(p=[], n=[], uv=[], i=[]), "led": dict(p=[], n=[], uv=[], i=[])}
        self.leds = []

    def face(self, prim, ax, c, ra, rb, sign, uv):
        a, b = {0: (2, 1), 1: (0, 2), 2: (0, 1)}[ax]
        pts = []
        for ia, ib in ((0, 0), (1, 0), (1, 1), (0, 1)):
            v = [0.0, 0.0, 0.0]; v[ax] = c; v[a] = ra[ia]; v[b] = rb[ib]; pts.append(tuple(v))
        n = [0, 0, 0]; n[ax] = sign
        order = [0, 1, 2, 3]
        if _dot(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])), n) < 0: order = [0, 3, 2, 1]
        d = self.prims[prim]; base = len(d["p"])
        for k in order:
            d["p"].append(tuple(round(q * S, 7) for q in pts[k])); d["n"].append(tuple(n)); d["uv"].append(uv[k])
        d["i"] += [base, base + 1, base + 2, base, base + 2, base + 3]

    def box(self, col, lo, hi, skip=()):
        for ax in range(3):
            for sg in (-1, 1):
                if (("-" if sg < 0 else "+") + "xyz"[ax]) in skip: continue
                a, b = {0: (2, 1), 1: (0, 2), 2: (0, 1)}[ax]
                self.face("main", ax, lo[ax] if sg < 0 else hi[ax], (lo[a], hi[a]), (lo[b], hi[b]), sg, sw(col))

    # decals (0.5 mm proud) on the 6 principal planes; (a,b) ranges follow face() axis mapping
    def front(self, x0, x1, y0, y1, z, col, lift=0.5, uv=None):   # +Z
        self.face("main", 2, z + lift, (x0, x1), (y0, y1), +1, uv or sw(col))

    def led_front(self, cx, cy, z, idx, w=14, h=9):
        self.face("led", 2, z + 1.0, (cx - w / 2, cx + w / 2), (cy - h / 2, cy + h / 2), +1, led_uv(idx)); self.leds.append(idx)

    def slats_front(self, x0, x1, y0, y1, z, n, col="panel"):
        pitch = (y1 - y0) / n
        for k in range(n):
            self.front(x0 + 6, x1 - 6, y0 + k * pitch + pitch * 0.25, y0 + k * pitch + pitch * 0.65, z, col, lift=1.0)


def quat_for(n):
    s = 0.70710678
    return {(0, 0, 1): (0, 0, 0, 1), (0, 1, 0): (-s, 0, 0, s), (0, -1, 0): (s, 0, 0, s), (0, 0, -1): (0, 1, 0, 0),
            (1, 0, 0): (0, s, 0, s), (-1, 0, 0): (0, -s, 0, s)}[tuple(n)]


def anchor(name, kind, x, y, z, n, **ex):
    return dict(name=name, t=(round(x * S, 6), round(y * S, 6), round(z * S, 6)), q=quat_for(n), extras=dict(kind=kind, direction=list(n), **ex))


# ------------------------------------------------------------------ assets
def floor_unit():
    m = Mesh(); W, D, Hh = 800, 900, 1900
    m.box("plinth", (-380, 0, -430), (380, 100, 430), skip=("-y", "+y"))
    m.box("chassis", (-W/2, 100, -D/2), (W/2, Hh, D/2), skip=("-y",))
    zf = D / 2
    # intake grille (front, upper)
    m.front(-340, 340, 1250, 1800, zf, "dark"); m.slats_front(-340, 340, 1250, 1800, zf, 12)
    m.front(-340, 340, 1180, 1196, zf, "accent")
    # control panel + display + buttons + LEDs
    m.front(-180, 180, 880, 1170, zf, "panel")
    m.front(-150, 10, 940, 1100, zf, "dark", lift=1.0, uv=disp_uv())
    for cx in (60, 125):
        for cy in (1040, 980):
            m.front(cx - 22, cx + 22, cy - 22, cy + 22, zf, "button", lift=1.0)
    for k, cx in enumerate((-120, -90, -60)): m.led_front(cx, 1140, zf, k)
    # service panel with seams and handle
    for (x0, x1, y0, y1) in ((-340, 340, 150, 156), (-340, 340, 814, 820), (-340, -334, 150, 820), (334, 340, 150, 820)):
        m.front(x0, x1, y0, y1, zf, "dark")
    m.box("dark", (270, 420, zf), (300, 560, zf + 14), skip=("-z",))
    # top outlet grille
    m.face("main", 1, 1900.5, (-300, 300), (-300, 300), +1, sw("dark"))
    for k in range(8):
        z0 = -290 + k * 72
        m.face("main", 1, 1901.0, (-290, 290), (z0, z0 + 34), +1, sw("panel"))
    # rear power connection box
    m.box("chassis_dk", (-60, 200, -D/2 - 45), (60, 330, -D/2), skip=("+z",))
    m.face("main", 2, -D/2 - 45.5, (-45, 45), (230, 280), -1, sw("dark"))
    m.face("main", 2, -D/2 - 45.5, (-55, 55), (300, 314), -1, sw("warn"))
    anchors = [anchor("Intake_01", "air_intake", 0, 1525, zf, (0, 0, 1)), anchor("Outlet_01", "air_outlet", 0, Hh, 0, (0, 1, 0)),
               anchor("Control_Panel", "control_panel", 0, 1025, zf, (0, 0, 1)), anchor("Service_Panel", "service_panel", 0, 485, zf, (0, 0, 1)),
               anchor("Power_Connection", "power", 0, 265, -D/2 - 45, (0, 0, -1))]
    return m, anchors, dict(footprint_m=[0.8, 0.9], height_m=1.9, pivot="bottom-center")


def compact_unit():
    m = Mesh(); W, D, Hh = 500, 600, 900
    m.box("plinth", (-230, 0, -280), (230, 60, 280), skip=("-y", "+y"))
    m.box("chassis", (-W/2, 60, -D/2), (W/2, Hh, D/2), skip=("-y",))
    zf = D / 2
    m.front(-200, 200, 560, 850, zf, "dark"); m.slats_front(-200, 200, 560, 850, zf, 7)
    m.front(-200, 200, 495, 510, zf, "accent")
    m.front(-200, 200, 300, 480, zf, "panel")
    m.front(-180, -10, 330, 450, zf, "dark", lift=1.0, uv=disp_uv())
    for cx in (60, 130): m.front(cx - 22, cx + 22, 360, 404, zf, "button", lift=1.0)
    for k, cx in enumerate((-160, -130, -100)): m.led_front(cx, 468, zf, k, 12, 8)
    for (x0, x1, y0, y1) in ((-200, 200, 90, 95), (-200, 200, 255, 260), (-200, -195, 90, 260), (195, 200, 90, 260)):
        m.front(x0, x1, y0, y1, zf, "dark")
    m.face("main", 1, Hh + 0.5, (-180, 180), (-200, 200), +1, sw("dark"))
    for k in range(5): m.face("main", 1, Hh + 1.0, (-170, 170), (-190 + k * 76, -190 + k * 76 + 36), +1, sw("panel"))
    m.box("chassis_dk", (-40, 120, -D/2 - 35), (40, 200, -D/2), skip=("+z",))
    m.face("main", 2, -D/2 - 35.5, (-28, 28), (140, 180), -1, sw("dark"))
    anchors = [anchor("Intake_01", "air_intake", 0, 705, zf, (0, 0, 1)), anchor("Outlet_01", "air_outlet", 0, Hh, 0, (0, 1, 0)),
               anchor("Control_Panel", "control_panel", 0, 390, zf, (0, 0, 1)), anchor("Service_Panel", "service_panel", 0, 175, zf, (0, 0, 1)),
               anchor("Power_Connection", "power", 0, 160, -D/2 - 35, (0, 0, -1))]
    return m, anchors, dict(footprint_m=[0.5, 0.6], height_m=0.9, pivot="bottom-center")


def wall_unit():
    m = Mesh(); W, Hh, D = 900, 300, 250
    for sx in (-300, 300):                                    # mounting brackets
        m.box("dark", (sx - 30, -130, 0), (sx + 30, 130, 14), skip=("+z",))
    m.box("chassis", (-W/2, -Hh/2, 14), (W/2, Hh/2, D), skip=("-z",))
    m.face("main", 1, Hh/2 + 0.5, (-400, 400), (40, 200), +1, sw("dark"))                   # intake (top)
    for k in range(6): m.face("main", 1, Hh/2 + 1.0, (-390, 390), (48 + k * 25, 48 + k * 25 + 12), +1, sw("panel"))
    m.face("main", 1, -Hh/2 - 0.5, (-400, 400), (30, 220), -1, sw("dark"))                  # outlet (bottom)
    for k in range(4): m.face("main", 1, -Hh/2 - 1.0, (-390, 390), (45 + k * 42, 45 + k * 42 + 20), -1, sw("panel"))
    m.front(-440, 440, -110, -96, D, "accent")
    m.front(150, 420, -80, 60, D, "panel")
    for k, cx in enumerate((200, 260, 320)): m.led_front(cx, 0, D, k, 24, 14)
    anchors = [anchor("Intake_01", "air_intake", 0, Hh/2, 120, (0, 1, 0)), anchor("Outlet_01", "air_outlet", 0, -Hh/2, 125, (0, -1, 0)),
               anchor("Bracket_L", "mount", -300, 0, 0, (0, 0, -1)), anchor("Bracket_R", "mount", 300, 0, 0, (0, 0, -1))]
    return m, anchors, dict(size_m=[0.9, 0.3, 0.25], pivot="center of back mounting plane (protrudes +Z)")


def ceiling_unit():
    m = Mesh(); W = 900; Hh = 260
    m.box("dark", (-480, -25, -480), (480, 0, 480), skip=("+y",))                           # mounting flange
    for sx in (-1, 1):
        for sz in (-1, 1):
            m.box("chassis_dk", (sx * 440 - 20, 0, sz * 440 - 20), (sx * 440 + 20, 100, sz * 440 + 20), skip=("-y",))
    m.box("chassis", (-W/2, -Hh, -W/2), (W/2, -25, W/2), skip=("+y",))
    y = -Hh - 0.5
    m.face("main", 1, y, (-300, 300), (-300, 300), -1, sw("dark"))                           # intake (center)
    for k in range(10): m.face("main", 1, y - 0.5, (-290, 290), (-290 + k * 58, -290 + k * 58 + 28), -1, sw("panel"))
    for sz in (-1, 1):                                                                       # outlets (2 side strips)
        z0, z1 = sorted((sz * 330, sz * 420))
        m.face("main", 1, y, (-420, 420), (z0, z1), -1, sw("dark"))
        for k in range(5): m.face("main", 1, y - 0.5, (-410 + k * 164, -410 + k * 164 + 120), (z0 + 12, z1 - 12), -1, sw("panel"))
    m.front(-440, 440, -150, -136, W/2, "accent")
    for k, cx in enumerate((300, 340, 380)): m.led_front(cx, -90, W/2, k, 24, 14)
    anchors = [anchor("Intake_01", "air_intake", 0, -Hh, 0, (0, -1, 0)), anchor("Outlet_01", "air_outlet", 0, -Hh, 375, (0, -1, 0)),
               anchor("Outlet_02", "air_outlet", 0, -Hh, -375, (0, -1, 0))]
    return m, anchors, dict(footprint_m=[0.96, 0.96], hang_m=Hh * S, pivot="mounting center at ceiling plane (y=0), unit hangs toward -Y")


def control_panel():
    m = Mesh()
    m.box("panel", (-100, -70, 0), (100, 70, 25), skip=("-z",))
    m.front(-85, 25, -40, 50, 25, "dark", lift=0.5, uv=disp_uv())
    for cx in (55, 82):
        for cy in (22, -12):
            m.box("button", (cx - 11, cy - 11, 25), (cx + 11, cy + 11, 31), skip=("-z",))
    for k, cx in enumerate((-70, -55, -40)): m.led_front(cx, 60, 25, k, 9, 6)
    m.front(-90, 90, -62, -56, 25, "accent")
    anchors = [anchor("Display", "display", -30, 5, 25, (0, 0, 1))] + [
        anchor(f"Button_{i+1:02d}", "button", cx, cy, 31, (0, 0, 1)) for i, (cx, cy) in enumerate(((55, 22), (82, 22), (55, -12), (82, -12)))]
    return m, anchors, dict(size_m=[0.2, 0.14, 0.031], pivot="center of back mounting plane (protrudes +Z)")


ASSETS = {"Cooling_Floor": floor_unit, "Cooling_Wall": wall_unit, "Cooling_Compact": compact_unit,
          "Cooling_ControlPanel": control_panel, "Cooling_Ceiling": ceiling_unit}


def write_glb(path, name, mesh, nodes, extras, atlas_png):
    bin_ = bytearray(); views = []; accs = []

    def view(data, target=None):
        while len(bin_) % 4: bin_.append(0)
        v = dict(buffer=0, byteOffset=len(bin_), byteLength=len(data))
        if target: v["target"] = target
        views.append(v); bin_.extend(data); return len(views) - 1
    prims = []
    for key, mat in (("main", 0), ("led", 1)):
        d = mesh.prims[key]
        mn = [min(p[k] for p in d["p"]) for k in range(3)]; mx = [max(p[k] for p in d["p"]) for k in range(3)]
        pv = view(b"".join(struct.pack("<3f", *p) for p in d["p"]), 34962); nv = view(b"".join(struct.pack("<3f", *p) for p in d["n"]), 34962)
        uv = view(b"".join(struct.pack("<2f", *p) for p in d["uv"]), 34962); iv = view(b"".join(struct.pack("<H", i) for i in d["i"]), 34963)
        b0 = len(accs)
        accs += [dict(bufferView=pv, componentType=5126, count=len(d["p"]), type="VEC3", min=mn, max=mx),
                 dict(bufferView=nv, componentType=5126, count=len(d["p"]), type="VEC3"),
                 dict(bufferView=uv, componentType=5126, count=len(d["p"]), type="VEC2"),
                 dict(bufferView=iv, componentType=5123, count=len(d["i"]), type="SCALAR")]
        prims.append(dict(attributes=dict(POSITION=b0, NORMAL=b0 + 1, TEXCOORD_0=b0 + 2), indices=b0 + 3, material=mat, mode=4))
    img = view(atlas_png)
    gn = [dict(name=name, mesh=0, extras=dict(extras, leds=sorted(mesh.leds), led_texture_width=N_LED, front="+Z"), children=list(range(1, 1 + len(nodes))))]
    for n in nodes: gn.append(dict(name=n["name"], translation=list(n["t"]), rotation=list(n["q"]), extras=n["extras"]))
    j = dict(asset=dict(version="2.0", generator="CoolingFamily procedural v1"), scene=0, scenes=[dict(nodes=[0])], nodes=gn,
             meshes=[dict(name=name + "_mesh", primitives=prims)],
             materials=[dict(name="M_Cooling", pbrMetallicRoughness=dict(baseColorTexture=dict(index=0), baseColorFactor=[1, 1, 1, 1], metallicFactor=0.15, roughnessFactor=0.65)),
                        dict(name="M_Status", pbrMetallicRoughness=dict(baseColorFactor=[0.05, 0.05, 0.05, 1], metallicFactor=0, roughnessFactor=0.5), emissiveFactor=[0.1, 0.9, 0.2])],
             textures=[dict(sampler=0, source=0)], images=[dict(bufferView=img, mimeType="image/png", name="cooling_atlas")],
             samplers=[dict(magFilter=9729, minFilter=9987, wrapS=33071, wrapT=33071)], accessors=accs, bufferViews=views, buffers=[dict(byteLength=len(bin_))])
    js = json.dumps(j, separators=(",", ":")).encode(); js += b" " * ((4 - len(js) % 4) % 4)
    while len(bin_) % 4: bin_.append(0)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js); f.write(struct.pack("<I4s", len(bin_), b"BIN\0")); f.write(bin_)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "out"; os.makedirs(out, exist_ok=True)
    atlas = png_bytes(AW, AH, make_atlas()); open(os.path.join(out, "cooling_atlas.png"), "wb").write(atlas)
    for name, fn in ASSETS.items():
        mesh, nodes, ex = fn()
        write_glb(os.path.join(out, name + ".glb"), name, mesh, nodes, ex, atlas)
        print(name, sum(len(d["i"]) // 3 for d in mesh.prims.values()), "tris", len(nodes), "anchors")
