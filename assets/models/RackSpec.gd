class_name RackSpec
## Dimensional reference for Rack_42U.glb (meters, Y-up, FRONT = +Z in the imported rack space).
## Rack origin = bottom-centre of footprint.

const U := 0.04445
const N_U := 42
const Y_U0 := 0.150                      # bottom edge of U1
const Z_FRONT_PLANE := 0.430             # front rail mounting plane (ear BACK face sits here)
const Z_REAR_PLANE := -0.430             # rear rail mounting plane
const PANEL_W := 0.4826                  # 19" panel width
const OPEN_W := 0.45085                  # 17.75" clear opening between rails
const HOLE_X := 0.23255                  # hole centre offset from rack centreline
const MAX_DEPTH := 0.860                 # front plane -> rear plane

static func u_bottom_y(u: int) -> float:
	return Y_U0 + (u - 1) * U            # u = 1..42

static func u_top_y(u: int, height_u: int = 1) -> float:
	return Y_U0 + (u - 1 + height_u) * U

## Rack-mount device convention: origin at bottom-centre of its lowest U,
## on the front mounting plane, body extends toward local -Z, front plate toward +Z.
static func mount(device: Node3D, rack: Node3D, u: int) -> void:
	device.position = Vector3(0.0, u_bottom_y(u), Z_FRONT_PLANE)
	rack.add_child(device)

## Open the doors: rotate around local Y (hinge is the node origin).
## FrontDoor hinge on -X side, opens with negative Y rotation; RearDoor is rotated 180 deg already.
static func set_door(door: Node3D, open_deg: float) -> void:
	var base_y := PI if door.name.begins_with("Rack_RearDoor") else 0.0
	door.rotation.y = base_y - deg_to_rad(open_deg)
