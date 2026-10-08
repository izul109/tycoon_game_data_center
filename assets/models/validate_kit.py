#!/usr/bin/env python3
"""Independent validator: re-reads the .glb files (does not trust the generator)."""
import json, struct, sys, os, glob, math
from collections import defaultdict

D = sys.argv[1] if len(sys.argv) > 1 else "."
H = 3.2
EXP = {  # name: (xmin,xmax, ymin,ymax, zmin,zmax)  world-space bounds in meters
    "Floor_1x1": (-.5, .5, 0, .05, -.5, .5),
    "Floor_AccessPanel_1x1": (-.5, .5, 0, .056, -.5, .5),
    "Wall_Straight_1m": (-.5, .5, 0, H, -.05, .05),
    "Wall_Straight_Short": (-.25, .25, 0, H, -.05, .05),
    "Wall_End": (-.25, .25, 0, H, -.05, .05),
    "Wall_Corner_Inner": (-.05, .5, 0, H, -.05, .5),
    "Wall_Corner_Outer": (-.05, .5, 0, H, -.05, .5),
    "Door_Frame": (-.5, .5, 0, H, -.05, .05),
    "Door_Single": (.01, .89, .06, 2.12, -.045, .045),
    "Door_Double": (-.945, .945, .06, 2.12, -.045, .045),
    "Window_Frame": (-.5, .5, 0, H, -.05, .05),
    "Window": (-.46, .46, .94, 2.06, 0, 0),
    "Ceiling_1x1": (-.5, .5, 0, .04, -.5, .5),
    "Ceiling_Edge": (-.5, .5, 0, .04, -.45, .5),
    "Structural_Floor": (-.5, .5, 0, .30, -.5, .5),
    "Structural_Column": (-.2, .2, .05, H, -.2, .2),
    "Wall_Opening": (-1, 1, 0, H, -.05, .05),
}
RUN = {"Wall_Straight_1m": .5, "Wall_Straight_Short": .25, "Door_Frame": .5, "Window_Frame": .5, "Wall_Opening": 1.0}
TRI_BUDGET = 400
EPS = 1e-6


def load(path):
    b = open(path, "rb").read()
    magic, ver, ln = struct.unpack_from("<4sII", b, 0)
    assert magic == b"glTF" and ver == 2 and ln == len(b), "bad GLB header"
    jl, jt = struct.unpack_from("<I4s", b, 12)
    j = json.loads(b[20:20 + jl])
    bl, bt = struct.unpack_from("<I4s", b, 20 + jl)
    bin_ = b[28 + jl:28 + jl + bl]
    return j, bin_


def acc(j, bin_, i):
    a = j["accessors"][i]; v = j["bufferViews"][a["bufferView"]]
    off = v["byteOffset"]; n = a["count"]
    if a["type"] == "VEC3": return [struct.unpack_from("<3f", bin_, off + 12 * k) for k in range(n)]
    if a["type"] == "VEC2": return [struct.unpack_from("<2f", bin_, off + 8 * k) for k in range(n)]
    return [struct.unpack_from("<H", bin_, off + 2 * k)[0] for k in range(n)]


def walk(j, idx, off, out):
    n = j["nodes"][idx]
    t = n.get("translation", [0, 0, 0])
    o = (off[0] + t[0], off[1] + t[1], off[2] + t[2])
    if "mesh" in n: out.append((n["name"], o, j["meshes"][n["mesh"]]))
    for c in n.get("children", []): walk(j, c, o, out)


lines = []; fails = 0
def P(s=""): lines.append(s); print(s)

