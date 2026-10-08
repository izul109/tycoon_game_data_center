# Cooling family - spec (Godot 4.7.2)

Fictional, brandless, zone-based gameplay objects. Meters, Y-up. **+Z is the front** of every unit. 2 surfaces per asset
(`M_Cooling` shared atlas `cooling_atlas.png`, `M_Status` LEDs), 60-114 triangles each.

| Asset | Size (W x H x D) | Pivot | Anchors (Node3D children) |
|---|---|---|---|
| Cooling_Floor | 0.80 x 1.90 x 0.90 (+0.045 rear power box, handle +0.014) | bottom-center; fits one 1x1 m cell | Intake_01 (front upper grille, +Z), Outlet_01 (top, +Y), Control_Panel, Service_Panel, Power_Connection (rear, -Z) |
| Cooling_Compact | 0.50 x 0.90 x 0.60 | bottom-center | same five anchors |
| Cooling_Wall | 0.90 x 0.30 x 0.25 | center of the back mounting plane, protrudes +Z | Intake_01 (top, +Y), Outlet_01 (bottom, -Y), Bracket_L, Bracket_R |
| Cooling_Ceiling | 0.96 x 0.96, hangs 0.26 below the ceiling plane, hanger stubs 0.10 above | center of the mounting plane (y=0), hangs toward -Y | Intake_01 (underside center), Outlet_01 / Outlet_02 (underside strips at z=+/-0.375), all -Y |
| Cooling_ControlPanel | 0.20 x 0.14 x 0.031 | center of the back mounting plane, protrudes +Z | Display, Button_01..Button_04 |

- Each anchor's local +Z axis is its air/interaction direction (also stored as `direction` in node metadata, with `kind`).
- Gameplay hooks: use the anchors to define cooling-zone coverage, link a control panel to a unit, or attach power later. No airflow geometry, particles, cables or pipes are included.
- The control panel has a real display area (static "22.5C" graphic baked in the atlas; swap the atlas region for dynamic UI) and 4 raised buttons.
- Mounting: wall unit has two rear brackets; ceiling unit has a flange plus 4 hanger stubs.
- LEDs (0 status, 1 alarm, 2 power): assign `cooling_status_led.gdshader` to surface 1 and set the instance uniform `led_word` (2 bits per LED: 0 off, 1 green, 2 amber blink, 3 red). Without the shader they show static green.
  `inst.set_instance_shader_parameter("led_word", state0 | (state1 << 2) | (state2 << 4))`
- Performance: all instances of one asset share mesh + materials; the atlas is shared by all five assets (import once if you externalize it).

## Limitations
- Not opened in Godot here; verify the LED shader (instance `uint` uniform) on first import.
- Vents and grilles are 0.5-1 mm decals (no real openings); no collision shapes.
- The preview PNG is a rough painter's-algorithm render, so small parts (handle, brackets) may look misplaced there.
