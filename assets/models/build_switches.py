#!/usr/bin/env python3
"""
Fictional 1U managed Ethernet switch family -> GLB (glTF 2.0), Godot 4.x ready.
Pure Python, no dependencies.  All design coordinates are in MILLIMETERS, exported in METERS.

Axes: +X right, +Y up, +Z = FRONT of the device (ports face +Z), -Z = rear.
Pivot: bottom-center of the device (x=0, y=0, z=0 at mid-depth).

Draw-call budget: 2 surfaces per switch
  surface 0  M_Switch : chassis + faceplate + port interiors + labels + decals, ONE shared 256x256 atlas
  surface 1  M_LED    : all status LEDs; UV.x encodes LED index -> per-instance status via shader
"""
import json, struct, zlib, os, sys

S = 0.001                              # mm -> m
H = 43.6                               # 1U chassis height (44.45 pitch minus 0.85 clearance)
W_BODY = 440.0
W_RACK = 482.6                         # 19-inch panel width
EAR_X = W_RACK / 2                     # 241.3
BODY_X = W_BODY / 2                    # 220
ZF, ZB = 200.0, -200.0                 # front / rear plane  (depth 400 mm)
PLATE_T = 3.0                          # port recess depth
PITCH, HOLE_W, HOLE_H = 15.0, 13.0, 13.0
ROW_BOT = (2.5, 15.5)
ROW_TOP = (28.1, 41.1)
LBL_LOW, LBL_UP = 19.3, 24.3           # label/LED row centers in the middle band
DECAL = 0.5                            # decal offset above surface
N_LED_TEX = 64

# ------------------------------------------------------------------ atlas / palette
PAL = {
    "chassis": (150, 155, 162), "face": (36, 39, 45), "dark": (8, 8, 10),
    "teal": (0, 150, 160), "teal_dk": (0, 85, 92),
    "amber": (235, 150, 20), "amber_dk": (130, 80, 10),
    "rear": (80, 84, 90), "slat": (60, 64, 72),
}
PAL_ORDER = list(PAL)
TEXT_RGB = (205, 210, 215)
GLYPH = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "001", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
    "U": ["101", "101", "101", "101", "111"],
}
AW = AH = 256
CELL_W, CELL_H = 32, 16               # label cell (8 x 8 grid in the top half)
SW = 32                               # palette swatch (8 x 4 grid in the bottom half)


def label_text(cell):
    return f"U{cell - 47}" if cell >= 48 else str(cell + 1)


