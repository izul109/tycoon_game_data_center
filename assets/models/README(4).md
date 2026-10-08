# Fictional rack server family: Server_1U / Server_2U / Server_4U

Files: `Server_1U.glb`, `Server_2U.glb`, `Server_4U.glb` (binary glTF 2.0).
Regenerate: `python3 generate_servers.py` (needs numpy). Verify + previews: `python3 validate_servers.py`.

## Conventions
| | |
|---|---|
| Units / up | meters, +Y up |
| **Front** | **+Z** (bezel, bays, power button face +Z); right-of-front is +X |
| Origin | bottom-center of the footprint (x=0, y=0 at bottom, z=0 mid-depth) |
| Width | 482.6 mm over the ears (19"), 436.6 mm chassis |
| Height | exactly 44.45 / 88.90 / 177.80 mm (bezel+ears fill the full U; chassis inset 0.8 mm top and bottom so stacked units don't touch) |
| Depth | 700 / 740 / 780 mm (bezel face to rear-most protrusion) |

## Node tree (per file)
```
Server_2U                      (root, extras: rack_units, dims, front_axis ...)
 +- Server_2U_Body             chassis + top service latch   (+ Anchor_Top_ServiceHatch)
 +- Server_2U_Front            bezel, ears, bays, vent, control pod  (+ Anchor_Front_*)
 +- Server_2U_Rear             PSUs, I/O, expansion covers, vent     (+ Anchor_Rear_*)
```
Front/Rear are separate nodes (separate meshes) in the same file, so they can be split out or hidden independently.

## Family contents
| | 1U | 2U | 4U |
|---|---|---|---|
| Drive bays (same carrier module, 4 columns) | 4 (4x1) | 12 (4x3) | 24 (4x6) |
| PSUs / power inlets | 2 | 2 | 4 (2x2) |
| Expansion slot covers | 1 | 2 | 3 |
| Front service port | - | 1 | 1 |
| Triangles | 716 | 998 | 1520 |
| Anchors | 27 | 37 | 54 |

Shared on every size: left intake vent, teal accent bar, right control pod (power button with green halo, 6 LEDs: Health, Fault, Locate, Net1, Net2, Service), ear slots per U, rear exhaust vent.

## Port color / shape key (rear)
Blue RJ45 = data (2) | Amber RJ45 = management (1) | Silver SFP cage = fiber (2) | Green small = service/console (1) | Silver frame + large dark opening = power inlet.

## Materials (10, shared across all three files)
SRV_Chassis, SRV_Bezel, SRV_Metal, SRV_Dark, SRV_Accent, SRV_Port_Data, SRV_Port_Mgmt, SRV_Port_Service, SRV_LED_Green, SRV_LED_Amber (LEDs use emissive). No textures, no UVs, flat-shaded.

## Anchors (empty nodes, no geometry)
Local **+Z = outward face normal**; a plug travels along local -Z. Each has `extras` (`anchor_type`, `side`, `index`, sometimes `row`/`col`/`label`).

Front: `Anchor_Front_PowerButton`, `Anchor_Front_LED_{Health,Fault,Locate,Net1,Net2,Service}`, `Anchor_Front_Bay_01..N` (row-major from top-left), `Anchor_Front_ServicePort` (2U/4U), `Anchor_Front_Vent`, `Anchor_Front_MountEar_{L,R}`.
Rear (numbered left to right as seen from behind): `Anchor_Rear_PSU_nn`, `Anchor_Rear_PowerInlet_nn`, `Anchor_Rear_Net_Data_01/02`, `Anchor_Rear_Net_SFP_01/02`, `Anchor_Rear_Mgmt_01`, `Anchor_Rear_Service_01`, `Anchor_Rear_Expansion_nn`, `Anchor_Rear_Vent`.
Top: `Anchor_Top_ServiceHatch`.

## Instancing notes
- 16-17 draw surfaces per server across 10 shared materials; use `MultiMeshInstance3D` per model for dense rows. Per-instance LED state can't change a shared material, so for per-unit LED states use the anchors (small overlay quads/lights) rather than editing materials.
- The detail is geometric, so there is no texture memory. For distant rows, swap to a box-only proxy via visibility ranges (not generated here).
