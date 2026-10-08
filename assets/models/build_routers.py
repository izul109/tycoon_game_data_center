#!/usr/bin/env python3
"""RX Series (fictional) router family -> GLB for Godot 4.x. Meters, Y-up, ports face +Z (front)."""
import os, math, json, struct
_src = open("/home/claude/build_kit.py").read()
_a = _src.index("# ---------------------------------------------------------------- constants")
_b = _src.index("# ---------------------------------------------------------------- assets")
_c = _src.index("# ---------------------------------------------------------------- GLB writer")
_d = _src.index("# ---------------------------------------------------------------- export")
OUT = "/mnt/user-data/outputs/RouterFamily"
os.makedirs(OUT + "/assets", exist_ok=True)
exec(_src[_a:_b].replace('OUT = "/mnt/user-data/outputs/VerticalKit"', ""))   # utils, Mesh, Node, MATS
exec(_src[_c:_d])                                                               # write_glb

MATS.clear()
MATS.update({
    "M_Faceplate":     ((0.07, 0.08, 0.10, 1), 0.4, 0.55, None),
    "M_Chassis":       ((0.34, 0.36, 0.39, 1), 0.8, 0.45, None),
    "M_Accent":        ((0.00, 0.62, 0.62, 1), 0.2, 0.40, None),
    "M_Port_Shell":    ((0.55, 0.57, 0.60, 1), 0.9, 0.35, None),
    "M_Port_Dark":     ((0.01, 0.01, 0.012, 1), 0.0, 0.90, None),
    "M_Vent_Dark":     ((0.02, 0.02, 0.025, 1), 0.0, 0.90, None),
    "M_Rubber":        ((0.03, 0.03, 0.03, 1), 0.0, 0.95, None),
    "M_Tag_WAN":       ((0.95, 0.55, 0.10, 1), 0.0, 0.60, None),
    "M_Tag_LAN":       ((0.15, 0.75, 0.40, 1), 0.0, 0.60, None),
    "M_Tag_UPLINK":    ((0.30, 0.45, 0.95, 1), 0.0, 0.60, None),
    "M_Tag_MGMT":      ((0.80, 0.80, 0.85, 1), 0.0, 0.60, None),
    "M_LED_Green":     ((0.05, 0.20, 0.08, 1), 0.0, 0.50, (0.10, 1.00, 0.30)),
    "M_LED_Amber":     ((0.25, 0.15, 0.02, 1), 0.0, 0.50, (1.00, 0.60, 0.05)),
    "M_LED_Blue":      ((0.05, 0.10, 0.25, 1), 0.0, 0.50, (0.20, 0.50, 1.00)),
})
TAG = {"WAN": "M_Tag_WAN", "LAN": "M_Tag_LAN", "UPLINK": "M_Tag_UPLINK", "MGMT": "M_Tag_MGMT"}
H1, H2 = 0.04445, 0.0889       # 1U / 2U
RACK_W, BODY_W = 0.4826, 0.440

# ---------------------------------------------------------------- helpers
def fb(m, mat, x0, x1, y0, y1, z0, d, skip=("-z",)):      # front-facing box (grows +Z)
    m.box(mat, (x0, y0, z0), (x1, y1, z0+d), skip)
def rb(m, mat, x0, x1, y0, y1, zr, d):                    # rear-facing box (grows -Z)
    m.box(mat, (x0, y0, zr-d), (x1, y1, zr), ("+z",))

LEDMESH = {}
for k, mt in (("green", "M_LED_Green"), ("amber", "M_LED_Amber"), ("blue", "M_LED_Blue")):
    me = Mesh("LED_" + k); me.box(mt, (-0.0015, -0.0015, -0.0015), (0.0015, 0.0015, 0.0), ("-z",)); LEDMESH[k] = me

PORT = {"rj45": dict(w=0.0155, h=0.0140, t=0.0015, d=0.003, ring="M_Port_Shell"),
        "sfp":  dict(w=0.0140, h=0.0100, t=0.0012, d=0.004, ring="M_Accent")}

class Dev:
    """collects anchors/LEDs and layout rectangles (for overlap validation)"""
    def __init__(self): self.ports, self.leds, self.rects = [], [], []

