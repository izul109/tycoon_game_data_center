# Stratum storage family (fictional) — Godot 4.x import notes

Format: glTF binary (.glb), metres, +Y up, **front faces +Z**, pivot = bottom-centre of the footprint.
Rack faceplate 482.6 mm (19"), chassis 435 mm, height = U × 44.45 mm − 0.79 mm (EIA clearance), so stacking at exact 44.45 mm pitch is correct.

| Node (file) | Form | Bays | Size W×H×D (mm) | Tris | Accent |
|---|---|---|---|---|---|
| Storage_Server | 2U | 12 × 3.5" front | 482.6 × 88.1 × 720 | ~900 | blue |
| Storage_DiskShelf_2U | 2U | 24 × 2.5" front | 482.6 × 88.1 × 560 | ~1030 | bronze |
| Storage_DiskShelf_4U | 4U | 60 slim sleds front | 482.6 × 177.1 × 880 | ~1940 | bronze |
| Storage_NAS_Rack | 2U | 8 × 3.5" + LCD/nav strip | 482.6 × 88.1 × 540 | ~630 | teal |
| Storage_NAS_Desktop | desktop | 4 vertical trays | 170 × 205 × 235 | ~360 | teal |

Rear connectors/handles protrude a few mm beyond the stated depth.

## Node layout (same in every file)
- `Body` – all static geometry, one surface, **vertex colours** (material `<Name>_Body`). Godot turns on "vertex colour as albedo" automatically on import; if it looks white, enable it on the material.
- `LED_Status` – front system LEDs (power / health / network / locate…). Unlit, vertex-coloured.
- `LED_DriveActivity` – one quad per bay; UV.x = (bay_index + 0.5) / bay_count, so a shader can light bays individually.
- `LED_Rear` – link, PSU and IO-module LEDs.
- `Display` (NAS_Rack only) – dim LCD panel.
Each LED group has its own material, so per-instance state changes via `material_override` or a shader parameter.
Root node metadata (`extras`) holds rack_units, bay_count, size_mm, role.

## Draw-call cost
Each asset is 4–5 meshes with one surface each (Body plus LED groups), so 4–5 draw calls per instance. If you place hundreds, merge the LED meshes or use MultiMesh.

No logos, no cables, no rack, no drive internals.