def make_atlas():
    px = bytearray(AW * AH * 3)

    def fill(x0, y0, w, h, c):
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                o = (y * AW + x) * 3
                px[o:o + 3] = bytes(c)
    fill(0, 0, AW, AH, PAL["face"])
    for k, name in enumerate(PAL_ORDER):
        fill((k % 8) * SW, 128 + (k // 8) * SW, SW, SW, PAL[name])
    for cell in range(52):
        t = label_text(cell); sc = 3
        wtxt = len(t) * 3 * sc + (len(t) - 1) * sc
        ox = (cell % 8) * CELL_W + (CELL_W - wtxt) // 2
        oy = (cell // 8) * CELL_H
        for gi, ch in enumerate(t):
            for gy, row in enumerate(GLYPH[ch]):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        fill(ox + gi * (3 * sc + sc) + gx * sc, oy + gy * sc, sc, sc, TEXT_RGB)
    return bytes(px)


def png_bytes(w, h, rgb):
    raw = b"".join(b"\x00" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def swatch_uv(name):
    k = PAL_ORDER.index(name)
    u = ((k % 8) * SW + SW / 2) / AW
    v = (128 + (k // 8) * SW + SW / 2) / AH
    return [(u, v)] * 4


def label_uv(cell):
    u0 = (cell % 8) * CELL_W / AW; u1 = u0 + CELL_W / AW
    v0 = (cell // 8) * CELL_H / AH; v1 = v0 + CELL_H / AH
    return [(u0, v1), (u1, v1), (u1, v0), (u0, v0)]       # (0,0),(1,0),(1,1),(0,1) = BL,BR,TR,TL


def led_uv(idx):
    return [(((idx + 0.5) / N_LED_TEX), 0.5)] * 4


# ------------------------------------------------------------------ mesh
def _sub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def _cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def _dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


class Mesh:
    def __init__(self):
        self.prims = {"main": dict(p=[], n=[], uv=[], i=[]), "led": dict(p=[], n=[], uv=[], i=[])}

    def face(self, prim, ax, c, ra, rb, sign, uv):
        a, b = {0: (2, 1), 1: (0, 2), 2: (0, 1)}[ax]
        pts = []
        for ia, ib in ((0, 0), (1, 0), (1, 1), (0, 1)):
            v = [0.0, 0.0, 0.0]; v[ax] = c; v[a] = ra[ia]; v[b] = rb[ib]; pts.append(tuple(v))
        n = [0, 0, 0]; n[ax] = sign
        order = [0, 1, 2, 3]
        if _dot(_cross(_sub(pts[1], pts[0]), _sub(pts[2], pts[0])), n) < 0:
            order = [0, 3, 2, 1]
        d = self.prims[prim]; base = len(d["p"])
        for k in order:
            d["p"].append(tuple(round(q * S, 7) for q in pts[k])); d["n"].append(tuple(n)); d["uv"].append(uv[k])
        d["i"] += [base, base + 1, base + 2, base, base + 2, base + 3]

    def box(self, col, lo, hi, skip=()):
        for ax in range(3):
            for sg in (-1, 1):
                if (("-" if sg < 0 else "+") + "xyz"[ax]) in skip:
                    continue
                a, b = {0: (2, 1), 1: (0, 2), 2: (0, 1)}[ax]
                self.face("main", ax, lo[ax] if sg < 0 else hi[ax], (lo[a], hi[a]), (lo[b], hi[b]), sg, swatch_uv(col))

    def rect_z(self, prim, x0, x1, y0, y1, z, sign, uv):
        self.face(prim, 2, z, (x0, x1), (y0, y1), sign, uv)


# ------------------------------------------------------------------ builder
def build(model):
    assert model in (24, 48)
    acc, acc_dk = ("teal", "teal_dk") if model == 24 else ("amber", "amber_dk")
    m = Mesh(); holes = []; nodes = []; leds = []; ports = {}

    # chassis (front face replaced by the faceplate quads below)
    m.box("chassis", (-BODY_X, 0, ZB), (BODY_X, H, ZF), skip=("+z",))
    m.box("chassis", (BODY_X, 0, ZF - PLATE_T), (EAR_X, H, ZF), skip=("-x",))
    m.box("chassis", (-EAR_X, 0, ZF - PLATE_T), (-BODY_X, H, ZF), skip=("+x",))

    def hole(cx, row, interior, w=HOLE_W):
        y0, y1 = row; x0, x1 = cx - w / 2, cx + w / 2
        holes.append((x0, x1, y0, y1))
        zb = ZF - PLATE_T; uv = swatch_uv(interior)
        m.face("main", 0, x0, (zb, ZF), (y0, y1), +1, uv)
        m.face("main", 0, x1, (zb, ZF), (y0, y1), -1, uv)
        m.face("main", 1, y0, (x0, x1), (zb, ZF), +1, uv)
        m.face("main", 1, y1, (x0, x1), (zb, ZF), -1, uv)
        m.face("main", 2, zb, (x0, x1), (y0, y1), +1, uv)

    def led(cx, cy, idx):
        m.rect_z("led", cx - 1.2, cx + 1.2, cy - 0.9, cy + 0.9, ZF + DECAL, +1, led_uv(idx))
        leds.append(idx)

    def label(cx, cy, cell):
        m.rect_z("main", cx - 3.5, cx + 3.5, cy - 1.75, cy + 1.75, ZF + DECAL, +1, label_uv(cell))

    def rj45_column(cx, top_n, bot_n):
        hole(cx, ROW_TOP, "dark"); hole(cx, ROW_BOT, "dark")
        for n, row, lbl in ((top_n, ROW_TOP, LBL_UP), (bot_n, ROW_BOT, LBL_LOW)):
            ports[f"Port_{n:02d}"] = dict(x=cx, y=(row[0] + row[1]) / 2, led=n - 1)
            led(cx - 3.4, lbl, n - 1); label(cx + 2.3, lbl, n - 1)

    # RJ45 columns: top = odd, bottom = even, groups of 6 columns separated by 3 mm
    xcur = -BODY_X + 8.0
    cols = model // 2
    for c in range(cols):
        rj45_column(xcur + PITCH / 2, 2 * c + 1, 2 * c + 2)
        xcur += PITCH
        if (c + 1) % 6 == 0 and c < cols - 1:
            xcur += 3.0
    rj45_end = xcur

    # right block: 2 uplink columns + console column (aligned to the right edge for both models)
    c_console = BODY_X - 8.0 - PITCH / 2            # 204.5
    c_up2 = c_console - PITCH - 4.0                 # 185.5
    c_up1 = c_up2 - PITCH                           # 170.5
    assert c_up1 - HOLE_W / 2 - rj45_end >= 4.0, "uplink block collides with RJ45 block"
    for k, (cx, tn, bn) in enumerate(((c_up1, 1, 2), (c_up2, 3, 4))):
        hole(cx, ROW_TOP, acc_dk); hole(cx, ROW_BOT, acc_dk)
        for n, row, lbl in ((tn, ROW_TOP, LBL_UP), (bn, ROW_BOT, LBL_LOW)):
            ports[f"Uplink_{n:02d}"] = dict(x=cx, y=(row[0] + row[1]) / 2, led=47 + n)
            led(cx - 3.4, lbl, 47 + n); label(cx + 2.3, lbl, 47 + n)
    hole(c_console, ROW_BOT, "dark")
    ports["Console"] = dict(x=c_console, y=(ROW_BOT[0] + ROW_BOT[1]) / 2, led=None)
    for k, dx in enumerate((-4.5, 0.0, 4.5)):        # PWR / SYS / FAN
        led(c_console + dx, 34.6, 52 + k)

    # faceplate: one quad per free interval of every horizontal band (holes excluded)
    ys = sorted({0.0, H} | {h[2] for h in holes} | {h[3] for h in holes})
    for ya, yb in zip(ys[:-1], ys[1:]):
        cover = sorted((h[0], h[1]) for h in holes if h[2] <= ya + 1e-9 and h[3] >= yb - 1e-9)
        x = -BODY_X
        for (a, b) in cover + [(BODY_X, BODY_X)]:
            if a - x > 1e-9:
                m.rect_z("main", x, a, ya, yb, ZF, +1, swatch_uv("face"))
            x = max(x, b)

    # decals: accent line, ear slots, faceplate vent grille (24-port only)
    m.rect_z("main", -BODY_X + 8, BODY_X - 8, 0.6, 1.6, ZF + DECAL, +1, swatch_uv(acc))
    for sx in (-1, 1):
        for cy in (5.95, 37.65):
            xc = sx * (BODY_X + EAR_X) / 2
            m.rect_z("main", xc - 5, xc + 5, cy - 2.9, cy + 2.9, ZF + DECAL, +1, swatch_uv("dark"))
    if model == 24:
        x = -17.0
        while x < 143.0:
            m.rect_z("main", x, x + 2.0, 8.0, 35.6, ZF + DECAL, +1, swatch_uv("dark"))
            x += 8.0

    # ventilation: side slots, top slots
    for sx in (-1, 1):
        z = -170.0
        while z < 20.0:
            m.face("main", 0, sx * (BODY_X + DECAL), (z, z + 2.0), (6.0, H - 6.0), sx, swatch_uv("dark"))
            z += 18.0
    x = -168.0
    while x <= 168.0:
        m.face("main", 1, H + DECAL, (x, x + 2.0), (-175.0, -125.0), +1, swatch_uv("dark"))
        x += 24.0

    # rear: 2 fan grilles, 2 PSU modules with inlets
    for fx in (-170.0, -110.0):
        m.face("main", 2, ZB - DECAL, (fx - 19, fx + 19), (2.8, 40.8), -1, swatch_uv("dark"))
        for sy in (12.0, 20.8, 29.6):
            m.face("main", 2, ZB - 2 * DECAL, (fx - 18, fx + 18), (sy, sy + 2.2), -1, swatch_uv("slat"))
    for px_ in (95.0, 175.0):
        m.face("main", 2, ZB - DECAL, (px_ - 35, px_ + 35), (3.0, 40.6), -1, swatch_uv("rear"))
        m.face("main", 2, ZB - 2 * DECAL, (px_ - 11, px_ + 11), (14.0, 27.0), -1, swatch_uv("dark"))

    # anchor nodes (meters)
    for name, p in sorted(ports.items()):
        nodes.append(dict(name=name, t=(round(p["x"] * S, 6), round(p["y"] * S, 6), ZF * S),
                          extras=dict(kind="console" if name == "Console" else ("uplink" if name.startswith("Uplink") else "rj45"),
                                      led_index=p["led"] if p["led"] is not None else -1)))
    for a in range(len(holes)):
        for b in range(a + 1, len(holes)):
            A, B = holes[a], holes[b]
            assert A[1] <= B[0] or B[1] <= A[0] or A[3] <= B[2] or B[3] <= A[2], f"hole overlap {A} {B}"
    assert all(-BODY_X < h[0] and h[1] < BODY_X for h in holes)
    return m, nodes, dict(ports=model, uplinks=4, rack_u=1, width_m=W_RACK * S, height_m=H * S, depth_m=(ZF - ZB) * S,
                          front="+Z", led_texture_width=N_LED_TEX, leds=sorted(leds))


# ------------------------------------------------------------------ GLB writer
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
        pv = view(b"".join(struct.pack("<3f", *p) for p in d["p"]), 34962)
        nv = view(b"".join(struct.pack("<3f", *p) for p in d["n"]), 34962)
        uv = view(b"".join(struct.pack("<2f", *p) for p in d["uv"]), 34962)
        iv = view(b"".join(struct.pack("<H", i) for i in d["i"]), 34963)
        base = len(accs)
        accs += [dict(bufferView=pv, componentType=5126, count=len(d["p"]), type="VEC3", min=mn, max=mx),
                 dict(bufferView=nv, componentType=5126, count=len(d["p"]), type="VEC3"),
                 dict(bufferView=uv, componentType=5126, count=len(d["p"]), type="VEC2"),
                 dict(bufferView=iv, componentType=5123, count=len(d["i"]), type="SCALAR")]
        prims.append(dict(attributes=dict(POSITION=base, NORMAL=base + 1, TEXCOORD_0=base + 2), indices=base + 3, material=mat, mode=4))
    img = view(atlas_png)
    gn = [dict(name=name, mesh=0, extras=extras, children=list(range(1, 1 + len(nodes))))]
    for n in nodes:
        gn.append(dict(name=n["name"], translation=list(n["t"]), extras=n["extras"]))
    j = dict(asset=dict(version="2.0", generator="SwitchFamily procedural v1"), scene=0, scenes=[dict(nodes=[0])], nodes=gn,
             meshes=[dict(name=name + "_mesh", primitives=prims)],
             materials=[dict(name="M_Switch", pbrMetallicRoughness=dict(baseColorTexture=dict(index=0), baseColorFactor=[1, 1, 1, 1],
                                                                       metallicFactor=0.1, roughnessFactor=0.7)),
                        dict(name="M_LED", pbrMetallicRoughness=dict(baseColorFactor=[0.05, 0.05, 0.05, 1], metallicFactor=0.0, roughnessFactor=0.5),
                             emissiveFactor=[0.1, 0.9, 0.2])],
             textures=[dict(sampler=0, source=0)], images=[dict(bufferView=img, mimeType="image/png", name="switch_atlas")],
             samplers=[dict(magFilter=9729, minFilter=9987, wrapS=33071, wrapT=33071)],
             accessors=accs, bufferViews=views, buffers=[dict(byteLength=len(bin_))])
    js = json.dumps(j, separators=(",", ":")).encode(); js += b" " * ((4 - len(js) % 4) % 4)
    while len(bin_) % 4: bin_.append(0)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(js) + 8 + len(bin_)))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(bin_), b"BIN\0")); f.write(bin_)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "out"
    os.makedirs(out, exist_ok=True)
    atlas = png_bytes(AW, AH, make_atlas())
    open(os.path.join(out, "switch_atlas.png"), "wb").write(atlas)
    for model in (24, 48):
        mesh, nodes, extras = build(model)
        write_glb(os.path.join(out, f"Switch_{model}P_1U.glb"), f"Switch_{model}P_1U", mesh, nodes, extras, atlas)
        tris = sum(len(d["i"]) // 3 for d in mesh.prims.values())
        print(f"Switch_{model}P_1U: {tris} tris, {len(nodes)} anchor nodes")
