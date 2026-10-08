# Modular Building Kit — Spec (Godot 4.7.2)

Units: meters, Y-up. 17 `.glb` files in `modular_kit/`, each a self-contained scene (root node = asset name).
Regenerate: `python3 build_modular_kit.py modular_kit` · Validate: `python3 validate_kit.py modular_kit`

## Kit constants
| Item | Value |
|---|---|
| Grid | 1.00 m. Walls sit on grid **lines**; floor/ceiling/slab tiles on grid **cells** (origin = cell center) |
| Wall thickness | 0.10 m (all wall pieces, flush plinth band, no protrusions) |
| Wall height | 3.20 m (floor level to underside of next slab) |
| Floor tile | 0.05 m thick, top at y=0.05 |
| Ceiling | place at y=3.00 (underside); tile 0.04 thick |
| Structural slab | 0.30 m thick, place at y=3.20 → **storey pitch 3.50 m** |
| Door clear opening | 0.90 × 2.15 (1 m slot) · double: 1.90 × 2.15 (2 m slot) |
| Window clear opening | 0.90 × 1.10, sill at y=0.95 |

## Pieces
| Asset | Footprint | Origin / pivot | Tris |
|---|---|---|---|
| Floor_1x1 | 1×1×0.05 | bottom-center | 20 |
| Floor_AccessPanel_1x1 | 1×1 (+4 mm hatch) | bottom-center | 72 |
| Wall_Straight_1m | 1.0 × 0.1 × 3.2 | bottom-center, on grid line | 8 |
| Wall_Straight_Short | 0.5 × 0.1 × 3.2 | bottom-center | 8 |
| Wall_End | 0.5 long, trim cap on −X end | bottom-center | 14 |
| Wall_Corner_Inner / _Outer | L, arms 0.5 m toward +X,+Z | on grid vertex | 24 / 20 |
| Door_Frame | 1 m slot | bottom-center | 22 |
| Door_Single | leaf 0.88 × 2.06 × 0.04 | **hinge, bottom** (place at frame x−0.45, rotate Y) | 60 |
| Door_Double | 2 leaves, nodes `Leaf_L`/`Leaf_R` | root bottom-center; leaf nodes are hinge pivots (x=±0.95) | 120 |
| Window_Frame | 1 m slot | bottom-center | 36 |
| Window | 0.92 × 1.12 double-sided quad | same origin as Window_Frame | 2 |
| Ceiling_1x1 | 1×1×0.04 | bottom-center; empty node `Socket_Center` for future lights/trays | 18 |
| Ceiling_Edge | 1 × 0.95 (stops at wall face, wall on −Z side) | bottom-center of cell; rotate in 90° steps | 18 |
| Structural_Floor | 1×1×0.30, edge ribs | bottom-center | 28 |
| Structural_Column | 0.30 shaft, 0.40 plates | floor level (shaft starts at y=0.05) | 28 |
| Wall_Opening | 2 m slot, cased opening | bottom-center | 22 |

## Assembly rules
- Wall runs: corner arm 0.5 + n × `Wall_Straight_1m` + corner arm 0.5 = (n+1) m. Use `Wall_Straight_Short` for half-grid steps, `Wall_End` to close a free end (rotate 180° to cap the +X end).
- Door_Frame / Window_Frame occupy exactly one `Wall_Straight_1m` slot; Wall_Opening occupies two.
- Wall-run pieces have **no end faces** (hidden geometry removed); a run must be terminated with a corner or `Wall_End`.
- Wall tops/bottoms have no faces (they meet slab/floor).

## Known limitations
- Inner and outer corners share one footprint; they differ only in finish (outer has a trim corner post). Orient by rotating about Y.
- Ceiling_Edge handles one wall side; inside corners need two edge rotations plus manual trimming (not in the requested list).
- No collision shapes are included (use Godot's import "Generate Physics" or box shapes in code if needed).
- Materials are flat PBR colors with 1 UV unit = 1 m, ready for tiling textures; no textures included.
