#!/usr/bin/env python3
"""
Procedural generator: fictional firewall appliance family (SysEng Sim - Data Center).
Outputs two .glb files (glTF 2.0) for Godot 4.x import.

Conventions
  - Units: meters. Y up. Front face = +Z (glTF/Godot-import standard). Rear = -Z.
  - Pivot: bottom-center of the footprint (origin at X=0, Y=0, Z=0 on the floor/shelf plane).
  - Port anchors: empty nodes under "Anchors/", placed on the port face, +Z = plug direction.
  - LED nodes under "LEDs/": one tiny mesh each, own material -> override per instance in Godot.
"""
import json, struct, sys
import numpy as np

# ---------------------------------------------------------------- materials
# name: (rgba, metallic, roughness, emissive_rgb)
MATS = {
    "MAT_Chassis":      ((0.13, 0.14, 0.16, 1), 0.3, 0.6, None),
    "MAT_Plate":        ((0.19, 0.20, 0.23, 1), 0.3, 0.5, None),
    "MAT_Lid":          ((0.27, 0.29, 0.32, 1), 0.4, 0.55, None),
    "MAT_EarMetal":     ((0.58, 0.60, 0.63, 1), 0.7, 0.4, None),
    "MAT_Rubber":       ((0.04, 0.04, 0.045, 1), 0.0, 0.9, None),
    "MAT_FW_Accent":    ((0.86, 0.22, 0.10, 1), 0.1, 0.5, None),   # security-appliance identity stripe
    "MAT_Grp_WAN":      ((0.95, 0.55, 0.08, 1), 0.1, 0.5, None),
    "MAT_Grp_LAN":      ((0.18, 0.50, 0.92, 1), 0.1, 0.5, None),
    "MAT_Grp_MGMT":     ((0.15, 0.78, 0.50, 1), 0.1, 0.5, None),
    "MAT_PortSocket":   ((0.015, 0.015, 0.02, 1), 0.0, 0.9, None),
    "MAT_VentDark":     ((0.02, 0.02, 0.025, 1), 0.0, 0.95, None),
    "MAT_LED_Green":    ((0.1, 0.9, 0.3, 1), 0.0, 0.4, (0.1, 1.0, 0.3)),
    "MAT_LED_AmberOff": ((0.25, 0.15, 0.02, 1), 0.0, 0.4, None),
    "MAT_LED_Off":      ((0.06, 0.07, 0.07, 1), 0.0, 0.4, None),
}
MAT_NAMES = list(MATS)

# ---------------------------------------------------------------- geometry
FACES = {  # name: (normal, u, v)  with u x v = normal (CCW from outside)
    "+Z": ((0, 0, 1), (1, 0, 0), (0, 1, 0)),
    "-Z": ((0, 0, -1), (-1, 0, 0), (0, 1, 0)),
    "+X": ((1, 0, 0), (0, 0, -1), (0, 1, 0)),
    "-X": ((-1, 0, 0), (0, 0, 1), (0, 1, 0)),
    "+Y": ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
    "-Y": ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
}


