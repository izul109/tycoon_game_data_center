// LED status shader for Switch_24P_1U / Switch_48P_1U (surface index 1 = M_LED).
// Per-instance status: 4 x uint, 2 bits per LED (16 LEDs per word).
//   0 = off, 1 = link (green), 2 = activity (amber blink), 3 = fault (red)
// LED index: Port_NN = NN-1 | Uplink_NN = 47+NN | system PWR/SYS/FAN = 52/53/54
// NOTE: written for Godot 4.x but not run in the editor here - test on first import.
shader_type spatial;
render_mode unshaded;

instance uniform uint led_w0 = 0u;
instance uniform uint led_w1 = 0u;
instance uniform uint led_w2 = 0u;
instance uniform uint led_w3 = 0u;

uniform vec3 col_off : source_color = vec3(0.04, 0.045, 0.05);
uniform vec3 col_link : source_color = vec3(0.10, 0.95, 0.25);
uniform vec3 col_act : source_color = vec3(1.00, 0.65, 0.05);
uniform vec3 col_fault : source_color = vec3(1.00, 0.10, 0.05);
uniform float blink_hz = 4.0;

void fragment() {
	uint idx = uint(UV.x * 64.0);
	uint word = idx >> 4u;
	uint w = led_w0;
	if (word == 1u) w = led_w1;
	else if (word == 2u) w = led_w2;
	else if (word == 3u) w = led_w3;
	uint st = (w >> ((idx & 15u) * 2u)) & 3u;
	vec3 c = col_off;
	if (st == 1u) c = col_link;
	else if (st == 2u) c = (fract(TIME * blink_hz + float(idx) * 0.37) < 0.5) ? col_act : col_off;
	else if (st == 3u) c = col_fault;
	ALBEDO = c;
}
