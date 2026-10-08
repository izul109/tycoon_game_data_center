# Meridian client family (fictional) — Godot 4.x import notes

Format: glTF binary (.glb), metres, +Y up, **front faces +Z**. Light office grey + one muted indigo accent (power ring / accent lines).
No logos, no cables, no characters. Companion to the dark "Stratum" storage family.

| Node / file | Size W×H×D (mm) | Pivot | Tris | Ethernet markers |
|---|---|---|---|---|
| Client_Desktop | 170 × 350 × 330 | bottom-centre | ~450 | 1 |
| Client_SFF | 230 × 70 × 230 | bottom-centre | ~300 | 1 |
| Client_Workstation | 220 × 470 × 500 | bottom-centre | ~630 | 2 (1G + 10G) |
| Client_Laptop (lid open 105°) | 320 × 215 × 220 base | bottom-centre of base | ~270 | 1 (left side) |
| Client_Monitor (24") | 544 × 425 × 200 | **base-centre** | ~115 | 0 |
| Client_Keyboard | 450 × 22 × 140 | bottom-centre | ~225 | 0 |
| Client_Mouse | 62 × 38 × 110 | bottom-centre | ~40 | 0 |
| Client_Printer | 420 × 296 × 408 | bottom-centre | ~265 | 1 |

## Ethernet connection points
Each Ethernet port has an empty child node `NetPort_Eth0` (and `NetPort_Eth1` on the workstation).
- Node origin = centre of the RJ45 plug face; local **+Z points out of the device** (rear ports face world −Z, laptop port faces −X).
- Node `extras` (Godot metadata): `port_type`, `port_index`, `speed`, `outward`, `owner`.
- Attach your logical connection point / cable anchor to these nodes. Positions are in the asset's own space.

## Meshes
- `Body` – static geometry, vertex colours (material `<Name>_Body`).
- `LED_Status` – front/rear LEDs (unlit, vertex-coloured; includes RJ45 link/activity LEDs).
- `Screen` (monitor, laptop) – single quad, **UV 0..1**, dark unlit base colour; assign your own texture/SubViewport.
- `Display` (printer) – small status LCD quad.
- `Stand` (monitor) – hide it to mount the head on a VESA arm; the 100×100 VESA pattern is on the rear hump.
Laptop depth including the open lid is ~0.28 m (lid leans back behind the base).
