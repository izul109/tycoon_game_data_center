class_name ISPLed
## Runtime helpers for the ISP_* devices (LED state + port anchors).
## Shared materials -> all LEDs of the same state batch together across many instances.

enum State { OFF, GREEN, AMBER, BLUE, RED }

const COLORS := {
	State.GREEN: Color(0.10, 1.00, 0.25),
	State.AMBER: Color(1.00, 0.60, 0.05),
	State.BLUE:  Color(0.15, 0.45, 1.00),
	State.RED:   Color(1.00, 0.10, 0.08),
}
static var _mats := {}

static func _mat(state: State) -> StandardMaterial3D:
	if not _mats.has(state):
		var m := StandardMaterial3D.new()
		if state == State.OFF:
			m.albedo_color = Color(0.02, 0.02, 0.025)
		else:
			var c: Color = COLORS[state]
			m.albedo_color = Color(c.r * 0.15, c.g * 0.15, c.b * 0.15)
			m.emission_enabled = true
			m.emission = c
			m.emission_energy_multiplier = 2.0
		_mats[state] = m
	return _mats[state]

## led: "LED_PWR", "LED_ISP", "LED_WAN", "LED_LAN" or "LED_MGMT"
static func set_led(device: Node, led: String, state: State) -> void:
	var n := device.find_child(led, true, false) as MeshInstance3D
	if n:
		n.set_surface_override_material(0, _mat(state))

## port: "ISP_IN", "WAN", "LAN", "MGMT" or "Power_In". +Z of the returned node points OUT of the port.
static func get_port(device: Node, port: String) -> Node3D:
	return device.find_child(port, true, false) as Node3D
