# Vertical Infrastructure Kit (Godot 4.x)

Satuan meter, Y-up, maju = -Z, grid 1x1 m. Floor-to-floor = 4.0 m. Convention: cell 1x1 berpusat di (n+0.5, n+0.5).
Impor: taruh folder di `res://`, Godot otomatis mengimpor `.glb`. Di Import dock: Generate Collision/Shapes sesuai kebutuhan.

| Aset | Ukuran (x,y,z) m | Pivot | Tris |
|---|---|---|---|
| Stair_Main | 0.9 x 2.0 x 3.0 (10 riser 0.20 / tread 0.30, ±33.7°) | titik awal bawah, tengah; naik ke -Z | 240 |
| Stair_Side | 0.05 x 2.0 x 3.0 (stringer) | sama dgn Stair_Main; pasang di x = ±0.475 | 88 |
| Stair_Landing | 1.0 x 2.0 x 1.0 (top plat di y=2.0, kaki ke lantai) | bawah-tengah | 108 |
| Stair_Railing | 0.05 x ~2.8 x 3.0 (handrail 0.9 di atas tread) | basis stair; pasang di x = ±0.475 | 60 |
| Elevator_Shaft | 3.0 x 4.0 x 3.0 (dinding 0.2, interior 2.6x2.6, bukaan 1.6x2.2 di sisi +Z) | bawah-tengah | 96 |
| Elevator_Cabin | 2.0 x 2.4 x 2.4 (bukaan 1.4x2.1) | bawah-tengah | 108 |
| Elevator_Door | 2 daun 0.69 x 2.06 (node Door_Left/Door_Right) | tiap daun: tengah-bawah; geser sumbu X | 24 |
| Elevator_Frame | 1.6 x 2.2 x 0.2 | bawah-tengah | 36 |
| Elevator_Control | 0.22 x 0.5 x 0.055 | bawah-tengah, belakang (menghadap +Z) | 96 |
| Utility_Riser | 1.0 x 4.0 x 1.0 (bukaan depan 0.7 x 3.6, ladder rack di dalam, atas/bawah terbuka) | bawah-tengah | 204 |
| Floor_Threshold | 1.0 x 0.035 x 0.3 | bawah-tengah | 36 |
| Guard_Rail | 1.0 x 1.1 x 0.12 | bawah-tengah | 84 |
| Safety_Barrier | 1.0 x 1.0 x 0.4 | bawah-tengah | 72 |

## Aturan rakit
- Stair 4 m: flight 1 di (0.5,0,0) -> 2 landing di (0.5,0,-3.5) & (1.5,0,-3.5) -> flight 2 di (1.5,2.0,-3.0) rotasi Y 180°. Bukaan lantai atas: x 0..2, z -4..0.
- Cabin: posisi y = y_lantai - 0.08 (`stop_offset_y` di extras) agar lantai cabin rata dengan sill.
- Frame & pintu hoistway di z = shaft_z + 1.4; pintu cabin di z = cabin_z + 1.17. Pintu geser 0.7 m ke dalam kantong dinding (`slide_open_x` di extras).
- Shaft modular: tumpuk per 4.0 m. Riser juga ditumpuk per 4.0 m.
- Elevator_Control: pasang di y=0.9, putar Y -90° untuk dinding kanan cabin.

## File
- `assets/*.glb` satu per aset, `Kit_Sheet.glb` semua aset berjajar, `Assembly_Test.glb` uji rakit (node `REF_Slabs` hanya referensi, bukan bagian kit).
- `build_kit.py` generator (ubah konstanta di atas lalu jalankan ulang).
