import json, struct, sys, os, math
D = sys.argv[1]
fails = 0; lines = []
def P(s=""): lines.append(s); print(s)
def load(p):
    b = open(p, "rb").read()
    assert b[:4] == b"glTF" and struct.unpack_from("<I", b, 8)[0] == len(b)
    jl = struct.unpack_from("<I", b, 12)[0]; j = json.loads(b[20:20+jl]); return j, b[28+jl:]
def acc(j, bn, i):
    a = j["accessors"][i]; v = j["bufferViews"][a["bufferView"]]; o = v["byteOffset"]; n = a["count"]
    if a["type"] == "VEC3": return [struct.unpack_from("<3f", bn, o+12*k) for k in range(n)]
    if a["type"] == "VEC2": return [struct.unpack_from("<2f", bn, o+8*k) for k in range(n)]
    return [struct.unpack_from("<H", bn, o+2*k)[0] for k in range(n)]
for ports in (24, 48):
    name = f"Switch_{ports}P_1U"; j, bn = load(os.path.join(D, name + ".glb")); iss = []
    root = j["nodes"][0]
    if root["name"] != name: iss.append("root name")
    allp = []; tris = 0; deg = 0; bad = 0
    for p in j["meshes"][0]["primitives"]:
        pos = acc(j, bn, p["attributes"]["POSITION"]); nor = acc(j, bn, p["attributes"]["NORMAL"]); idx = acc(j, bn, p["indices"])
        allp += pos
        for k in range(0, len(idx), 3):
            a, b, c = (pos[idx[k+q]] for q in range(3)); tris += 1
            e1 = [b[i]-a[i] for i in range(3)]; e2 = [c[i]-a[i] for i in range(3)]
            cr = (e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2], e1[0]*e2[1]-e1[1]*e2[0])
            if math.sqrt(sum(x*x for x in cr)) < 1e-12: deg += 1
            n = nor[idx[k]]
            if sum(cr[i]*n[i] for i in range(3)) <= 0: bad += 1
    lo = [min(q[i] for q in allp) for i in range(3)]; hi = [max(q[i] for q in allp) for i in range(3)]
    # body bounds exclude decal offsets (<=1 mm): check with tolerance
    if abs(hi[0]-0.2413) > 1e-3 or abs(lo[0]+0.2413) > 1e-3: iss.append(f"width {lo[0]:.4f}..{hi[0]:.4f}")
    if abs(lo[1]) > 1e-6 or abs(hi[1]-0.0436) > 1e-3: iss.append(f"height {lo[1]:.4f}..{hi[1]:.4f}")
    if abs(hi[2]-0.2005) > 1e-4 or abs(lo[2]+0.201) > 1e-4: iss.append(f"depth {lo[2]:.4f}..{hi[2]:.4f}")
    if hi[1] - lo[1] > 0.04445: iss.append("exceeds 1U")
    if abs((hi[0]+lo[0])/2) > 1e-6: iss.append("not centered in X")
    names = [n["name"] for n in j["nodes"][1:]]
    exp = [f"Port_{i:02d}" for i in range(1, ports+1)] + [f"Uplink_{i:02d}" for i in range(1, 5)] + ["Console"]
    if sorted(names) != sorted(exp): iss.append("anchor names mismatch")
    if len(set(names)) != len(names): iss.append("duplicate names")
    for n in j["nodes"][1:]:
        t = n["translation"]
        if not (abs(t[2]-0.2) < 1e-6 and abs(t[0]) < 0.22 and 0 < t[1] < 0.0436): iss.append(f"anchor out of range {n['name']}")
    # anchors pairwise >= 13.5 mm apart (no ambiguity when picking ports)
    pts = [n["translation"] for n in j["nodes"][1:]]
    md = min(math.dist(a, b) for i, a in enumerate(pts) for b in pts[i+1:])
    if md < 0.0149: iss.append(f"anchors too close {md*1000:.1f} mm")
    leds = j["nodes"][0]["extras"]["leds"]
    if len(set(leds)) != len(leds) or max(leds) >= 64: iss.append("LED index clash")
    nprim = len(j["meshes"][0]["primitives"])
    if nprim != 2: iss.append("surface count")
    if deg: iss.append(f"{deg} degenerate"); 
    if bad: iss.append(f"{bad} bad winding")
    ok = "PASS" if not iss else "FAIL: " + "; ".join(iss); fails += bool(iss)
    P(f"{name}: {tris} tris, {len(allp)} verts, {nprim} surfaces, {len(j['nodes'])-1} anchors, {len(leds)} LEDs, min anchor spacing {md*1000:.1f} mm, "
      f"size {(hi[0]-lo[0])*1000:.1f} x {(hi[1]-lo[1])*1000:.1f} x {(hi[2]-lo[2])*1000:.1f} mm  {ok}")
P("RESULT: " + ("ALL CHECKS PASSED" if not fails else f"{fails} FAILURE(S)"))
open(os.path.join(D, "..", "switch_validation_report.txt"), "w").write("\n".join(lines) + "\n")