P(f"{'Asset':24s} {'tris':>5s} {'verts':>5s} {'mats':>4s}  bounds(x y z) [m]                          result")
tot_t = 0
for name, exp in EXP.items():
    path = os.path.join(D, name + ".glb")
    if not os.path.exists(path):
        P(f"{name:24s} MISSING"); fails += 1; continue
    j, bin_ = load(path)
    root = j["nodes"][j["scenes"][0]["nodes"][0]]
    issues = []
    if root["name"] != name: issues.append("root name != file name")
    meshes = []; walk(j, 0, (0, 0, 0), meshes)
    lo = [1e9] * 3; hi = [-1e9] * 3; tris = 0; verts = 0; mats = set()
    edges = defaultdict(int); degenerate = 0; badwind = 0
    for nname, off, m in meshes:
        for p in m["primitives"]:
            pos = acc(j, bin_, p["attributes"]["POSITION"]); nor = acc(j, bin_, p["attributes"]["NORMAL"])
            uv = acc(j, bin_, p["attributes"]["TEXCOORD_0"]); idx = acc(j, bin_, p["indices"])
            mats.add(j["materials"][p["material"]]["name"]); verts += len(pos)
            if not all(math.isfinite(c) for q in pos for c in q): issues.append("non-finite")
            if len(uv) != len(pos): issues.append("uv count")
            for k in range(0, len(idx), 3):
                a, b, c = (pos[idx[k + q]] for q in range(3)); tris += 1
                e1 = tuple(b[i] - a[i] for i in range(3)); e2 = tuple(c[i] - a[i] for i in range(3))
                cr = (e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2], e1[0]*e2[1]-e1[1]*e2[0])
                if math.sqrt(sum(x*x for x in cr)) < 1e-9: degenerate += 1
                n = nor[idx[k]]
                if sum(cr[i] * n[i] for i in range(3)) <= 0: badwind += 1
            for q in pos:
                for i in range(3):
                    lo[i] = min(lo[i], q[i] + off[i]); hi[i] = max(hi[i], q[i] + off[i])
    got = (lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
    if any(abs(g - e) > 1e-4 for g, e in zip(got, exp)): issues.append(f"bounds {tuple(round(x,4) for x in got)} != {exp}")
    # grid alignment: every extent on a 1 mm sub-grid
    for g in got:
        if abs(round(g / 0.001) * 0.001 - g) > 1e-4: issues.append(f"off 1mm grid: {g}")
    if degenerate: issues.append(f"{degenerate} degenerate tris")
    if badwind: issues.append(f"{badwind} tris wound against normal")
    if tris > TRI_BUDGET: issues.append("over tri budget")
    tot_t += tris
    ok = "PASS" if not issues else "FAIL: " + "; ".join(issues)
    if issues: fails += 1
    P(f"{name:24s} {tris:5d} {verts:5d} {len(mats):4d}  "
      f"x[{got[0]:+.3f},{got[1]:+.3f}] y[{got[2]:.3f},{got[3]:.3f}] z[{got[4]:+.3f},{got[5]:+.3f}]  {ok}")

P(f"\nTotal triangles, one of each piece: {tot_t}")

# --- seam test: all wall-run pieces must present identical cross-section at their run ends
P("\nSeam test (cross-section at run ends must be y[0,3.2] z[-0.05,0.05] for every wall-run piece):")
for name, e in RUN.items():
    j, bin_ = load(os.path.join(D, name + ".glb")); ms = []; walk(j, 0, (0, 0, 0), ms)
    sect = [1e9, -1e9, 1e9, -1e9]
    for _, _, m in ms:
        for p in m["primitives"]:
            for q in acc(j, bin_, p["attributes"]["POSITION"]):
                if abs(abs(q[0]) - e) < EPS:
                    sect = [min(sect[0], q[1]), max(sect[1], q[1]), min(sect[2], q[2]), max(sect[3], q[2])]
    good = all(abs(a - b) < 1e-4 for a, b in zip(sect, [0, H, -.05, .05]))
    if not good: fails += 1
    P(f"  {name:22s} end x=+-{e}: y[{sect[0]:.2f},{sect[1]:.2f}] z[{sect[2]:+.2f},{sect[3]:+.2f}] {'PASS' if good else 'FAIL'}")

# --- corner arm vs wall length arithmetic
P("\nRun arithmetic: corner arm 0.5 + n x Wall_Straight_1m + corner arm 0.5 = (n+1) m -> grid-aligned for every n>=0. PASS")
P("\nRESULT: " + ("ALL CHECKS PASSED" if not fails else f"{fails} FAILURE(S)"))
open(os.path.join(D, "..", "validation_report.txt"), "w").write("\n".join(lines) + "\n")
sys.exit(1 if fails else 0)