def port(m, dev, name, kind, cx, cy, z0, role, speed, off=(0, 0, 0), parent="ports"):
    p = PORT[kind]; w, h, t, d = p["w"], p["h"], p["t"], p["d"]
    fb(m, p["ring"], cx-w/2, cx+w/2, cy+h/2-t, cy+h/2, z0, d)
    fb(m, p["ring"], cx-w/2, cx+w/2, cy-h/2, cy-h/2+t, z0, d)
    fb(m, p["ring"], cx-w/2, cx-w/2+t, cy-h/2+t, cy+h/2-t, z0, d)
    fb(m, p["ring"], cx+w/2-t, cx+w/2, cy-h/2+t, cy+h/2-t, z0, d)
    iw, ih = w-2*t, h-2*t
    m.poly("M_Port_Dark", [(cx-iw/2, cy-ih/2, z0+0.001), (cx+iw/2, cy-ih/2, z0+0.001),
                           (cx+iw/2, cy+ih/2, z0+0.001), (cx-iw/2, cy+ih/2, z0+0.001)], (0, 0, 1))
    pos = (cx, cy, z0+d)
    dev.ports.append((name, pos, kind, role, speed, parent))
    dev.rects.append((name, cx+off[0], cy+off[1], w, h))

def led(dev, name, cx, cy, zs, kind="green", off=(0, 0), parent="leds"):
    dev.leds.append((name, LEDMESH[kind], (cx, cy, zs+0.0015), parent))
    dev.rects.append((name, cx+off[0], cy+off[1], 0.003, 0.003))

def strip(m, mat, x0, x1, y, zs):
    fb(m, mat, x0, x1, y-0.00125, y+0.00125, zs, 0.0005)

def ears(m, H, holes, zf, t=0.003):
    for sx in (-1, 1):
        X = lambda a, b: (min(sx*a, sx*b), max(sx*a, sx*b))
        for a, b in ((0.220, 0.2262), (0.2352, 0.2413)):
            x0, x1 = X(a, b); m.box("M_Faceplate", (x0, 0, zf-t), (x1, H, zf))
        segs = [0.0]
        for hy in holes: segs += [hy-0.0035, hy+0.0035]
        segs.append(H)
        x0, x1 = X(0.2262, 0.2352)
        for i in range(0, len(segs), 2):
            if segs[i+1]-segs[i] > 1e-6: m.box("M_Faceplate", (x0, segs[i], zf-t), (x1, segs[i+1], zf))

def vent_front(m, x0, x1, y0, y1, zs, n):
    fb(m, "M_Vent_Dark", x0, x1, y0, y1, zs, 0.0005)
    pitch = (x1-x0-0.006)/(n-1)
    for i in range(n):
        cx = x0+0.003+pitch*i
        fb(m, "M_Faceplate", cx-0.002, cx+0.002, y0+0.001, y1-0.001, zs+0.0005, 0.0020)

def vent_rear_h(m, x0, x1, y0, y1, zr, n):
    rb(m, "M_Vent_Dark", x0, x1, y0, y1, zr, 0.0005)
    for i in range(n):
        cy = y0+0.004+(y1-y0-0.008)*i/(n-1)
        rb(m, "M_Faceplate", x0+0.001, x1-0.001, cy-0.0015, cy+0.0015, zr-0.0005, 0.0020)

def iec_inlet(m, cx, cy, zr):
    rb(m, "M_Port_Shell", cx-0.01375, cx+0.01375, cy-0.0095, cy+0.0095, zr, 0.006)
    m.poly("M_Port_Dark", [(cx-0.0105, cy-0.0065, zr-0.0065), (cx+0.0105, cy-0.0065, zr-0.0065),
                           (cx+0.0105, cy+0.0065, zr-0.0065), (cx-0.0105, cy+0.0065, zr-0.0065)], (0, 0, -1))

def mk_nodes(dev, extra_children=()):
    pn = Node("Ports"); ln = Node("LEDs")
    for name, pos, kind, role, speed, parent in dev.ports:
        if parent == "ports":
            pn.children.append(Node(name, t=pos, extras={"anchor": name, "role": role, "connector": kind.upper(),
                                                         "speed": speed, "cable_dir": "+Z"}))
    for name, me, pos, parent in dev.leds:
        if parent == "leds": ln.children.append(Node(name, me, t=pos))
    return [pn, ln] + list(extra_children)

