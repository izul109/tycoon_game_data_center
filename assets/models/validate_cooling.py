import json, struct, sys, os, math
D = sys.argv[1]; fails = 0; L = []
def P(s=""): L.append(s); print(s)
def load(p):
    b = open(p, "rb").read(); assert b[:4] == b"glTF" and struct.unpack_from("<I", b, 8)[0] == len(b)
    jl = struct.unpack_from("<I", b, 12)[0]; return json.loads(b[20:20+jl]), b[28+jl:]
def acc(j, bn, i):
    a = j["accessors"][i]; v = j["bufferViews"][a["bufferView"]]; o = v["byteOffset"]; n = a["count"]
    if a["type"] == "VEC3": return [struct.unpack_from("<3f", bn, o+12*k) for k in range(n)]
    if a["type"] == "VEC2": return [struct.unpack_from("<2f", bn, o+8*k) for k in range(n)]
    return [struct.unpack_from("<H", bn, o+2*k)[0] for k in range(n)]
def rot(q, v):
    x, y, z, w = q; vx, vy, vz = v
    tx = 2*(y*vz - z*vy); ty = 2*(z*vx - x*vz); tz = 2*(x*vy - y*vx)
    return (vx + w*tx + (y*tz - z*ty), vy + w*ty + (z*tx - x*tz), vz + w*tz + (x*ty - y*tx))
# name: (x[min,max], y[min,max], z[min,max]) in meters, tolerance 1.5 mm (decal lift)
EXP = {
 "Cooling_Floor": ((-.4, .4), (0, 1.9), (-.495, .465)),
 "Cooling_Compact": ((-.25, .25), (0, .9), (-.335, .3)),
 "Cooling_Wall": ((-.45, .45), (-.15, .15), (0, .25)),
 "Cooling_ControlPanel": ((-.1, .1), (-.07, .07), (0, .031)),
 "Cooling_Ceiling": ((-.48, .48), (-.26, .1), (-.48, .48)),
}
P("Asset                   tris verts surf anchors  size (mm)                 result")
for name, (ex, ey, ez) in EXP.items():
    j, bn = load(os.path.join(D, name + ".glb")); iss = []
    pos_all = []; tris = 0; bad = 0; deg = 0
    for p in j["meshes"][0]["primitives"]:
        pos = acc(j, bn, p["attributes"]["POSITION"]); nor = acc(j, bn, p["attributes"]["NORMAL"]); idx = acc(j, bn, p["indices"]); pos_all += pos
        for k in range(0, len(idx), 3):
            a, b, c = (pos[idx[k+q]] for q in range(3)); tris += 1
            e1 = [b[i]-a[i] for i in range(3)]; e2 = [c[i]-a[i] for i in range(3)]
            cr = (e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2], e1[0]*e2[1]-e1[1]*e2[0])
            if math.sqrt(sum(x*x for x in cr)) < 1e-12: deg += 1
            n = nor[idx[k]]
            if sum(cr[i]*n[i] for i in range(3)) <= 0: bad += 1
    lo = [min(q[i] for q in pos_all) for i in range(3)]; hi = [max(q[i] for q in pos_all) for i in range(3)]
    for ax, (a, b) in enumerate((ex, ey, ez)):
        if abs(lo[ax]-a) > 1.6e-3 or abs(hi[ax]-b) > 1.6e-3: iss.append(f"axis{'xyz'[ax]} {lo[ax]:.4f}..{hi[ax]:.4f} != {a}..{b}")
    if name in ("Cooling_Floor", "Cooling_Compact") and abs(lo[1]) > 1e-6: iss.append("floor pivot not at y=0")
    if name in ("Cooling_Wall", "Cooling_ControlPanel") and abs(lo[2]) > 1e-6: iss.append("mount plane not at z=0")
    if name == "Cooling_Ceiling" and abs(hi[0]+lo[0]) > 1e-6: iss.append("ceiling not centered")
    if name in ("Cooling_Floor", "Cooling_Compact") and (max(abs(lo[0]), abs(hi[0])) > .5 or lo[2] < -.5 or hi[2] > .5): iss.append("outside 1x1 cell")
    if len(j["meshes"][0]["primitives"]) != 2: iss.append("surface count")
    if bad: iss.append(f"{bad} bad winding")
    if deg: iss.append(f"{deg} degenerate")
    names = [n["name"] for n in j["nodes"][1:]]
    if len(set(names)) != len(names): iss.append("dup anchors")
    if not any(n.startswith("Intake_01") for n in names) and name != "Cooling_ControlPanel": iss.append("no intake anchor")
    for n in j["nodes"][1:]:
        r = rot(n["rotation"], (0, 0, 1)); d = n["extras"]["direction"]
        if max(abs(r[i]-d[i]) for i in range(3)) > 1e-5: iss.append(f"anchor {n['name']} +Z != direction")
        t = n["translation"]
        if not all(lo[i]-2e-3 <= t[i] <= hi[i]+2e-3 for i in range(3)): iss.append(f"anchor {n['name']} outside bounds")
    leds = j["nodes"][0]["extras"]["leds"]
    if len(set(leds)) != len(leds): iss.append("LED idx clash")
    ok = "PASS" if not iss else "FAIL: " + "; ".join(iss); fails += bool(iss)
    P(f"{name:22s} {tris:4d} {len(pos_all):5d} {len(j['meshes'][0]['primitives']):4d} {len(names):7d}  {(hi[0]-lo[0])*1000:.0f} x {(hi[1]-lo[1])*1000:.0f} x {(hi[2]-lo[2])*1000:.0f}   {ok}")
P("RESULT: " + ("ALL CHECKS PASSED" if not fails else f"{fails} FAILURE(S)"))
open(os.path.join(D, "..", "cooling_validation_report.txt"), "w").write("\n".join(L) + "\n")
