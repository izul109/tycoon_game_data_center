#!/usr/bin/env python3
"""
Procedural generator: facility-support asset set (SysEng Sim - Data Center).
12 x .glb (glTF 2.0) + manifest.json, for Godot 4.x.

Conventions (same as the firewall set)
  - Units: meters. Y up. Front / outward face = +Z.
  - Wall assets : origin = mounting point (center of the back plate, on the wall plane z=0),
                  object protrudes toward +Z. Place so that +Z points out of the wall.
  - Ceiling     : origin = mounting center on the ceiling plane (y=0), object hangs toward -Y.
  - Floor       : origin = bottom-center.
  - One MeshInstance3D ("Body") per asset, <= 4 surfaces, shared material names across all files.
  - Optional empty nodes: Anchors/<NAME> (light sources, text, seat, press points),
    LEDs/<NAME> (tiny separate meshes you can recolor per instance).
"""
import json, struct, sys, os
import numpy as np
from math import cos, sin, pi

# name: (rgba, metallic, roughness, emissive_rgb)
MATS = {
    "MAT_Facility_White": ((0.82, 0.84, 0.86, 1), 0.1, 0.5, None),
    "MAT_Facility_Grey":  ((0.45, 0.48, 0.52, 1), 0.4, 0.5, None),
    "MAT_Facility_Dark":  ((0.10, 0.11, 0.13, 1), 0.3, 0.6, None),
    "MAT_Metal":          ((0.60, 0.62, 0.65, 1), 0.8, 0.4, None),
    "MAT_Lens":           ((0.02, 0.03, 0.05, 1), 0.6, 0.15, None),
    "MAT_Emissive_White": ((0.95, 0.97, 1.00, 1), 0.0, 0.5, (1.0, 0.98, 0.92)),
    "MAT_Emissive_Screen":((0.05, 0.20, 0.22, 1), 0.0, 0.4, (0.10, 0.70, 0.80)),
    "MAT_Safety_Red":     ((0.80, 0.08, 0.06, 1), 0.0, 0.45, None),
    "MAT_Warning_Yellow": ((0.98, 0.80, 0.05, 1), 0.0, 0.5, None),
    "MAT_Safety_Green":   ((0.00, 0.50, 0.25, 1), 0.0, 0.5, None),
    "MAT_Info_Blue":      ((0.05, 0.30, 0.70, 1), 0.0, 0.5, None),
    "MAT_Sign_White":     ((0.92, 0.93, 0.92, 1), 0.0, 0.5, None),
    "MAT_Sign_Black":     ((0.03, 0.03, 0.03, 1), 0.0, 0.6, None),
    "MAT_LED_Green":      ((0.10, 0.90, 0.30, 1), 0.0, 0.4, (0.10, 1.00, 0.30)),
    "MAT_LED_Red":        ((0.90, 0.10, 0.08, 1), 0.0, 0.4, (1.00, 0.10, 0.08)),
}

FACES = {
    "+Z": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    "-Z": ((0, 0, -1), (-1, 0, 0), (0, 1, 0)),
    "+X": ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    "-X": ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    "+Y": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    "-Y": ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
}
ALL = tuple(FACES)