class MeshBuilder:
    def __init__(self):
        self.prims = {}  # mat -> (pos list, nrm list, idx list)

    def box(self, mat, c, s, faces=("+Z", "-Z", "+X", "-X", "+Y", "-Y")):
        P, N, I = self.prims.setdefault(mat, ([], [], []))
        c = np.array(c, float)
        h = np.array(s, float) / 2
        for f in faces:
            n, u, v = (np.array(a, float) for a in FACES[f])
            hu = abs(u) @ h
            hv = abs(v) @ h
            hn = abs(n) @ h
            ctr = c + n * hn
            base = len(P)
            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                P.append((ctr + u * hu * su + v * hv * sv).tolist())
                N.append(n.tolist())
            I += [base, base + 1, base + 2, base, base + 2, base + 3]

    def tris(self):
        return sum(len(i) // 3 for _, _, i in self.prims.values())


# ---------------------------------------------------------------- glTF writer
class GLTF:
    def __init__(self):
        self.bin = bytearray()
        self.views, self.accs, self.meshes, self.nodes = [], [], [], []
        self.mats = []
        for name in MAT_NAMES:
            rgba, met, rough, emis = MATS[name]
            m = {"name": name, "pbrMetallicRoughness": {"baseColorFactor": list(rgba),
                 "metallicFactor": met, "roughnessFactor": rough}}
            if emis:
                m["emissiveFactor"] = list(emis)
            self.mats.append(m)

    def _view(self, data, target):
        while len(self.bin) % 4:
            self.bin.append(0)
        self.views.append({"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data), "target": target})
        self.bin += data
        return len(self.views) - 1

    def _acc(self, view, ctype, count, atype, mn=None, mx=None):
        a = {"bufferView": view, "componentType": ctype, "count": count, "type": atype}
        if mn is not None:
            a["min"], a["max"] = mn, mx
        self.accs.append(a)
        return len(self.accs) - 1

    def add_mesh(self, name, mb):
        prims = []
        for mat, (P, N, I) in mb.prims.items():
            p = np.array(P, np.float32)
            n = np.array(N, np.float32)
            i = np.array(I, np.uint16)
            a_p = self._acc(self._view(p.tobytes(), 34962), 5126, len(p), "VEC3", p.min(0).tolist(), p.max(0).tolist())
            a_n = self._acc(self._view(n.tobytes(), 34962), 5126, len(n), "VEC3")
            a_i = self._acc(self._view(i.tobytes(), 34963), 5123, len(i), "SCALAR")
            prims.append({"attributes": {"POSITION": a_p, "NORMAL": a_n}, "indices": a_i,
                          "material": MAT_NAMES.index(mat), "mode": 4})
        self.meshes.append({"name": name, "primitives": prims})
        return len(self.meshes) - 1

    def node(self, name, mesh=None, t=None, extras=None, children=None):
        d = {"name": name}
        if mesh is not None:
            d["mesh"] = mesh
        if t is not None:
            d["translation"] = [float(x) for x in t]
        if extras:
            d["extras"] = extras
        if children:
            d["children"] = children
        self.nodes.append(d)
        return len(self.nodes) - 1

    def save(self, path, root):
        while len(self.bin) % 4:
            self.bin.append(0)
        doc = {"asset": {"version": "2.0", "generator": "gen_firewalls.py"},
               "scene": 0, "scenes": [{"nodes": [root]}], "nodes": self.nodes,
               "meshes": self.meshes, "materials": self.mats, "accessors": self.accs,
               "bufferViews": self.views, "buffers": [{"byteLength": len(self.bin)}]}
        j = json.dumps(doc, separators=(",", ":")).encode()
        j += b" " * ((4 - len(j) % 4) % 4)
        out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(j) + 8 + len(self.bin))
        out += struct.pack("<II", len(j), 0x4E4F534A) + j
        out += struct.pack("<II", len(self.bin), 0x004E4942) + bytes(self.bin)
        open(path, "wb").write(out)


# ---------------------------------------------------------------- shared parts
PORT_ORDER = ["MGMT", "WAN_01", "WAN_02", "LAN_01", "LAN_02", "LAN_03", "LAN_04"]


def grp(pid):
    return "MAT_Grp_MGMT" if pid == "MGMT" else ("MAT_Grp_WAN" if pid.startswith("WAN") else "MAT_Grp_LAN")


def rj45(mb, pid, x, y, zf):
    """RJ45 port on a +Z face at depth zf: frame (group color) + dark socket. Returns anchor position."""
    m = grp(pid)
    W, H, t = 0.022, 0.019, 0.002
    bw, bh = 0.003, 0.0035
    mb.box(m, (x - W / 2 + bw / 2, y, zf + t / 2), (bw, H, t), ("+Z", "+X", "-X", "+Y", "-Y"))
    mb.box(m, (x + W / 2 - bw / 2, y, zf + t / 2), (bw, H, t), ("+Z", "+X", "-X", "+Y", "-Y"))
    mb.box(m, (x, y + H / 2 - bh / 2, zf + t / 2), (W - 2 * bw, bh, t), ("+Z", "+Y", "-Y"))
    mb.box(m, (x, y - H / 2 + bh / 2, zf + t / 2), (W - 2 * bw, bh, t), ("+Z", "+Y", "-Y"))
    mb.box("MAT_PortSocket", (x, y, zf + 0.0003), (W - 2 * bw, H - 2 * bh, 0.0006), ("+Z",))
    return (x, y, zf)


def led_mesh(gl, cache, size, mat):
    key = (size, mat)
    if key not in cache:
        mb = MeshBuilder()
        mb.box(mat, (0, 0, 0), (size[0], size[1], size[2]), ("+Z", "+X", "-X", "+Y", "-Y"))
        cache[key] = gl.add_mesh(f"LED_{size[0]*1000:.0f}x{size[1]*1000:.0f}_{mat[4:]}", mb)
    return cache[key]


SYS_LEDS = [("PWR", "MAT_LED_Green"), ("STATUS", "MAT_LED_Green"),
            ("ALERT", "MAT_LED_AmberOff"), ("HA", "MAT_LED_Off")]


def finish(gl, mb, root_name, anchors, leds, mesh_name):
    body = gl.add_mesh(mesh_name, mb)
    n_body = gl.node("Body", mesh=body)
    a_nodes = [gl.node(pid, t=pos, extras={"port_id": pid, "port_type": pid.split("_")[0],
                                           "plug_dir": "+Z"}) for pid, pos in anchors]
    n_anch = gl.node("Anchors", children=a_nodes)
    l_nodes = [gl.node(name, mesh=mesh, t=pos, extras={"led_id": name}) for name, mesh, pos in leds]
    n_led = gl.node("LEDs", children=l_nodes)
    return gl.node(root_name, children=[n_body, n_anch, n_led])


# ---------------------------------------------------------------- 1U enterprise firewall
def build_1u(path):
    gl, mb = GLTF(), MeshBuilder()
    W, WP, H, D = 0.438, 0.4826, 0.044, 0.30
    zf, zr = D / 2, -D / 2
    tp = 0.003  # front plate thickness
    # chassis + front plate + ears
    mb.box("MAT_Chassis", (0, H / 2, -tp / 2), (W, H, D - tp), ("-Z", "+X", "-X", "+Y", "-Y"))
    mb.box("MAT_Plate", (0, H / 2, zf - tp / 2), (W, H, tp), ("+Z", "+Y", "-Y"))
    ew = (WP - W) / 2
    for sx in (-1, 1):
        ex = sx * (W / 2 + ew / 2)
        mb.box("MAT_EarMetal", (ex, H / 2, zf - tp / 2), (ew, H, tp), ("+Z", "-Z", "+X", "-X", "+Y", "-Y"))
        mb.box("MAT_VentDark", (ex, H / 2, zf + 0.0002), (0.0065, 0.0125, 0.0004), ("+Z",))  # rack-screw slot
    # top lid + vent slots (two fields)
    mb.box("MAT_Lid", (0, H + 0.0004, -tp / 2 - 0.01), (W - 0.004, 0.0008, D - tp - 0.025), ("+Y",))
    for fx in (-0.10, 0.10):
        for i in range(8):
            mb.box("MAT_VentDark", (fx + (i - 3.5) * 0.008, H + 0.0010, -0.02), (0.003, 0.0004, 0.12), ("+Y",))
    # front: left vent slots
    for i in range(5):
        mb.box("MAT_VentDark", (-0.205 + i * 0.012, H / 2, zf + 0.0002), (0.0035, 0.026, 0.0004), ("+Z",))
    # front: accent stripe (security identity)
    mb.box("MAT_FW_Accent", (0, 0.0425, zf + 0.0003), (0.40, 0.0014, 0.0006), ("+Z", "+Y"))
    # ports
    xs = {"MGMT": -0.105, "WAN_01": -0.045, "WAN_02": -0.017,
          "LAN_01": 0.045, "LAN_02": 0.073, "LAN_03": 0.101, "LAN_04": 0.129}
    py = 0.0185
    anchors, leds, cache = [], [], {}
    for pid in PORT_ORDER:
        anchors.append((pid, rj45(mb, pid, xs[pid], py, zf)))
        leds.append((f"LED_{pid}", led_mesh(gl, cache, (0.005, 0.003, 0.0008), "MAT_LED_Green"),
                     (xs[pid], 0.0325, zf + 0.0004)))
    for names, m in ((["MGMT"], "MAT_Grp_MGMT"), (["WAN_01", "WAN_02"], "MAT_Grp_WAN"),
                     (["LAN_01", "LAN_02", "LAN_03", "LAN_04"], "MAT_Grp_LAN")):
        a, b = xs[names[0]], xs[names[-1]]
        mb.box(m, ((a + b) / 2, 0.0385, zf + 0.0003), (b - a + 0.022, 0.0018, 0.0006), ("+Z", "+Y"))
    # system LEDs on dark inset panel
    mb.box("MAT_PortSocket", (0.1865, H / 2, zf + 0.0003), (0.050, 0.030, 0.0006), ("+Z",))
    for k, (nm, mat) in enumerate(SYS_LEDS):
        x = 0.1735 + (k % 2) * 0.026
        y = 0.0295 if k < 2 else 0.0145
        leds.append((f"LED_{nm}", led_mesh(gl, cache, (0.006, 0.006, 0.0008), mat), (x, y, zf + 0.0007)))
    # rear: fans, PSU plate, power inlet (C14-style)
    for fx in (-0.15, -0.04):
        mb.box("MAT_VentDark", (fx, H / 2, zr - 0.0002), (0.046, 0.034, 0.0004), ("-Z",))
        for i in range(4):
            mb.box("MAT_Chassis", (fx + (i - 1.5) * 0.010, H / 2, zr - 0.0005), (0.002, 0.034, 0.0006), ("-Z",))
    mb.box("MAT_Plate", (0.165, H / 2, zr - 0.0005), (0.075, 0.036, 0.001), ("-Z",))
    mb.box("MAT_EarMetal", (0.165, H / 2, zr - 0.0013), (0.034, 0.024, 0.0006), ("-Z",))   # inlet frame
    mb.box("MAT_PortSocket", (0.165, H / 2, zr - 0.0018), (0.026, 0.016, 0.0004), ("-Z",))
    root = finish(gl, mb, "FW_1U_Enterprise", anchors, leds, "FW_1U_Body")
    gl.save(path, root)
    return mb.tris(), len(leds)


# ---------------------------------------------------------------- compact firewall
def build_compact(path):
    gl, mb = GLTF(), MeshBuilder()
    W, H, D, y0 = 0.230, 0.044, 0.150, 0.003
    zf, zr = D / 2, -D / 2
    yt = y0 + H
    mb.box("MAT_Chassis", (0, y0 + H / 2, 0), (W, H, D), ("+Z", "-Z", "+X", "-X", "+Y", "-Y"))
    mb.box("MAT_Lid", (0, yt + 0.0004, -0.004), (W - 0.006, 0.0008, D - 0.014), ("+Y",))
    # rubber feet + wall-mount flanges (bottom, symmetric around pivot)
    for fx in (-0.09, 0.09):
        for fz in (-0.045, 0.045):
            mb.box("MAT_Rubber", (fx, 0.0015, fz), (0.014, 0.003, 0.014), ("+X", "-X", "+Z", "-Z", "-Y"))
    for sx in (-1, 1):
        fxc = sx * (W / 2 + 0.011)
        mb.box("MAT_EarMetal", (fxc, y0 + 0.001, 0), (0.022, 0.002, 0.060), ("+Y", "-Y", "+X", "-X", "+Z", "-Z"))
        mb.box("MAT_VentDark", (fxc + sx * 0.002, y0 + 0.0022, 0), (0.007, 0.0004, 0.014), ("+Y",))
    # top vents (rear half) + side vents
    for i in range(7):
        mb.box("MAT_VentDark", (-0.06 + i * 0.020, yt + 0.0010, -0.025), (0.003, 0.0004, 0.070), ("+Y",))
    for sx, f in ((-1, "-X"), (1, "+X")):
        for i in range(6):
            mb.box("MAT_VentDark", (sx * (W / 2 + 0.0002), y0 + H / 2, -0.03 + i * 0.012), (0.0004, 0.022, 0.0035), (f,))
    mb.box("MAT_FW_Accent", (0, 0.0445, zf + 0.0003), (0.20, 0.0014, 0.0006), ("+Z", "+Y"))
    # ports (front)
    pitch, gap = 0.025, 0.012
    span = 6 * pitch + 2 * gap
    x = -span / 2
    xs = {}
    for k, pid in enumerate(PORT_ORDER):
        xs[pid] = x
        x += pitch + (gap if pid in ("MGMT", "WAN_02") else 0)
    py = 0.0235
    anchors, leds, cache = [], [], {}
    for pid in PORT_ORDER:
        anchors.append((pid, rj45(mb, pid, xs[pid], py, zf)))
        leds.append((f"LED_{pid}", led_mesh(gl, cache, (0.005, 0.003, 0.0008), "MAT_LED_Green"),
                     (xs[pid], 0.0365, zf + 0.0004)))
    for names, m in ((["MGMT"], "MAT_Grp_MGMT"), (["WAN_01", "WAN_02"], "MAT_Grp_WAN"),
                     (["LAN_01", "LAN_02", "LAN_03", "LAN_04"], "MAT_Grp_LAN")):
        a, b = xs[names[0]], xs[names[-1]]
        mb.box(m, ((a + b) / 2, 0.0405, zf + 0.0003), (b - a + 0.022, 0.0018, 0.0006), ("+Z", "+Y"))
    # system LEDs (bottom-left row)
    mb.box("MAT_PortSocket", (-0.0675, 0.0085, zf + 0.0003), (0.058, 0.008, 0.0006), ("+Z",))
    for k, (nm, mat) in enumerate(SYS_LEDS):
        leds.append((f"LED_{nm}", led_mesh(gl, cache, (0.006, 0.004, 0.0008), mat),
                     (-0.087 + k * 0.016, 0.0085, zf + 0.0007)))
    # rear: DC/AC power input (barrel-style) + small plate
    mb.box("MAT_Plate", (0.075, y0 + H / 2, zr - 0.0004), (0.045, 0.030, 0.0008), ("-Z",))
    mb.box("MAT_EarMetal", (0.075, y0 + H / 2, zr - 0.0011), (0.020, 0.020, 0.0006), ("-Z",))
    mb.box("MAT_PortSocket", (0.075, y0 + H / 2, zr - 0.0016), (0.012, 0.012, 0.0004), ("-Z",))
    root = finish(gl, mb, "FW_Compact", anchors, leds, "FW_Compact_Body")
    gl.save(path, root)
    return mb.tris(), len(leds)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    print("1U      tris/leds:", build_1u(f"{out}/fw_1u_enterprise.glb"))
    print("Compact tris/leds:", build_compact(f"{out}/fw_compact.glb"))
