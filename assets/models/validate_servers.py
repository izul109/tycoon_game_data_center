#!/usr/bin/env python3
"""Validate Server_*.glb (dimensions, pivot, naming, anchors, budgets) and render preview sheets."""
import json
import os
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
U = 0.04445
EXPECT = {"1U": (1, 0.700), "2U": (2, 0.740), "4U": (4, 0.780)}
TOL = 2e-4


def read_glb(path):
    b = open(path, "rb").read()
    magic, ver, total = struct.unpack_from("<III", b, 0)
    assert magic == 0x46546C67 and ver == 2 and total == len(b), "bad GLB header"
    jl, jt = struct.unpack_from("<II", b, 12)
    js = json.loads(b[20:20 + jl])
    bl, bt = struct.unpack_from("<II", b, 20 + jl)
    return js, b[28 + jl:28 + jl + bl]


def mesh_tris(js, binb, mesh):
    out = []
    for pr in mesh["primitives"]:
        def acc(i, dt, comps):
            a = js["accessors"][i]
            v = js["bufferViews"][a["bufferView"]]
            return np.frombuffer(binb, dtype=dt, count=a["count"] * comps, offset=v["byteOffset"]).reshape(-1, comps) if comps > 1 else \
                np.frombuffer(binb, dtype=dt, count=a["count"], offset=v["byteOffset"])
        P = acc(pr["attributes"]["POSITION"], "<f4", 3)
        N = acc(pr["attributes"]["NORMAL"], "<f4", 3)
        I = acc(pr["indices"], "<u2", 1)
        out.append((js["materials"][pr["material"]], P, N, I))
    return out


def validate(key):
    path = os.path.join(HERE, f"Server_{key}.glb")
    js, binb = read_glb(path)
    n, depth = EXPECT[key]
    errs, info = [], {}
    nodes = js["nodes"]
    root = nodes[js["scenes"][0]["nodes"][0]]
    if root["name"] != f"Server_{key}":
        errs.append("root name")
    names = [x["name"] for x in nodes]
    if len(set(names)) != len(names):
        errs.append("duplicate node names")
    for suf in ("Body", "Front", "Rear"):
        if f"Server_{key}_{suf}" not in names:
            errs.append(f"missing node Server_{key}_{suf}")
    allp, tris = [], 0
    for nd in nodes:
        if "mesh" in nd:
            for mat, P, N, I in mesh_tris(js, binb, js["meshes"][nd["mesh"]]):
                if not np.isfinite(P).all():
                    errs.append("NaN verts")
                if (I >= len(P)).any():
                    errs.append("bad index")
                tris += len(I) // 3
                allp.append(P)
    P = np.concatenate(allp)
    mn, mx = P.min(0), P.max(0)
    w, h, d = mx - mn
    info.update(width=w, height=h, depth=d, min=mn, max=mx, tris=tris, mats=len(js["materials"]),
                prims=sum(len(m["primitives"]) for m in js["meshes"]))
    if abs(w - 0.4826) > TOL:
        errs.append(f"width {w:.4f} != 0.4826")
    if abs(h - n * U) > TOL:
        errs.append(f"height {h:.5f} != {n * U:.5f}")
    if abs(d - depth) > 1e-3:
        errs.append(f"depth {d:.4f} != {depth}")
    if abs(mn[1]) > 1e-6:
        errs.append("pivot: bottom not at y=0")
    if abs(mn[0] + mx[0]) > 1e-5:
        errs.append("pivot: not centered in X")
    if abs(mn[2] + mx[2]) > 1e-4:
        errs.append("pivot: not centered in Z")
    anchors = [x for x in nodes if x["name"].startswith("Anchor_")]
    for a in anchors:
        if "mesh" in a:
            errs.append("anchor has mesh")
    info["anchors"] = len(anchors)
    # all anchors within bounds (+1 mm tolerance)
    for a in anchors:
        t = np.array(a["translation"])
        if (t < mn - 1e-3).any() or (t > mx + 1e-3).any():
            errs.append(f"anchor outside bounds: {a['name']}")
    return errs, info, js, binb


# ----------------------------------------------------------------------------
# software z-buffer renderer (orthographic)
# ----------------------------------------------------------------------------

def collect(js, binb):
    out = []
    for nd in js["nodes"]:
        if "mesh" in nd:
            for mat, P, N, I in mesh_tris(js, binb, js["meshes"][nd["mesh"]]):
                out.append((mat, P.astype(np.float64), N.astype(np.float64), I.reshape(-1, 3)))
    return out


def rot(yaw, pitch):
    cy, sy, cp, sp = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return Rx @ Ry


