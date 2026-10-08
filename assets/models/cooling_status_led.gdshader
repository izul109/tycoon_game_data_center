// Status LED shader for all Cooling_* assets (surface index 1 = M_Status).
// Per-instance state: one uint, 2 bits per LED (16 LEDs max).  0 off, 1 green, 2 amber (blink), 3 red.
// LED index: 0 = status, 1 = alarm, 2 = power.
// NOTE: written for Godot 4.x, not run in the editor here - test on first import.
shader_type spatial;
render_mode unshaded;

instance uniform uint led_word = 0u;

uniform vec3 col_off : source_color = vec3(0.04, 0.045, 0.05);
uniform vec3 col_ok : source_color = vec3(0.10, 0.95, 0.25);
uniform vec3 col_warn : source_color = vec3(1.00, 0.65, 0.05);
uniform vec3 col_fault : source_color = vec3(1.00, 0.10, 0.05);
uniform float blink_hz = 2.0;

void fragment() {
	uint idx = uint(UV.x * 16.0);
	uint st = (led_word >> (idx * 2u)) & 3u;
	vec3 c = col_off;
	if (st == 1u) c = col_ok;
	else if (st == 2u) c = (fract(TIME * blink_hz) < 0.5) ? col_warn : col_off;
	else if (st == 3u) c = col_fault;
	ALBEDO = c;
}