# ---------------------------------------------------------------- RX-500 rack router (1U)
def build_rack():
    dev = Dev(); m = Mesh("Router_Rack"); D = 0.30; zf = D/2
    m.box("M_Chassis", (-0.22, 0.001, -zf), (0.22, 0.0435, zf-0.004))
    m.box("M_Faceplate", (-0.22, 0, zf-0.004), (0.22, H1, zf))
    ears(m, H1, [0.00635, 0.0381], zf)
    fb(m, "M_Accent", -0.22, 0.22, 0.0418, 0.0432, zf, 0.0005)
    cy = 0.0205
    layout = [("MGMT", "rj45", -0.165, "MGMT", "1G")] + \
             [("WAN_%02d" % (i+1), "rj45", -0.125+0.019*i, "WAN", "1G") for i in range(2)] + \
             [("LAN_%02d" % (i+1), "rj45", -0.060+0.019*i, "LAN", "1G") for i in range(4)] + \
             [("UPLINK_%02d" % (i+1), "sfp", 0.040+0.0235*i, "UPLINK", "10G") for i in range(2)]
    groups = {}
    for name, kind, cx, role, spd in layout:
        port(m, dev, name, kind, cx, cy, zf, role.lower(), spd)
        led(dev, "LED_" + name, cx, 0.0345, zf)
        groups.setdefault(role, []).append(cx)
    for role, xs in groups.items(): strip(m, TAG[role], min(xs)-0.0078, max(xs)+0.0078, 0.0105, zf)
    for i, (n, y, k) in enumerate((("PWR", 0.0335, "green"), ("SYS", 0.0205, "blue"), ("ALM", 0.0075, "amber"))):
        led(dev, "LED_" + n, -0.2055, y, zf, k)
    vent_front(m, 0.100, 0.200, 0.006, 0.038, zf, 9)
    # rear: 2 fan grilles, IEC inlet, rocker switch, ground stud
    zr = -zf
    for cx in (-0.15, -0.09): vent_rear_h(m, cx-0.02, cx+0.02, 0.004, 0.040, zr, 5)
    iec_inlet(m, 0.164, 0.022, zr)
    rb(m, "M_Faceplate", 0.115, 0.135, 0.012, 0.032, zr, 0.004)
    rb(m, "M_Port_Shell", 0.187, 0.193, 0.019, 0.025, zr, 0.006)
    pwr = Node("PWR_IN", t=(0.164, 0.022, zr-0.0065), ry=180, extras={"anchor": "PWR_IN", "connector": "IEC_C14", "cable_dir": "-Z"})
    root = Node("Router_Rack", m, children=mk_nodes(dev, [Node("Rear", children=[pwr])]),
                extras={"model": "RX-500", "form": "1U rack", "rack_units": 1})
    return root, dev

