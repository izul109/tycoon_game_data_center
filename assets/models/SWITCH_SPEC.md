# Switch family — spec (Godot 4.7.2)

Fictional, brandless 1U managed switches. Units m, Y-up, **front (ports) faces +Z**. Pivot = bottom-center (x=0, y=0, z=mid-depth).

| | Switch_24P_1U | Switch_48P_1U |
|---|---|---|
| RJ45-style ports | 24 (`Port_01`..`Port_24`) | 48 (`Port_01`..`Port_48`) |
| Uplinks (accent-colored cages) | 4 (`Uplink_01`..`Uplink_04`) | 4 (`Uplink_01`..`Uplink_04`) |
| Console | `Console` | `Console` |
| Triangles / vertices | 654 / 1308 | 998 / 1996 |
| Surfaces (draw calls) | 2 | 2 |
| Accent | teal | amber |

Size: 482.6 mm (19" panel incl. ears) x 43.6 mm chassis (+0.5 mm top-vent decals) x 400 mm deep. Fits a 44.45 mm 1U slot.

## Port association
- Each port is an empty `Node3D` child of the root, named as above, placed at the center of the port opening on the front plane (z = 0.200). Cable ends should attach at these nodes; +Z is the outward direction.
- Numbering: top row odd, bottom row even (Port_01 above Port_02). Uplinks: 01 top-left, 02 bottom-left, 03 top-right, 04 bottom-right. Anchors are at least 15 mm apart.
- Node metadata (`extras`): `kind` (rj45/uplink/console) and `led_index`.
- Ports are real 3 mm recesses (dark interior; accent interior for uplinks), so a cable end can visibly sit in them.

## LEDs and numbering
- One LED per port, plus 3 system LEDs (PWR/SYS/FAN, indices 52/53/54). LED index: Port_NN = NN-1, Uplink_NN = 47+NN.
- All LEDs are one surface (`M_LED`, surface 1). Fallback look without a shader: static green.
- Per-instance status: assign `switch_led_status.gdshader` to surface 1 and set the 4 instance uniforms:
```gdscript
func set_led(inst: MeshInstance3D, idx: int, state: int) -> void:  # 0 off,1 link,2 activity,3 fault
    var key := "led_w%d" % (idx >> 4)
    var v: int = inst.get_instance_shader_parameter(key)
    var sh := (idx & 15) * 2
    inst.set_instance_shader_parameter(key, (v & ~(3 << sh)) | (state << sh))
```
(Assign the shader once with `inst.set_surface_override_material(1, led_material)`; all instances share it.)
- Port numbers (1-48, U1-U4) are baked in the shared 256x256 atlas (`switch_atlas.png`), which also holds all flat colors, so surface 0 is a single material.

## Performance notes
- All switch instances share one mesh + one material per surface; 2 draw calls each, ~1000 tris max.
- Port anchor nodes (53 per 48-port) cost nothing at render time; strip them on far/unselected instances, or use the table in this spec instead.
- Ventilation: side slots, top slots, front grille (24-port), rear fan grilles and PSU bays are low-cost decals.

## Limitations
- Not opened in Godot here; the LED shader (instance uniform `uint`) is untested - verify on first import.
- No collision shape, no rack, no cables, no emissive textures; labels are tiny (about 3 mm digits) and only readable at close range.