def render(geom, yaw_deg, pitch_deg, scale, size, center, ss=2):
    W, Hh = size[0] * ss, size[1] * ss
    R = rot(np.radians(yaw_deg), np.radians(pitch_deg))
    img = np.zeros((Hh, W, 3), np.float32)
    bgt, bgb = np.array([0.90, 0.92, 0.95]), np.array([0.72, 0.75, 0.80])
    for y in range(Hh):
        img[y] = bgt + (bgb - bgt) * (y / Hh)
    zb = np.full((Hh, W), -1e9, np.float32)
    L = np.array([-0.35, 0.65, 0.70])
    L /= np.linalg.norm(L)
    c = np.array(center)
    for mat, P, N, I in geom:
        base = np.array(mat["pbrMetallicRoughness"]["baseColorFactor"][:3]) ** (1 / 2.2)
        emis = np.array(mat.get("emissiveFactor", [0, 0, 0]))
        metal = mat["pbrMetallicRoughness"]["metallicFactor"]
        V = (P - c) @ R.T
        Nv = N @ R.T
        sx = W / 2 + V[:, 0] * scale * ss
        sy = Hh / 2 - V[:, 1] * scale * ss
        dz = V[:, 2]
        for tri in I:
            if Nv[tri[0], 2] <= 0:
                continue
            x = sx[tri]; y = sy[tri]; z = dz[tri]
            x0, x1 = int(max(0, np.floor(x.min()))), int(min(W - 1, np.ceil(x.max())))
            y0, y1 = int(max(0, np.floor(y.min()))), int(min(Hh - 1, np.ceil(y.max())))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            den = (y[1] - y[2]) * (x[0] - x[2]) + (x[2] - x[1]) * (y[0] - y[2])
            if abs(den) < 1e-12:
                continue
            l0 = ((y[1] - y[2]) * (gx - x[2]) + (x[2] - x[1]) * (gy - y[2])) / den
            l1 = ((y[2] - y[0]) * (gx - x[2]) + (x[0] - x[2]) * (gy - y[2])) / den
            l2 = 1 - l0 - l1
            m = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            if not m.any():
                continue
            zz = l0 * z[0] + l1 * z[1] + l2 * z[2]
            sub = zb[y0:y1 + 1, x0:x1 + 1]
            upd = m & (zz > sub + 1e-7)
            if not upd.any():
                continue
            nrm = Nv[tri[0]]
            diff = max(0.0, float(nrm @ L))
            shade = 0.38 + 0.62 * diff
            col = base * shade * (1.0 + 0.25 * metal) + emis
            col = np.clip(col, 0, 1)
            sub[upd] = zz[upd]
            img[y0:y1 + 1, x0:x1 + 1][upd] = col
    im = Image.fromarray((img * 255).astype(np.uint8))
    return im.resize(size, Image.LANCZOS)


def sheet(models, views, scale, cell, out, title_h=0):
    cols, rows = len(views), len(models)
    sheet_im = Image.new("RGB", (cols * cell[0], rows * cell[1]), (230, 232, 236))
    for r, (key, geom, bbox) in enumerate(models):
        c3 = [(bbox[0][i] + bbox[1][i]) / 2 for i in range(3)]
        for c, (yaw, pitch) in enumerate(views):
            im = render(geom, yaw, pitch, scale, cell, c3)
            sheet_im.paste(im, (c * cell[0], r * cell[1]))
    sheet_im.save(out)


def main():
    ok = True
    models = []
    print(f"{'Server':8}{'W(mm)':>9}{'H(mm)':>9}{'D(mm)':>9}{'tris':>7}{'mats':>6}{'prims':>7}{'anchors':>9}")
    for key in ("1U", "2U", "4U"):
        errs, info, js, binb = validate(key)
        print(f"{key:8}{info['width'] * 1000:9.1f}{info['height'] * 1000:9.2f}{info['depth'] * 1000:9.1f}"
              f"{info['tris']:7}{info['mats']:6}{info['prims']:7}{info['anchors']:9}")
        for e in errs:
            ok = False
            print("   FAIL:", e)
        models.append((key, collect(js, binb), (info["min"], info["max"])))
    print("ALL CHECKS PASSED" if ok else "CHECKS FAILED")
    if "--no-render" in sys.argv:
        return 0 if ok else 1
    # orthographic front/rear (same px/m on every row)
    sheet(models, [(0, 0), (180, 0)], 1500, (760, 340), os.path.join(HERE, "preview_front_rear.png"))
    sheet(models, [(-32, 22), (148, 22)], 820, (900, 520), os.path.join(HERE, "preview_angles.png"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