# ---------------------------------------------------------------- RX-100 compact router
def build_compact():
    dev = Dev(); m = Mesh("Router_Compact"); c = 0.004; hw, y0, y1 = 0.075, 0.004, 0.042
    prof = [(-hw+c, y0), (hw-c, y0), (hw, y0+c), (hw, y1-c), (hw-c, y1), (-hw+c, y1), (-hw, y1-c), (-hw, y0+c)]
    m.extrude_profile("M_Chassis", prof, -0.110, 0.110)
    for sx in (-1, 1):
        for sz in (-1, 1):
            m.box("M_Rubber", (sx*0.085-0.006, 0, sz*0.055-0.006), (sx*0.085+0.006, 0.004, sz*0.055+0.006), ("+y",))
    zf = hw
    fb(m, "M_Faceplate", -0.100, 0.100, 0.010, 0.036, zf, 0.001)
    zs = zf+0.001
    fb(m, "M_Accent", -0.100, 0.100, 0.0372, 0.0382, zf, 0.0005)
    cy = 0.0225
    layout = [("WAN_01", -0.075, "WAN")] + [("LAN_%02d" % (i+1), -0.030+0.0195*i, "LAN") for i in range(4)]
    groups = {}
    for name, cx, role in layout:
        port(m, dev, name, "rj45", cx, cy, zs, role.lower(), "1G")
        led(dev, "LED_" + name, cx, 0.0335, zs)
        groups.setdefault(role, []).append(cx)
    for role, xs in groups.items(): strip(m, TAG[role], min(xs)-0.0078, max(xs)+0.0078, 0.0125, zs)
    for n, x, k in (("PWR", 0.062, "green"), ("SYS", 0.075, "blue"), ("ALM", 0.088, "amber")):
        led(dev, "LED_" + n, x, 0.0225, zs, k)
    for i in range(9):   # top vent slats
        z = -0.030+0.0075*i
        m.box("M_Vent_Dark", (-0.060, y1, z-0.002), (0.060, y1+0.0005, z+0.002), ("-y",))
    zr = -hw   # rear: DC jack + 2 vent slots
    rb(m, "M_Port_Shell", 0.0645, 0.0755, 0.0170, 0.0280, zr, 0.008)
    m.poly("M_Port_Dark", [(0.0665, 0.0190, zr-0.0085), (0.0735, 0.0190, zr-0.0085), (0.0735, 0.0260, zr-0.0085), (0.0665, 0.0260, zr-0.0085)], (0, 0, -1))
    for x in (-0.05, -0.03): rb(m, "M_Vent_Dark", x-0.008, x+0.008, 0.014, 0.034, zr, 0.0005)
    for sx in (-1, 1):   # wall-mount tabs with keyhole slots
        a, b = (0.110, 0.135) if sx > 0 else (-0.135, -0.110)
        m.box("M_Chassis", (a, 0.004, -0.070), (b, 0.0065, -0.040))
        sa, sb = (0.1175, 0.1275) if sx > 0 else (-0.1275, -0.1175)
        m.box("M_Port_Dark", (sa, 0.0065, -0.062), (sb, 0.0069, -0.048), ("-y",))
    pwr = Node("PWR_IN", t=(0.070, 0.0225, zr-0.0085), ry=180, extras={"anchor": "PWR_IN", "connector": "DC_BARREL", "cable_dir": "-Z"})
    root = Node("Router_Compact", m, children=mk_nodes(dev, [Node("Rear", children=[pwr])]),
                extras={"model": "RX-100", "form": "desktop / wall-mount"})
    return root, dev

# ---------------------------------------------------------------- RX-900 modular router (2U)
BAY_X = [-0.09875+0.09*k for k in range(4)]
MOD_Y0 = 0.0037

def build_module(kind):
    """returns (mesh, ports spec, leds spec) in module-local coords: x center, y from module bottom, plate front z=0..0.003"""
    name = {"WAN": "Module_WAN", "LAN": "Module_LAN", "UPLINK": "Module_UPLINK", "BLANK": "Module_BLANK"}[kind]
    m = Mesh(name); hw, Hm = 0.04375, 0.0815
    m.box("M_Faceplate", (-hw, 0, 0), (hw, Hm, 0.003), ("-z",))
    depth = 0.10 if kind != "BLANK" else 0.03
    m.box("M_Chassis", (-0.0432, 0.0005, -depth), (0.0432, 0.0810, 0), ("+z",))
    for y in (0.0017, 0.0762):      # ejector levers
        fb(m, "M_Port_Shell", -0.012, 0.012, y, y+0.0036, 0.003, 0.004)
    spec = []
    if kind == "BLANK":
        fb(m, "M_Vent_Dark", -0.030, 0.030, 0.012, 0.068, 0.003, 0.0005)
        for i in range(6):
            cy = 0.016+0.0095*i
            fb(m, "M_Faceplate", -0.029, 0.029, cy-0.0015, cy+0.0015, 0.0035, 0.0020)
        return m, spec
    fb(m, TAG[kind], -0.034, 0.034, 0.0725, 0.0745+0.0, 0.003, 0.0005)
    if kind == "WAN":   spec = [("WAN_01", "rj45", 0.0, 0.0575, "1G"), ("WAN_02", "rj45", 0.0, 0.0235, "1G")]
    if kind == "LAN":   spec = [("LAN_01", "rj45", -0.0215, 0.0575, "1G"), ("LAN_02", "rj45", 0.0215, 0.0575, "1G"),
                                ("LAN_03", "rj45", -0.0215, 0.0235, "1G"), ("LAN_04", "rj45", 0.0215, 0.0235, "1G")]
    if kind == "UPLINK": spec = [("UPLINK_01", "sfp", 0.0, 0.0575, "10G"), ("UPLINK_02", "sfp", 0.0, 0.0235, "10G")]
    return m, spec

