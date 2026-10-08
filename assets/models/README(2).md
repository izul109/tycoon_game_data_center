# CableTray Kit (Godot 4.x)

Hanya infrastruktur fisik, tanpa mesh kabel. Satuan meter, Y-up. Arah jalur piece = -Z (maju Godot).
Penampang tray: lebar 0,30 x tinggi 0,10 m (rel 0,02; rung/alas 0,012), tipe ladder terbuka.
Grid 1 m: titik sambung (connection point) berada di tengah sisi sel 1x1 m. Jarak rung tetap 0,25 m, termasuk melewati sambungan.

## Pivot / origin
Origin = garis tengah (centerline) penampang di titik sambung masuk (`Conn_In`). Jalur procedural cukup mengikuti polyline centerline.
Tiap piece punya node kosong `Conn_*` dengan extras `travel_dir` (arah jalur keluar/masuk) untuk snapping.

| Aset | Mounting / orientasi | Panjang / sel | Conn node | Tris |
|---|---|---|---|---|
| CableTray_Ceiling_Straight | terbuka ke atas (+Y), ladder | 1 m ke -Z | Conn_In, Conn_Out | 56 |
| CableTray_Wall_Straight | menempel dinding: alas di x=-0.05, terbuka ke +X, lebar vertikal, kuping pengikat | 1 m ke -Z | Conn_In, Conn_Out | 96 |
| CableTray_Floor_Straight | terbuka ke atas, alas solid (trough) | 1 m ke -Z | Conn_In, Conn_Out | 32 |
| CableTray_Vertical | alas di x=-0.05, terbuka ke +X | 1 m ke +Y | Conn_In, Conn_Out | 56 |
| CableTray_Corner90 | datar (bisa diputar ke dinding), belok kiri | sel 1x1 | In (0,0,0), Out (-0.5,0,-0.5) arah -X | 100 |
| CableTray_T | datar, input dari kaki T | sel 1x1 | In, Out_L (-0.5,0,-0.5), Out_R (0.5,0,-0.5) | 120 |
| CableTray_Cross | datar | sel 1x1 | In, Out_L, Out_R, Out_F (0,0,-1) | 188 |
| CableTray_Transition | siku vertikal -> horizontal di bidang dinding | sel 1x1 | In (0,0,0) naik +Y, Out (0,0.5,-0.5) arah -Z | 112 |
| CableTray_Support | hanger trapeze, tali di bawah tray, batang ke plafon (`ceiling_offset_y` = 0.55) | di mana saja sepanjang tray | - | 60 |
| CableTray_Cover | tutup 1 m, di atas straight (h 0.03..0.06) | 1 m ke -Z | - | 32 |
| CableTray_End | tutup ujung, +Z menghadap tray, pelat meluas ke -Z | - | - | 12 |
| CablePass_Floor | kerb 5 cm + flens, bukaan 0,34 x 0,34 | origin = pusat bukaan di permukaan lantai | - | 96 |
| CablePass_Wall | bukaan 0,34 x 0,14, selongsong tebal dinding 0,2 | origin = pusat bukaan di muka dinding sisi ruang, dinding ke -Z | - | 144 |
| CablePass_Ceiling | flens + kerah turun 4 cm, bukaan 0,34 x 0,34 | origin = pusat bukaan di permukaan bawah plafon | - | 96 |

Total kit: 1.188 segitiga. 1-3 material per aset (M_Tray_Steel, M_Tray_Dark, M_Tray_Cover) untuk memudahkan MultiMesh.

## Aturan pakai
- Belok kanan: pakai Corner90 dengan origin di titik Out dan putar 180° (jalur dibalik); belok kiri: langsung.
- Corner90/T/Cross dipakai juga di lantai dan dinding dengan diputar; Transition khusus bidang dinding.
- End cap: putar agar +Z lokal menghadap tray; Cover: satu per straight 1 m.
- Floor/ceiling pass-through dilalui CableTray_Vertical (footprint 0,3 x 0,1 muat di bukaan).

## File
`assets/*.glb`, `Kit_Sheet.glb`, `Assembly_Test.glb` (uji rakit; semua sambungan dicek selisih 0,000 m), `Preview_*.png`, `Detail_*.png`, `build_trays.py`.
