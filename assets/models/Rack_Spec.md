# Rack_42U – Spesifikasi

Satuan meter, Y-up, glTF 2.0. **Depan rak = +Z**, kanan (dari depan) = +X. Origin rak = tengah-bawah footprint.

## Dimensi kunci
| Item | Nilai |
|---|---|
| 1U | 0.04445 m |
| Ruang U | y 0.1500 → 2.0169 m (1.8669 m = 42U) |
| Tinggi total | 2.090 m |
| Lebar x kedalaman rangka | 0.800 × 1.100 m (+ pintu ±0.03) |
| Bukaan antar rel | 0.45085 m (17,75") |
| Lebar panel perangkat | 0.4826 m (19") |
| Pusat lubang | x = ±0.23255 m, pola EIA-310 (6,35 / 22,225 / 38,1 mm dari dasar U) |
| Bidang rel depan / belakang | z = +0.430 / -0.430 (jarak 0.860 m) |

U n bawah = `0.150 + (n-1)*0.04445`. Tinggi panel 1U = 43,66 mm (celah 0,79 mm).

## Konvensi pivot
- **Part tetap** (Rack_42U, Base, Foot, Top, SidePanel L/R, Rail x4): transform identity, geometri di ruang rak. Rack_Foot = 4 kaki dalam satu mesh.
- **Modul** (Blank 1/2/4U, Shelf, CableManager_Horizontal): origin = tengah-bawah U terbawah, di bidang rel depan (z=0 lokal), badan ke -Z.
- **Pintu**: origin = poros engsel di tepi bawah; badan ke +X lokal, luar = +Z lokal. RearDoor sudah diputar 180° Y.
- **CableManager_Vertical (+ _R)**: origin = tengah-X duct, dasar U1, ujung depan; badan ke -Z sedalam 0.20 m. Diletakkan di sisi belakang.
- Penanda: `Rack_Mount_Front`, `Rack_Mount_Rear` (titik acuan U1).
- `Rack_Collision-convcolonly`: dibuat Godot jadi StaticBody3D konveks (hapus jika tidak perlu).

## Catatan
- Blank, rak, shelf, dan horizontal manager di scene hanyalah contoh penempatan (U1, U35, U36–42); hapus/ganti dengan hardware.
- Lubang rel adalah tekstur (bukan geometri); satu tile = tepat 1U sehingga garis batas U selalu sejajar.
- Pintu mesh memakai alpha-scissor (material `M_Mesh`, double-sided).
- Total 2.290 segitiga, 6 material, 2 tekstur kecil (32×128 dan 32×32). Untuk banyak rak: import sekali, lalu instansiasi scene (atau MultiMesh).
- Regenerasi: `python3 build_rack.py <folder_output>` (tanpa dependensi).