def build_modular():
    dev = Dev(); m = Mesh("Router_Modular"); D = 0.38; zf = D/2; zb = 0.09
    m.box("M_Chassis", (-0.22, 0.001, -zf), (0.22, H2-0.001, zb))                 # rear block
    m.box("M_Chassis", (-0.22, 0.001, zb), (-0.145, H2-0.001, zf-0.004))          # supervisor body
    m.box("M_Faceplate", (-0.22, 0, zf-0.004), (-0.145, H2, zf))                  # supervisor plate
    ears(m, H2, [0.00635, 0.0381, 0.0508, 0.08255], zf)
    m.box("M_Faceplate", (-0.145, 0, zb), (0.22, MOD_Y0, zf))                     # bottom rail
    m.box("M_Faceplate", (-0.145, H2-MOD_Y0-0.0000, zb), (0.22, H2, zf)) if False else m.box("M_Faceplate", (-0.145, 0.0852, zb), (0.22, H2, zf))
    for k in range(5):
        x0 = -0.145+0.09*k; w = 0.0025 if k < 4 else 0.005
        m.box("M_Faceplate", (x0, MOD_Y0, zb), (x0+w, 0.0852, zf))
    fb(m, "M_Accent", -0.22, 0.22, 0.0866, 0.0880, zf, 0.0005)
    # supervisor front: LEDs, MGMT, vent
    zs = zf
    for n, x, k in (("PWR", -0.200, "green"), ("SYS", -0.185, "blue"), ("ALM", -0.170, "amber")):
        led(dev, "LED_" + n, x, 0.0775, zs, k)
    port(m, dev, "MGMT", "rj45", -0.1825, 0.0500, zs, "mgmt", "1G")
    led(dev, "LED_MGMT", -0.1825, 0.0620, zs)
    strip(m, TAG["MGMT"], -0.1903, -0.1747, 0.0395, zs)
    fb(m, "M_Vent_Dark", -0.205, -0.160, 0.008, 0.032, zs, 0.0005)
    for i in range(5):
        cy = 0.0115+0.0045*i*1.0 + 0.0
        fb(m, "M_Faceplate", -0.204, -0.161, 0.0105+0.0052*i, 0.0135+0.0052*i, zs+0.0005, 0.002)
    # rear: two PSU plates, central fan grille
    zr = -zf
    for cx in (-0.14, 0.14):
        rb(m, "M_Faceplate", cx-0.06, cx+0.06, 0.005, 0.0839, zr, 0.002)
        iec_inlet(m, cx, 0.062, zr-0.002)
        vent_rear_h(m, cx-0.045, cx+0.045, 0.012, 0.040, zr-0.002, 4)
    vent_rear_h(m, -0.06, 0.06, 0.008, 0.080, zr, 7)
    # bays / modules
    bays = []
    for k, kind in enumerate(("WAN", "LAN", "UPLINK", "BLANK")):
        mm, spec = build_module(kind)
        mod_dev = Dev(); ch = []
        for pname, pk, px, py, spd in spec:
            port(mm, mod_dev, pname, pk, px, py, 0.003, kind.lower(), spd, off=(BAY_X[k], MOD_Y0))
            led(mod_dev, "LED_" + pname, px, py+0.0105, 0.003, off=(BAY_X[k], MOD_Y0))
        for n, pos, _k, role, spd, _p in mod_dev.ports:
            ch.append(Node(n, t=pos, extras={"anchor": n, "role": role, "connector": _k.upper(), "speed": spd, "cable_dir": "+Z"}))
        for n, me, pos, _p in mod_dev.leds: ch.append(Node(n, me, t=pos))
        dev.rects += mod_dev.rects
        modn = Node(mm.name, mm, children=ch, extras={"module_type": kind, "pull_axis": "+Z", "pull_distance": 0.10})
        bays.append(Node("Bay_%d" % (k+1), t=(BAY_X[k], MOD_Y0, zf), children=[modn],
                         extras={"slot": k+1, "module_pull_dir": "+Z"}))
    pn = Node("Ports"); ln = Node("LEDs")
    for name, pos, kind, role, speed, parent in dev.ports:
        pn.children.append(Node(name, t=pos, extras={"anchor": name, "role": role, "connector": kind.upper(), "speed": speed, "cable_dir": "+Z"}))
    for name, me, pos, parent in dev.leds: ln.children.append(Node(name, me, t=pos))
    pa = Node("PWR_IN_A", t=(-0.14, 0.062, zr-0.0085), ry=180, extras={"anchor": "PWR_IN_A", "connector": "IEC_C14", "cable_dir": "-Z"})
    pb = Node("PWR_IN_B", t=(0.14, 0.062, zr-0.0085), ry=180, extras={"anchor": "PWR_IN_B", "connector": "IEC_C14", "cable_dir": "-Z"})
    root = Node("Router_Modular", m, children=[pn, ln, Node("Bays", children=bays), Node("Rear", children=[pa, pb])],
                extras={"model": "RX-900", "form": "2U rack, 4 bays", "rack_units": 2})
    return root, dev

