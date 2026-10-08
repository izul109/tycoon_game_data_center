# ISP boundary hardware – Spesifikasi

Satuan meter, Y-up, glTF 2.0. Satu file GLB per perangkat. **Origin = tengah-bawah footprint** (kaki karet di y=0).
**Depan = +Z** (LED status), **belakang = -Z** (semua port + power). Tidak ada kabel, router, atau firewall; tanpa logo/teks.

| File / root node | W × H × D (mm) | Port (node anchor) | LED node | Body |
|---|---|---|---|---|
| `ISP_Modem` | 180 × 45 × 130 | `ISP_IN` (coax F), `LAN` (RJ45), `Power_In` (DC barrel) | PWR, ISP, LAN | 228 tri |
| `ISP_InternetGateway` | 300 × 50 × 220 | `WAN`, `LAN`, `MGMT` (RJ45), `Power_In` (IEC C14) | PWR, WAN, LAN, MGMT | 328 tri |
| `ISP_FiberGateway` | 200 × 60 × 150 (+4 hatch) | `ISP_IN` (SC/APC + dust cap hijau), `LAN` (RJ45), `Power_In` (DC) | PWR, ISP, LAN | 288 tri |
| `ISP_CPE` | 120 × 32 × 90 | `WAN`, `LAN` (RJ45), `Power_In` (DC) | PWR, WAN, LAN | 224 tri |

Warna strip label di atas port (tanpa teks): ISP_IN oranye, WAN biru, LAN hijau, MGMT ungu.

## Struktur node
- Root = mesh body gabungan (5 surface: body, metal, dark, trim vertex-color, vent alpha-scissor) → 1 mesh/perangkat untuk instancing murah.
- **Port anchor**: node kosong bernama persis `ISP_IN` / `WAN` / `LAN` / `MGMT` / `Power_In`, di bidang muka port. **+Z lokal = arah keluar port** (arah kabel). Metadata (`type`, `role`) ada di `extras` → Godot meta `extras`.
- **LED**: node mesh `LED_PWR`, `LED_ISP`, `LED_WAN`, `LED_LAN`, `LED_MGMT` (quad 2 segitiga, mesh dipakai bersama). Ganti material lewat `set_surface_override_material(0, …)`; `ISPLed.gd` sudah menyediakan `set_led(device, "LED_WAN", ISPLed.State.AMBER)` dan `get_port(device, "LAN")`.
- Default LED: PWR hijau, ISP/WAN biru, LAN hijau, MGMT amber.

## Catatan performa & penggunaan
- Semua perangkat muat di `Rack_Shelf` (nampan 440 mm lebar × 840 mm dalam); gateway (300 mm) hanya muat satu per baris shelf; modem, fiber gateway, dan CPE yang lebih kecil bisa berdampingan.
- Ventilasi memakai decal alpha-scissor (tekstur 32×16), bukan geometri. Tidak ada tekstur lain.
- Banyak instance: import sekali, simpan sebagai scene, lalu instansiasi; material bisa di-*extract* agar dibagi lintas file.
- Mengubah dimensi/port: edit `build_isp_hardware.py`, jalankan `python3 build_isp_hardware.py <folder>` (tanpa dependensi).