class MB:
    def __init__(self):
        self.prims = {}

    def _p(self, mat):
        return self.prims.setdefault(mat, ([], [], []))

    def box(self, mat, c, s, faces=ALL):
        P, N, I = self._p(mat)
        c = np.array(c, float); h = np.array(s, float) / 2
        for f in faces:
            n, u, v = (np.array(a, float) for a in FACES[f])
            hu, hv, hn = abs(u) @ h, abs(v) @ h, abs(n) @ h
            ctr = c + n * hn; b = len(P)
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                P.append((ctr + u * hu * su + v * hv * sv).tolist()); N.append(n.tolist())
            I += [b, b + 1, b + 2, b, b + 2, b + 3]

    def frustum(self, mat, c, r0, r1, h, n=8, axis="y", caps=(False, True), phase=0.0):
        """Cone frustum, base center c, extends along +axis ('y' or 'z'). Smooth side normals."""
        P, N, I = self._p(mat)
        c = np.array(c, float)

        def tf(v):
            v = np.array(v, float)
            return np.array([v[0], -v[2], v[1]]) if axis == "z" else v
        ang = [phase + 2 * pi * i / n for i in range(n)]
        slope = (r0 - r1) / h
        base = len(P)
        for a in ang:
            nr = np.array([cos(a), slope, sin(a)]); nr /= np.linalg.norm(nr)
            P.append((tf([r0 * cos(a), 0, r0 * sin(a)]) + c).tolist()); N.append(tf(nr).tolist())
            P.append((tf([r1 * cos(a), h, r1 * sin(a)]) + c).tolist()); N.append(tf(nr).tolist())
        for i in range(n):
            j = (i + 1) % n
            bi, ti, bj, tj = base + 2 * i, base + 2 * i + 1, base + 2 * j, base + 2 * j + 1
            I += [bi, tj, bj, bi, ti, tj]
        for top, r, y in ((True, r1, h), (False, r0, 0)):
            if not caps[1 if top else 0]:
                continue
            cb = len(P); nrm = tf([0, 1 if top else -1, 0]).tolist()
            P.append((tf([0, y, 0]) + c).tolist()); N.append(nrm)
            for a in ang:
                P.append((tf([r * cos(a), y, r * sin(a)]) + c).tolist()); N.append(nrm)
            for i in range(n):
                a_, b_ = cb + 1 + i, cb + 1 + (i + 1) % n
                I += [cb, b_, a_] if top else [cb, a_, b_]

    def prism(self, mat, poly, z0, z1, faces=("front", "back", "side")):
        """Convex CCW polygon (x,y) extruded along Z."""
        P, N, I = self._p(mat)
        n = len(poly)
        if "front" in faces:
            b = len(P)
            for x, y in poly: P.append([x, y, z1]); N.append([0, 0, 1])
            for i in range(1, n - 1): I += [b, b + i, b + i + 1]
        if "back" in faces:
            b = len(P)
            for x, y in poly: P.append([x, y, z0]); N.append([0, 0, -1])
            for i in range(1, n - 1): I += [b, b + i + 1, b + i]
        if "side" in faces:
            for i in range(n):
                (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
                dx, dy = x1 - x0, y1 - y0; L = (dx * dx + dy * dy) ** .5; nn = [dy / L, -dx / L, 0]
                b = len(P)
                for x, y, z in ((x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1)):
                    P.append([x, y, z]); N.append(nn)
                I += [b, b + 1, b + 2, b, b + 2, b + 3]

    def tris(self): return sum(len(i) // 3 for _, _, i in self.prims.values())

    def check(self, name):
        for mat, (P, N, I) in self.prims.items():
            p = np.array(P); n = np.array(N); t = np.array(I).reshape(-1, 3)
            g = np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]])
            bad = (np.einsum("ij,ij->i", g, n[t[:, 0]]) <= 0)
            assert not bad.any(), f"{name}/{mat}: {bad.sum()} triangles wound against their normals"
            assert len(P) < 65535

    def bounds(self):
        a = np.vstack([np.array(P) for P, _, _ in self.prims.values()])
        return a.min(0), a.max(0)