# ---------------------------------------------------------------- export
builders = {"Router_Compact": build_compact, "Router_Rack": build_rack, "Router_Modular": build_modular}
built = {k: f() for k, f in builders.items()}
for k, (root, dev) in built.items():
    write_glb(f"{OUT}/assets/{k}.glb", [root], k)
SHEET_X = {"Router_Compact": -0.55, "Router_Rack": 0.0, "Router_Modular": 0.66}
sheet = []
for k, f in builders.items():
    r, _ = f(); r.t = (SHEET_X[k], 0, 0); sheet.append(r)
write_glb(f"{OUT}/Router_Family_Sheet.glb", sheet, "Router_Family")

# ---------------------------------------------------------------- validation
def collect(node, M0, acc, depth=0):
    t = node.t; h = math.radians(node.ry)
    c, s = math.cos(h), math.sin(h)
    p = (M0[0] + c*t[0] + s*t[2] if False else None)
def walk(node, origin=(0, 0, 0), acc=None):
    acc = acc if acc is not None else []
    o = (origin[0]+node.t[0], origin[1]+node.t[1], origin[2]+node.t[2])   # no nested rotations affect front-facing anchors
    acc.append((node, o))
    for ch in node.children: walk(ch, o, acc)
    return acc

def tri_count(node):
    tot, seen = 0, set()
    for n, _ in walk(node):
        if n.mesh is not None: tot += sum(len(pr["idx"])//3 for pr in n.mesh.p.values())
    return tot

print("== family validation ==")
for k, (root, dev) in built.items():
    mn, mx = bounds(root.mesh) if False else (None, None)
    P = [v for pr in root.mesh.p.values() for v in pr["pos"]]
    xs = [v[0] for v in P]; ys = [v[1] for v in P]; zs = [v[2] for v in P]
    allw = walk(root)
    names = [n.name for n, _ in allw if n.extras and "anchor" in n.extras]
    # include module meshes in bounds
    for n, o in allw:
        if n.mesh is not None and n is not root:
            for pr in n.mesh.p.values():
                for v in pr["pos"]:
                    xs.append(v[0]+o[0]); ys.append(v[1]+o[1]); zs.append(v[2]+o[2])
    print(f"{k}: size x={max(xs)-min(xs):.4f} y={max(ys)-min(ys):.4f} z={max(zs)-min(zs):.4f}  "
          f"min=({min(xs):.4f},{min(ys):.4f},{min(zs):.4f})  tris={tri_count(root)}")
    print("   anchors:", ", ".join(sorted(names)))
    # overlap check on front-face rectangles
    bad = 0
    R = dev.rects
    for i in range(len(R)):
        for j in range(i+1, len(R)):
            a, b = R[i], R[j]
            if abs(a[1]-b[1]) < (a[3]+b[3])/2 and abs(a[2]-b[2]) < (a[4]+b[4])/2: bad += 1; print("   OVERLAP", a[0], b[0])
    print(f"   front-face rectangles: {len(R)}, overlaps: {bad}")
