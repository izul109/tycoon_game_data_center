# RX Series — keluarga router fiktif (Godot 4.x)

Satuan meter, Y-up. Semua port menghadap +Z (depan); kabel keluar searah +Z (`cable_dir` di extras). Pivot: bawah-tengah.
Tanpa logo/merek. Bahasa desain sama di ketiganya: faceplate gelap, garis aksen teal, port RJ45 berframe logam, SFP+ berframe teal,
strip warna per grup (WAN oranye, LAN hijau, UPLINK biru, MGMT abu terang), LED PWR hijau / SYS biru / ALM amber.

| Model | Node root | Ukuran (x,y,z) m | Tris |
|---|---|---|---|
| RX-100 Compact (desktop / wall-mount) | Router_Compact | 0.27 x 0.0425 x 0.1625 (+ tab dinding) | 564 |
| RX-500 Rack 1U | Router_Rack | 0.4826 x 0.04445 x ~0.31 (faceplate 19", body 0.44, kedalaman 0.30) | 944 |
| RX-900 Modular 2U | Router_Modular | 0.4826 x 0.0889 x ~0.39 (4 bay) | 1350 |

## Port anchor (node kosong, +Z = arah keluar kabel, posisi di muka port)
| Anchor | Compact | Rack | Modular |
|---|---|---|---|
| WAN_01 / WAN_02 | WAN_01 | ya / ya | Module_WAN |
| LAN_01..LAN_04 | ya | ya | Module_LAN (2x2) |
| UPLINK_01 / UPLINK_02 (SFP+ 10G) | - | ya | Module_UPLINK |
| MGMT | - | ya | panel supervisor |
Anchor ada di `Ports/` (anchor modul ada di dalam node modulnya, jadi ikut bergerak saat modul ditarik).
Ekstra non-jaringan: `Rear/PWR_IN` (Compact, Rack), `Rear/PWR_IN_A`, `PWR_IN_B` (Modular), untuk kabel daya di masa depan.

## LED
Tiap port punya `LED_<port>` (mesh terpisah, bisa di-override materialnya per instance: M_LED_Green/Amber/Blue emissive), plus `LED_PWR`, `LED_SYS`, `LED_ALM`.

## Modular
`Bays/Bay_1..4` -> `Module_WAN`, `Module_LAN`, `Module_UPLINK`, `Module_BLANK`. Tarik modul keluar dengan menggeser node modul
sepanjang +Z hingga `pull_distance` = 0.10 m (extras); rongga bay kosong terlihat di belakangnya. Slot bisa diisi ulang dengan modul lain.

## Rack
Lubang telinga mengikuti pitch EIA-310 (1U: 6.35 / 38.1 mm; 2U: ditambah 50.8 / 82.55 mm). Tumpuk per 0.04445 m.

## File
`assets/*.glb`, `Router_Family_Sheet.glb`, `Preview_*.png`, `Front_*.png`, `build_routers.py` (generator).
