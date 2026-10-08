class_name RoomSpec
## Grid + placement helpers for the data-center room kit (meters, Y-up, +Z = front / exposed side).

const GRID := 1.0
const SLAB_Y := 0.0
const FLOOR_Y := 0.30            # finished raised-floor surface (place props at this height)
const WALL_TECH_H := 3.0
const WALL_ACOUSTIC_H := 2.0

## Centre of grid cell (ix, iz) at slab level (floor tiles use this).
static func cell_center(ix: int, iz: int) -> Vector3:
	return Vector3((ix + 0.5) * GRID, SLAB_Y, (iz + 0.5) * GRID)

## Props stand on the raised floor.
static func prop_position(ix: float, iz: float) -> Vector3:
	return Vector3(ix * GRID, FLOOR_Y, iz * GRID)

## Rotation (degrees about Y) so an asset's exposed/front side (+Z) faces the given direction.
## Godot: +90 deg maps +Z -> +X.
static func yaw_for(facing: Vector3) -> float:
	return rad_to_deg(atan2(facing.x, facing.z))

## Wall panel (origin = centre of back face): placed at the wall plane, mid-height.
static func wall_position(x: float, z: float, height: float) -> Vector3:
	return Vector3(x, height * 0.5, z)

## Server trolley platform slides on its local Y within [0.20, 1.35].
static func set_trolley_height(trolley: Node3D, y: float) -> void:
	var p := trolley.find_child("Trolley_Platform", true, false) as Node3D
	if p:
		p.position.y = clampf(y, 0.20, 1.35)