class GLTF:
    def __init__(self):
        self.bin = bytearray(); self.views, self.accs, self.meshes, self.nodes, self.mats = [], [], [], [], []
        self.midx = {}

    def mat(self, name):
        if name not in self.midx:
            rgba, met, rough, emis = MATS[name]
            m = {"name": name, "pbrMetallicRoughness": {"baseColorFactor": list(rgba), "metallicFactor": met, "roughnessFactor": rough}}
            if emis: m["emissiveFactor"] = list(emis)
            self.mats.append(m); self.midx[name] = len(self.mats) - 1
        return self.midx[name]

    def _view(self, data, target):
        while len(self.bin) % 4: self.bin.append(0)
        self.views.append({"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data), "target": target})
        self.bin += data; return len(self.views) - 1

    def _acc(self, view, ct, count, at, mn=None, mx=None):
        a = {"bufferView": view, "componentType": ct, "count": count, "type": at}
        if mn is not None: a["min"], a["max"] = mn, mx
        self.accs.append(a); return len(self.accs) - 1

    def add_mesh(self, name, mb):
        prims = []
        for mat, (P, N, I) in mb.prims.items():
            p, n, i = np.array(P, np.float32), np.array(N, np.float32), np.array(I, np.uint16)
            ap = self._acc(self._view(p.tobytes(), 34962), 5126, len(p), "VEC3", p.min(0).tolist(), p.max(0).tolist())
            an = self._acc(self._view(n.tobytes(), 34962), 5126, len(n), "VEC3")
            ai = self._acc(self._view(i.tobytes(), 34963), 5123, len(i), "SCALAR")
            prims.append({"attributes": {"POSITION": ap, "NORMAL": an}, "indices": ai, "material": self.mat(mat), "mode": 4})
        self.meshes.append({"name": name, "primitives": prims}); return len(self.meshes) - 1

    def node(self, name, mesh=None, t=None, extras=None, children=None):
        d = {"name": name}
        if mesh is not None: d["mesh"] = mesh
        if t is not None: d["translation"] = [float(x) for x in t]
        if extras: d["extras"] = extras
        if children: d["children"] = children
        self.nodes.append(d); return len(self.nodes) - 1

    def save(self, path, root):
        while len(self.bin) % 4: self.bin.append(0)
        doc = {"asset": {"version": "2.0", "generator": "gen_facility_support.py"}, "scene": 0, "scenes": [{"nodes": [root]}],
               "nodes": self.nodes, "meshes": self.meshes, "materials": self.mats, "accessors": self.accs,
               "bufferViews": self.views, "buffers": [{"byteLength": len(self.bin)}]}
        j = json.dumps(doc, separators=(",", ":")).encode(); j += b" " * ((4 - len(j) % 4) % 4)
        out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(j) + 8 + len(self.bin))
        out += struct.pack("<II", len(j), 0x4E4F534A) + j + struct.pack("<II", len(self.bin), 0x004E4942) + bytes(self.bin)
        open(path, "wb").write(out)


class Asset:
    def __init__(self, name, mesh_name, mount):
        self.name, self.mesh_name, self.mount = name, mesh_name, mount
        self.gl, self.mb = GLTF(), MB()
        self.anchors, self.leds, self._ledcache = [], [], {}

    def anchor(self, name, pos, kind):
        self.anchors.append((name, pos, kind))

    def led(self, name, mat, size, pos):
        key = (size, mat)
        if key not in self._ledcache:
            m = MB(); m.box(mat, (0, 0, 0), size, ("+Z", "+X", "-X", "+Y", "-Y"))
            self._ledcache[key] = self.gl.add_mesh(f"LED_{mat[8:]}", m)
        self.leds.append((name, self._ledcache[key], pos))

    def save(self, outdir):
        self.mb.check(self.name)
        gl = self.gl
        kids = [gl.node("Body", mesh=gl.add_mesh(self.mesh_name, self.mb))]
        if self.anchors:
            kids.append(gl.node("Anchors", children=[gl.node(n, t=p, extras={"anchor": n, "kind": k, "dir": "+Z"}) for n, p, k in self.anchors]))
        if self.leds:
            kids.append(gl.node("LEDs", children=[gl.node(n, mesh=m, t=p, extras={"led_id": n}) for n, m, p in self.leds]))
        gl.save(f"{outdir}/{self.name}.glb", gl.node(self.name, children=kids))
        lo, hi = self.mb.bounds()
        return {"file": f"{self.name}.glb", "mount": self.mount, "tris": self.mb.tris(),
                "surfaces": [m for m in self.mb.prims], "size_m": [round(float(x), 4) for x in (hi - lo)],
                "bounds_min": [round(float(x), 4) for x in lo], "anchors": [a[0] for a in self.anchors],
                "leds": [l[0] for l in self.leds]}


# ===================================================================== assets
def ceiling_light():
    a = Asset("fac_light_ceiling", "FacLightCeiling", "ceiling: origin on ceiling plane, hangs toward -Y")
    m = a.mb; H = 0.035
    for z in (-0.295, 0.295):
        m.box("MAT_Facility_White", (0, -H / 2, z), (0.62, H, 0.03), ("-Y", "+X", "-X", "+Z", "-Z"))
    for x in (-0.295, 0.295):
        m.box("MAT_Facility_White", (x, -H / 2, 0), (0.03, H, 0.56), ("-Y", "+X", "-X", "+Z", "-Z"))
    m.box("MAT_Emissive_White", (0, -0.030, 0), (0.56, 0.002, 0.56), ("-Y",))
    a.anchor("LIGHT", (0, -0.04, 0), "light_source")
    return a


def emergency_light():
    a = Asset("fac_light_emergency", "FacLightEmergency", "wall: origin = back-plate center on wall, protrudes +Z")
    m = a.mb
    m.box("MAT_Facility_White", (0, 0, 0.035), (0.30, 0.11, 0.07), ("+Z", "+X", "-X", "+Y", "-Y"))
    for x in (-0.075, 0.075):
        m.frustum("MAT_Facility_Grey", (x, 0, 0.07), 0.040, 0.034, 0.028, 8, "z", (False, False))
        m.frustum("MAT_Emissive_White", (x, 0, 0.098), 0.030, 0.030, 0.002, 8, "z", (False, True))
    a.led("LED_STATUS", "MAT_LED_Green", (0.008, 0.008, 0.001), (0, 0.032, 0.0705))
    a.anchor("LIGHT_L", (-0.075, 0, 0.100), "light_source")
    a.anchor("LIGHT_R", (0.075, 0, 0.100), "light_source")
    return a


def wall_light():
    a = Asset("fac_light_wall", "FacLightWall", "wall: origin = back-plate center on wall, protrudes +Z")
    m = a.mb
    m.box("MAT_Facility_Grey", (0, 0, 0.035), (0.36, 0.10, 0.07), ("+Z", "+X", "-X", "+Y", "-Y"))
    m.box("MAT_Facility_Dark", (0, 0.052, 0.0425), (0.38, 0.004, 0.085), ("+Y", "-Y", "+X", "-X", "+Z"))
    m.box("MAT_Emissive_White", (0, 0, 0.0705), (0.30, 0.06, 0.001), ("+Z", "+X", "-X", "+Y", "-Y"))
    a.anchor("LIGHT", (0, 0, 0.075), "light_source")
    return a


def camera():
    a = Asset("fac_camera", "FacCamera", "wall: origin = back-plate center on wall, protrudes +Z; camera looks along +Z")
    m = a.mb
    m.box("MAT_Facility_Grey", (0, 0, 0.004), (0.06, 0.09, 0.008), ("+Z", "+X", "-X", "+Y", "-Y"))
    m.box("MAT_Facility_Grey", (0, 0, 0.045), (0.026, 0.026, 0.074), ("+Z", "+X", "-X", "+Y", "-Y"))
    m.box("MAT_Facility_Grey", (0, -0.0155, 0.062), (0.022, 0.019, 0.026), ("+Z", "-Z", "+X", "-X", "-Y"))
    m.frustum("MAT_Facility_White", (0, -0.05, 0.035), 0.034, 0.034, 0.18, 8, "z", (True, True))
    m.box("MAT_Facility_White", (0, -0.0145, 0.13), (0.075, 0.004, 0.20), ("+Y", "-Y", "+X", "-X", "+Z", "-Z"))
    m.frustum("MAT_Lens", (0, -0.05, 0.215), 0.026, 0.024, 0.006, 8, "z", (False, True))
    a.led("LED_REC", "MAT_LED_Red", (0.005, 0.005, 0.001), (0, -0.0795, 0.2155))
    a.anchor("CAM_VIEW", (0, -0.05, 0.221), "camera_view")
    return a


def extinguisher():
    a = Asset("fac_extinguisher", "FacExtinguisher", "floor: origin = bottom-center; front (label) faces +Z")
    m = a.mb
    m.frustum("MAT_Facility_Dark", (0, 0, 0), 0.056, 0.056, 0.012, 10, "y", (False, False))
    m.frustum("MAT_Safety_Red", (0, 0.012, 0), 0.055, 0.055, 0.288, 10, "y", (False, False))
    m.frustum("MAT_Safety_Red", (0, 0.300, 0), 0.055, 0.026, 0.045, 10, "y", (False, True))
    m.frustum("MAT_Facility_Dark", (0, 0.345, 0), 0.026, 0.026, 0.030, 10, "y", (False, False))
    m.box("MAT_Facility_Dark", (0, 0.393, 0), (0.05, 0.036, 0.045), ("+Z", "-Z", "+X", "-X", "+Y"))
    m.box("MAT_Facility_Dark", (-0.025, 0.416, 0), (0.075, 0.010, 0.020))
    m.box("MAT_Facility_Dark", (-0.0475, 0.403, 0), (0.055, 0.006, 0.020))
    m.box("MAT_Facility_Dark", (0.040, 0.385, 0), (0.030, 0.016, 0.016), ("+Z", "-Z", "+X", "+Y", "-Y"))
    m.frustum("MAT_Sign_White", (0, 0.095, 0), 0.0555, 0.0555, 0.105, 10, "y", (False, False))
    m.box("MAT_Facility_Dark", (0, 0.150, 0.0531), (0.030, 0.060, 0.0006), ("+Z",))
    return a


def extinguisher_mount():
    a = Asset("fac_extinguisher_mount", "FacExtinguisherMount", "wall: origin = back-plate center on wall, protrudes +Z")
    m = a.mb
    m.box("MAT_Facility_Grey", (0, 0, 0.004), (0.10, 0.34, 0.008), ("+Z", "+X", "-X", "+Y", "-Y"))
    m.box("MAT_Metal", (0, -0.1555, 0.067), (0.10, 0.011, 0.12), ("+Y", "-Y", "+X", "-X", "+Z"))
    m.box("MAT_Metal", (0, -0.1475, 0.1265), (0.10, 0.015, 0.004), ("+Z", "-Z", "+X", "-X", "+Y"))
    for x in (-0.0585, 0.0585):
        m.box("MAT_Metal", (x, 0.06, 0.06825), (0.004, 0.028, 0.1205), ("+X", "-X", "+Y", "-Y", "+Z"))
    m.box("MAT_Metal", (0, 0.06, 0.1265), (0.121, 0.028, 0.004), ("+Z", "-Z", "+X", "-X", "+Y", "-Y"))
    a.anchor("EXT_SEAT", (0, -0.15, 0.067), "extinguisher_pivot")
    return a


def sign_safety():
    a = Asset("fac_sign_safety", "FacSignSafety", "wall: origin = back-plate center on wall, protrudes +Z")
    m = a.mb; t = 0.004; z = t + 0.0003
    m.box("MAT_Safety_Green", (0, 0, t / 2), (0.30, 0.30, t), ("+Z", "+X", "-X", "+Y", "-Y"))
    m.box("MAT_Sign_White", (0, 0, z), (0.07, 0.19, 0.0006), ("+Z",))
    m.box("MAT_Sign_White", (0, 0, z), (0.19, 0.07, 0.0006), ("+Z",))
    for p, s in (((0, 0.134), (0.276, 0.008)), ((0, -0.134), (0.276, 0.008)), ((-0.134, 0), (0.008, 0.26)), ((0.134, 0), (0.008, 0.26))):
        m.box("MAT_Sign_White", (p[0], p[1], z), (s[0], s[1], 0.0006), ("+Z",))
    return a


def sign_warning():
    a = Asset("fac_sign_warning", "FacSignWarning", "wall: origin = triangle centroid on wall, protrudes +Z")
    m = a.mb
    tri = [(-0.15, -0.0866), (0.15, -0.0866), (0.0, 0.1732)]
    m.prism("MAT_Sign_Black", tri, 0.0, 0.004, ("front", "side"))
    m.prism("MAT_Warning_Yellow", [(x * 0.84, y * 0.84) for x, y in tri], 0.004, 0.0055, ("front",))
    m.box("MAT_Sign_Black", (0, 0.0475, 0.0060), (0.022, 0.075, 0.001), ("+Z",))
    m.box("MAT_Sign_Black", (0, -0.034, 0.0060), (0.022, 0.022, 0.001), ("+Z",))
    return a


def sign_room():
    a = Asset("fac_sign_room", "FacSignRoom", "wall: origin = back-plate center on wall, protrudes +Z")
    m = a.mb; t = 0.004
    m.box("MAT_Facility_Dark", (0, 0, t / 2), (0.32, 0.12, t), ("+Z", "+X", "-X", "+Y", "-Y"))
    m.box("MAT_Sign_White", (0.015, 0, t + 0.0003), (0.27, 0.09, 0.0006), ("+Z",))
    m.box("MAT_Info_Blue", (-0.138, 0, t + 0.0003), (0.024, 0.09, 0.0006), ("+Z",))
    a.anchor("TEXT", (0.015, 0, t + 0.0007), "label3d_text_area_0.26x0.08")
    return a


def sign_directional():
    a = Asset("fac_sign_directional", "FacSignDirectional", "wall: origin = back-plate center on wall; arrow points +X (mirror with scale.x=-1, rotate Z for up/down)")
    m = a.mb; t = 0.004; z0, z1 = t, t + 0.0006
    m.box("MAT_Info_Blue", (0, 0, t / 2), (0.32, 0.12, t), ("+Z", "+X", "-X", "+Y", "-Y"))
    m.box("MAT_Sign_White", (-0.02, 0, t + 0.0003), (0.16, 0.028, 0.0006), ("+Z",))
    m.prism("MAT_Sign_White", [(0.06, -0.05), (0.125, 0.0), (0.06, 0.05)], z0, z1, ("front",))
    return a


def panel_control():
    a = Asset("fac_panel_control", "FacPanelControl", "wall: origin = back-plate center on wall, protrudes +Z")
    m = a.mb
    m.box("MAT_Facility_White", (0, 0, 0.02), (0.18, 0.24, 0.04), ("+Z", "+X", "-X", "+Y", "-Y"))
    m.box("MAT_Facility_Dark", (0, 0.05, 0.04075), (0.14, 0.09, 0.0015), ("+Z",))
    m.box("MAT_Emissive_Screen", (0, 0.05, 0.0423), (0.12, 0.07, 0.0008), ("+Z",))
    for x, mat in ((-0.04, "MAT_Facility_Dark"), (0, "MAT_Facility_Dark"), (0.04, "MAT_Safety_Red")):
        m.box(mat, (x, -0.03, 0.043), (0.028, 0.020, 0.006), ("+Z", "+X", "-X", "+Y", "-Y"))
    a.led("LED_STATUS", "MAT_LED_Green", (0.008, 0.008, 0.001), (0.07, -0.095, 0.0405))
    a.anchor("SCREEN", (0, 0.05, 0.0431), "screen_surface_0.12x0.07")
    for i, x in enumerate((-0.04, 0, 0.04), 1):
        a.anchor(f"BTN_{i:02d}", (x, -0.03, 0.046), "press_point")
    return a


def estop():
    a = Asset("fac_estop_enclosure", "FacEstopEnclosure", "wall: origin = back-plate center on wall, protrudes +Z")
    m = a.mb
    m.box("MAT_Warning_Yellow", (0, 0, 0.03), (0.10, 0.12, 0.06), ("+Z", "+X", "-X", "+Y", "-Y"))
    m.frustum("MAT_Facility_Dark", (0, 0, 0.06), 0.036, 0.034, 0.010, 10, "z", (False, True))
    m.frustum("MAT_Safety_Red", (0, 0, 0.070), 0.030, 0.026, 0.016, 10, "z", (False, True))
    a.anchor("PRESS", (0, 0, 0.086), "press_point")
    return a


ASSETS = [ceiling_light, emergency_light, wall_light, camera, extinguisher, extinguisher_mount,
          sign_safety, sign_warning, sign_room, sign_directional, panel_control, estop]

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    manifest = {"units": "meters", "front": "+Z", "assets": {}}
    for fn in ASSETS:
        a = fn(); info = a.save(out)
        manifest["assets"][a.name] = info
        print(f"{a.name:26s} tris={info['tris']:4d} surfaces={len(info['surfaces'])} size={info['size_m']}")
    json.dump(manifest, open(f"{out}/facility_support_manifest.json", "w"), indent=1)
