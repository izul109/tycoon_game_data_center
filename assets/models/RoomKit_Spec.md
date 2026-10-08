# Data-center room kit – Spesifikasi

Satuan meter, Y-up, glTF 2.0. Satu GLB per aset. **Grid = 1 m.** Sisi depan / sisi terbuka = **+Z**.
Rotasi hanya kelipatan 90° pada sumbu Y (Godot: `rotation.y = +90°` memetakan +Z → +X).
Slab lantai = y 0. **Permukaan raised floor = y 0,30 m.**

| Aset | Ukuran (m) | Tri | Pivot |
|---|---|---|---|
| `Floor_Panel_1m` | 1 × 1 (permukaan y=0,30) | 2 | tengah-bawah sel, level slab |
| `Floor_Edge_1m` | 1 × 1, sisi terbuka **+Z** | 10 | idem |
| `Floor_Corner_1m` | 1 × 1, sisi terbuka **+Z dan +X** | 20 | idem |
| `Floor_AccessPanel_1m` | 1 × 1, insert + frame + 2 lift cup | 130 | idem |
| `WallPanel_Technical` | 1 × 3 × 0,10 | 94 | tengah muka belakang (mounting); tempatkan di y=1,5 |
| `WallPanel_Acoustic` | 1 × 2 × 0,07 | 80 | idem; y = tinggi pasang + 1,0 |
| `Staging_Platform` | dek 2 × 1 × 0,20, ramp 0,75 m di +Z | 114 | tengah-bawah dek |
| `Cart_Small` | 0,55 × 0,90 × 0,92 (dek 0,73) | 280 | tengah-bawah wheelbase; handle di -Z |
| `Trolley_Server` | 0,73 × 1,02 × 1,55; platform bersih 0,58 × 0,90 | 322 | tengah-bawah base; tiang di -Z |
| `Workbench_Maintenance` | 1,8 × 0,76 × 0,90 (+riser 1,35) | 154 | tengah-bawah footprint |
| `Cabinet_Tool` | 0,90 × 0,52 × 1,80 | 64 | tengah-bawah; pintu ke +Z |
| `Container_TechWaste` | 0,63 × 0,62 × 0,84 | 122 | tengah-bawah; roda di -Z |

## Lantai (modular, seamless)
- Semua tile tepat 1,000 m; permukaan di y=0,30 (insert access panel 0,5 mm lebih rendah di dalam frame logam = terlihat "bisa diangkat").
- UV dunia-kontinu (satu tile tekstur = satu sel); garis sambungan ada di tekstur, bukan geometri celah → tidak ada retakan.
- Tidak ada pedestal/struktur tersembunyi: tile hanya permukaan atas (hollow by design). Tepi dan sudut menutup sisi dengan trim aluminium + skirt.
- Susunan: `Floor_Edge_1m` rotasi 0°/90°/180°/270° untuk sisi +Z/+X/-Z/-X. `Floor_Corner_1m` rotasi 0°(+Z,+X) / 90°(+X,-Z) / 180°(-Z,-X) / 270°(-X,+Z).

## Troli server
- `Trolley_Platform` adalah child node yang bergeser pada Y lokal (0,20 – 1,35 m, default 0,75). `RoomSpec.set_trolley_height(trolley, y)`.
- Lebar bersih 580 mm / kedalaman 900 mm → muat perangkat rak 19" (482,6 mm) hingga ±800 mm dalam. Strip kuning di tepi depan.

## Collision
Setiap aset punya node `Collision-convcolonly` (box). `Staging_Platform` punya dua: `Collision_Deck-convcolonly` dan `Collision_Ramp-convcolonly` (baji) agar ramp tetap bisa dilalui. Godot mengubahnya jadi StaticBody3D dan membuang mesh-nya.

## Performa
- Tiap aset 1 mesh gabungan, 2–5 surface; tidak ada detail mekanis berlebih. Lantai 2–130 tri per sel.
- Hanya dua tekstur: `floor` 128×128 (sambungan + speckle halus) dan `vent` 32×16 (alpha-scissor). Trim memakai vertex color (satu material untuk banyak warna).
- Untuk lantai besar gunakan `MultiMeshInstance3D` per jenis tile.
- Regenerasi: `python3 build_room_assets.py <folder>` (tanpa dependensi).
