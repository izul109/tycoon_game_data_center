# Fictional cable-management family (same visual language as the server family)

Files: `PatchPanel_24.glb`, `PatchPanel_48.glb`, `CableManager_1U_Horizontal.glb`, `CableManager_Vertical.glb`,
`BrushPanel_1U.glb`, `BlankingPanel_1U_Passthrough.glb`.
Regenerate: `python3 generate_cable_mgmt.py` (numpy + Pillow). Verify and render previews: `python3 validate_cable_mgmt.py`.

## Conventions (identical to the servers)
meters, +Y up, **front = +Z**, origin bottom-center of the footprint. Shared SRV_* materials and teal accent edge.
Anchors are empty nodes; local +Z = outward face normal (a cable would travel along local -Z).

| Asset | W x H x D (mm) | Tris | Anchors |
|---|---|---|---|
| PatchPanel_24 | 482.6 x 44.45 (1U) x 87 | 508 | 49 |
| PatchPanel_48 | 482.6 x 88.90 (2U, two rows of 24) x 87 | 974 | 97 |
| CableManager_1U_Horizontal | 482.6 x 44.45 x 81 | 116 | 11 |
| CableManager_Vertical | 150 x 1866.9 (42U) x 251 | 584 | 44 |
| BrushPanel_1U | 482.6 x 44.45 x 31 | 130 | 6 |
| BlankingPanel_1U_Passthrough | 482.6 x 44.45 x 16 | 106 | 2 |

## Patch panels
- Ports on a 17.2 mm pitch, groups of 6 split by a thin line; numbers sit under each port.
  48-port numbering is row-major, top row 01-24, bottom row 25-48.
- Port numbers come from ONE small embedded texture atlas (1024x384 PNG, 7-segment digits, no font).
  Each label is a 2-triangle quad; this is the only textured material in the family.
- Anchors: `Port_01..Port_24/48` (front opening, +Z) and `Term_01..` (rear termination slot, -Z).
- Rear: tray, 6-port termination strips with a slot per port, and a cable support bar on two arms (no cable geometry).

## Cable managers
- Horizontal 1U: 8 finger openings (40 mm each) into a dark channel, open at both ends.
  Anchors `Guide_01..08` (front openings), `Duct_End_L/R` (side entries, normal -X / +X).
- Vertical: 150 mm wide, 250 mm deep, 42U tall; slotted finger walls on BOTH sides (21 slots of 2U each),
  open front with retaining lips, base plate, open top. Anchors `Guide_Left_01..21`, `Guide_Right_01..21`
  (index 1 = U1-2, bottom first; normals -X/+X), `Channel_Top` (+Y), `Anchor_Align_Front`.
- Brush panel: 380 x 20 mm opening, two dark brush strips with a central passage, shallow tray. Anchors `Pass_01..05`.
- Blanking panel: 100 x 26 mm grommeted pass-through (open hole by design). Anchor `Pass_01`.

## Placement
- Every rack-mounted piece has `Anchor_Mount` at the ear-face plane, bottom edge, centered (+Z). Put it on the rack's
  front mounting plane at the U boundary you want. The same plane is in the root node extras as `mount_plane_z`.
- Server family mounting plane (for reference): z = D/2 - 0.004 (bezel/ear face), D = 0.700 / 0.740 / 0.780.
- Vertical manager: y=0 is the floor-side bottom; set its Y so the bottom equals the rack's U1 bottom (or the rack base,
  your choice) and `Anchor_Align_Front` on the rack front plane. Width 150 mm sits beside a 600 mm rack.

## Instancing
4-9 draw surfaces per asset, 4-6 shared materials, 94-974 triangles. Use MultiMeshInstance3D per model.
