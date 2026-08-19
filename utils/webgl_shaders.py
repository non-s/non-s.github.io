"""GLSL shaders for WebGL ray-marching renderer.

Each visual family is a signed distance function (SDF) that the fragment
shader ray-marches to produce filled, shaded 3D surfaces with PBR
materials, soft shadows and ambient occlusion — capabilities that the
CPU numpy/PIL wireframe path cannot achieve.

The shaders are injected into the HTML template's <script> tag at runtime.
The fragment shader is the creative core: it defines the scene's SDF,
the normal estimation, the lighting model and the material properties.
"""

from __future__ import annotations

# Vertex shader — minimal: pass through position and UV.
VERTEX_SHADER = """
precision highp float;
attribute vec2 a_position;
varying vec2 v_uv;
void main() {
    v_uv = a_position * 0.5 + 0.5;
    gl_Position = vec4(a_position, 0.0, 1.0);
}
"""

# Common GLSL header: uniforms, helpers, lighting model.
_COMMON_HEADER = """
precision highp float;
varying vec2 v_uv;
uniform float u_time;
uniform vec2 u_resolution;
uniform vec3 u_camera_pos;
uniform vec3 u_camera_target;
uniform float u_fov;
uniform vec3 u_light_pos;
uniform vec3 u_light_color;
uniform float u_light_intensity;
uniform vec3 u_base_color;
uniform vec3 u_accent_color;
uniform float u_metalness;
uniform float u_roughness;
uniform float u_bloom;
uniform float u_compression;
uniform float u_rupture;
uniform float u_tide;
uniform float u_stillness;
uniform int u_family;

#define MAX_STEPS 128
#define MAX_DIST 100.0
#define SURF_DIST 0.001
#define PI 3.14159265359

mat2 rot(float a) {
    float c = cos(a), s = sin(a);
    return mat2(c, -s, s, c);
}

float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

float smax(float a, float b, float k) {
    return -smin(-a, -b, k);
}

// SDF primitives.
float sdSphere(vec3 p, float r) { return length(p) - r; }
float sdTorus(vec3 p, vec2 t) {
    vec2 q = vec2(length(p.xz) - t.x, p.y);
    return length(q) - t.y;
}
float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}
float sdOctahedron(vec3 p, float s) {
    p = abs(p);
    return (p.x + p.y + p.z - s) * 0.57735027;
}

// Mandelbulb power-2 SDF (approximation for ray-marching).
float sdMandelbulb(vec3 p, float power) {
    vec3 z = p;
    float dr = 1.0;
    float r = 0.0;
    for (int i = 0; i < 4; i++) {
        r = length(z);
        if (r > 2.0) break;
        float theta = acos(z.z / r);
        float phi = atan(z.y, z.x);
        dr = pow(r, power - 1.0) * power * dr + 1.0;
        float zr = pow(r, power);
        theta *= power;
        phi *= power;
        z = zr * vec3(sin(theta) * cos(phi), sin(theta) * sin(phi), cos(theta));
        z += p;
    }
    return 0.5 * log(r) * r / dr;
}

// Gyroid surface SDF.
float sdGyroid(vec3 p) {
    float k = 1.0;
    float g = abs(dot(sin(p * k), cos(p.yzx * k))) - 0.3;
    return g * 0.5;
}

// Julia set 3D (quadratic Julia in R3 via quaternion).
float sdJulia(vec3 p, float t) {
    vec4 z = vec4(p, 0.0);
    vec4 c = vec4(0.3 * sin(t), 0.5 * cos(t * 0.7), 0.4 * sin(t * 1.3), 0.0);
    float m2 = 0.0;
    for (int i = 0; i < 8; i++) {
        m2 = dot(z, z);
        if (m2 > 16.0) break;
        z = vec4(z.x * z.x - dot(z.yzw, z.yzw), 2.0 * z.x * z.yzw) + c;
    }
    return 0.25 * sqrt(m2) * log2(m2);
}

// Helix SDF.
float sdHelix(vec3 p) {
    float r = length(p.xy);
    float a = atan(p.y, p.x) + p.z * 0.5;
    float d = abs(r - 0.8) - 0.15;
    float d2 = abs(sin(a * 3.0)) - 0.1;
    return max(d, d2 * 0.3);
}

// Klein bottle SDF (approximate).
float sdKlein(vec3 p) {
    float u = atan(p.x, p.z) * 2.0;
    float v = atan(p.y, length(p.xz) - 1.5);
    float r = 0.4;
    vec3 q = vec3(
        (1.5 + cos(u * 0.5) * sin(v) - sin(u * 0.5) * sin(v * 2.0)) * cos(u),
        (1.5 + cos(u * 0.5) * sin(v) - sin(u * 0.5) * sin(v * 2.0)) * sin(u),
        sin(u * 0.5) * sin(v) + cos(u * 0.5) * sin(v * 2.0)
    );
    return length(p - q) - r;
}

// Mobius strip SDF.
float sdMobius(vec3 p) {
    float u = atan(p.x, p.z);
    float v = (length(p.xz) - 1.0);
    float twist = u * 0.5;
    vec3 q = vec3(
        (1.0 + v * cos(twist)) * cos(u),
        v * sin(twist),
        (1.0 + v * cos(twist)) * sin(u)
    );
    return length(p - q) - 0.08;
}

// DNA double helix SDF.
float sdDNA(vec3 p) {
    p.z += u_time * 0.3;
    float a1 = p.z * 0.8;
    float a2 = a1 + PI;
    vec3 s1 = vec3(cos(a1) * 0.6, sin(a1) * 0.6, p.z);
    vec3 s2 = vec3(cos(a2) * 0.6, sin(a2) * 0.6, p.z);
    float d1 = sdSphere(p - s1, 0.15);
    float d2 = sdSphere(p - s2, 0.15);
    // Rungs.
    float rung_phase = fract(p.z * 0.5);
    float rung = sdBox(p - vec3(0.0, 0.0, floor(p.z * 0.5) / 0.5), vec3(0.7, 0.02, 0.02));
    float d = smin(d1, d2, 0.1);
    if (rung_phase < 0.05) d = smin(d, rung, 0.05);
    return d;
}

// Plasma field SDF.
float sdPlasma(vec3 p) {
    float t = u_time * 0.5;
    float d = sin(p.x * 2.0 + t) + sin(p.y * 2.0 + t * 1.3) + sin(p.z * 2.0 + t * 0.7);
    return abs(d) * 0.3 - 0.4;
}

// Accretion disk SDF.
float sdAccretion(vec3 p) {
    float r = length(p.xz);
    float a = atan(p.x, p.z) + u_time * 0.5;
    float disk = abs(p.y) - 0.05 - 0.3 * smoothstep(1.0, 3.0, r);
    float swirl = sin(a * 3.0 + r * 2.0) * 0.1;
    return max(disk - swirl, -(r - 3.0));
}

// Sphere with event-driven deformation (used by families that build on the
// base sphere: orb, comet, shell, hourglass, membrane, etc.).
float sdDeformedSphere(vec3 p, float t) {
    float breath = 0.14 * sin(u_time * 0.8 + dot(p, vec3(1.0)));
    float bloom = u_bloom * 0.3 * sin(length(p) * 3.0 - u_time * 2.0);
    float compress = u_compression * 0.2 * (1.0 - smoothstep(0.0, 0.5, abs(p.y)));
    float tide = u_tide * 0.15 * sin(p.x * 2.0 + u_time);
    float rupture_gap = u_rupture * 0.1 * smoothstep(0.4, 0.5, abs(sin(p.x * 2.0)));
    float still = max(0.25, 1.0 - 0.72 * u_stillness);
    float r = (1.0 + breath + bloom - compress + tide - rupture_gap) * still;
    return sdSphere(p, r);
}

// Torus knot (p,q)=(3,2).
float sdTorusKnot(vec3 p) {
    float u = atan(p.x, p.z);
    float r = length(p.xz);
    float tube = 0.2;
    float a = 3.0 * u;
    float b = 2.0 * u;
    vec3 q = vec3(
        (1.5 + cos(a) * 0.5) * cos(u),
        sin(b) * 0.5,
        (1.5 + cos(a) * 0.5) * sin(u)
    );
    return length(p - q) - tube;
}

// Superformula SDF.
float sdSuperformula(vec3 p) {
    float t = u_time * 0.2;
    float m = 6.0 + 2.0 * sin(t);
    float phi = atan(p.y, p.x);
    float r1 = pow(abs(cos(m * phi * 0.25)), 2.0) + pow(abs(sin(m * phi * 0.25)), 2.0);
    r1 = pow(r1, -0.5);
    float r = length(p.xy);
    float d = abs(r - r1 * 0.5) - 0.05;
    return max(d, abs(p.z) - 0.3);
}

// Cone SDF (used by comet family).
float sdCone(vec3 p, float r, float h) {
    vec2 q = vec2(length(p.xy), p.z);
    return max(dot(q, normalize(vec2(r, h))), -h - p.z);
}

// Scene SDF — dispatches to the selected family via if-else chain
// (GLSL ES 3.0 does not support switch statements).
float map(vec3 p) {
    float t = u_time;
    p.xz = rot(0.3 * sin(t * 0.2)) * p.xz;
    int f = u_family;

    if (f == 0) return sdDeformedSphere(p, t);            // orb
    if (f == 1) return sdTorus(p, vec2(1.0, 0.35));        // torus
    if (f == 2) { // ribbon
        float r = length(p.xy) - 0.8;
        return max(r - 0.1, abs(p.z) - 0.3 * sin(length(p.xy) * 3.0 + t));
    }
    if (f == 3) return smin(sdDeformedSphere(p, t), sdDeformedSphere(p - vec3(0.8,0,0), t), 0.3);
    if (f == 4) { // membrane
        float d = sdDeformedSphere(p, t);
        return smax(d, -sdSphere(p, 0.5), 0.1);
    }
    if (f == 5) { // comet
        float d = sdDeformedSphere(p, t);
        float tail = sdCone(p - vec3(0.0, 0.0, 1.5), 0.3, 2.0);
        return smin(d, tail, 0.2);
    }
    if (f == 6) { // shell (rotating)
        vec3 q = p;
        q.xz = rot(t * 0.1) * q.xz;
        return sdDeformedSphere(q, t);
    }
    if (f == 7) return sdTorusKnot(p);                     // knot
    if (f == 8) { // hourglass
        float pinch = abs(cos(p.y * 3.0));
        return sdSphere(p * vec3(1.0, 1.0, 1.0), 0.8 * pinch + 0.2);
    }
    if (f == 9) { // coral
        float d = sdSphere(p, 0.8);
        for (int i = 0; i < 4; i++) {
            float fi = float(i);
            vec3 q = p + vec3(sin(fi * 1.7 + t), cos(fi * 2.3), sin(fi * 1.1)) * 0.3;
            d = smin(d, sdSphere(q, 0.2), 0.15);
        }
        return d;
    }
    if (f == 10) return sdGyroid(p + t * 0.1);             // gyroid
    if (f == 11) return sdMandelbulb(p * 1.2, 2.0 + u_bloom); // mandelbulb
    if (f == 12) return sdJulia(p, t * 0.3);               // julia_set
    if (f == 13) return sdHelix(p);                        // helix
    if (f == 14) return sdMobius(p);                       // mobius
    if (f == 15) return sdKlein(p);                        // klein_bottle
    if (f == 16) return sdDNA(p);                          // dna_helix
    if (f == 17) return sdPlasma(p);                       // plasma_field
    if (f == 18) return sdAccretion(p);                    // accretion_disk
    if (f == 19) return sdSuperformula(p);                 // superformula
    if (f == 20) { // crystal_lattice
        vec3 q = fract(p * 2.0) - 0.5;
        return sdOctahedron(q, 0.3) / 2.0;
    }
    if (f == 21) { // torus_knot variant
        float u = atan(p.x, p.z) + t * 0.3;
        vec3 q = vec3(cos(3.0 * u) * 1.2, sin(2.0 * u) * 0.8, sin(3.0 * u) * 1.2);
        return length(p - q) - 0.15;
    }
    if (f == 22) { // spiral_galaxy
        float r = length(p.xz);
        float a = atan(p.x, p.z) + r * 1.5 + t * 0.1;
        float arm = abs(sin(a * 3.0)) - 0.1;
        return max(arm * 0.2, abs(p.y) - 0.1 - smoothstep(0.5, 2.5, r) * 0.05);
    }
    return sdDeformedSphere(p, t);
}

// Normal via tetrahedral gradient (4 taps instead of 6).
vec3 calcNormal(vec3 p) {
    const float eps = 0.001;
    const vec2 h = vec2(1.0, -1.0) * eps;
    return normalize(
        h.xyy * map(p + h.xyy) +
        h.yyx * map(p + h.yyx) +
        h.yxy * map(p + h.yxy) +
        h.xxx * map(p + h.xxx)
    );
}

// Soft shadow.
float softShadow(vec3 ro, vec3 rd, float mint, float maxt, float k) {
    float res = 1.0;
    float t = mint;
    for (int i = 0; i < 32; i++) {
        float h = map(ro + rd * t);
        res = min(res, k * h / t);
        t += clamp(h, 0.02, 0.3);
        if (h < 0.001 || t > maxt) break;
    }
    return clamp(res, 0.0, 1.0);
}

// Ambient occlusion.
float calcAO(vec3 p, vec3 n) {
    float occ = 0.0;
    float sca = 1.0;
    for (int i = 0; i < 5; i++) {
        float hr = 0.01 + 0.12 * float(i) / 4.0;
        float d = map(p + n * hr);
        occ += (hr - d) * sca;
        sca *= 0.95;
    }
    return clamp(1.0 - 3.0 * occ, 0.0, 1.0);
}

// PBR lighting (simplified Cook-Torrance).
vec3 pbrLight(vec3 p, vec3 n, vec3 viewDir) {
    vec3 lightDir = normalize(u_light_pos - p);
    float ndotl = max(dot(n, lightDir), 0.0);
    float ndotv = max(dot(n, viewDir), 0.0);
    vec3 halfDir = normalize(lightDir + viewDir);
    float ndoth = max(dot(n, halfDir), 0.0);

    // Diffuse (Lambert).
    vec3 diffuse = u_base_color * ndotl / PI;

    // Specular (GGX approximation).
    float alpha = u_roughness * u_roughness;
    float a2 = alpha * alpha;
    float denom = ndoth * ndoth * (a2 - 1.0) + 1.0;
    float d_ggx = a2 / (PI * denom * denom);
    float g_vis = 0.25 / max(ndotl * ndotv, 0.001);
    vec3 F0 = mix(vec3(0.04), u_base_color, u_metalness);
    vec3 specular = F0 * d_ggx * g_vis * ndotl;

    // Ambient + AO.
    float ao = calcAO(p, n);
    float shadow = softShadow(p + n * 0.01, lightDir, 0.02, 20.0, 16.0);
    vec3 ambient = u_base_color * 0.1 * ao;

    return (diffuse + specular) * u_light_color * u_light_intensity * shadow + ambient;
}

// (renderScene is inlined in main() for direct camera-ray construction.)

void main() {
    vec2 uv = (v_uv * 2.0 - 1.0);
    uv.x *= u_resolution.x / u_resolution.y;

    // Camera ray — simple forward-z approach (proven to work).
    vec3 ro = u_camera_pos;
    vec3 target = u_camera_target;
    vec3 forward = normalize(target - ro);
    vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), forward));
    vec3 up = cross(forward, right);
    vec3 rd = normalize(right * uv.x + up * uv.y + forward * u_fov);

    float t = 0.0;
    float min_dist = MAX_DIST;
    bool hit = false;
    for (int i = 0; i < MAX_STEPS; i++) {
        vec3 p = ro + rd * t;
        float d = map(p);
        min_dist = min(min_dist, d);
        if (d < SURF_DIST) { hit = true; break; }
        if (t > MAX_DIST) break;
        t += d;
    }

    // Background — dark void with subtle gradient.
    vec3 bg = mix(vec3(0.0), vec3(0.01, 0.005, 0.02), 1.0 - v_uv.y * 0.5);
    bg += u_accent_color * 0.02 * exp(-min_dist * 3.0);

    vec3 col;
    if (hit) {
        vec3 p = ro + rd * t;
        vec3 n = calcNormal(p);
        vec3 viewDir = normalize(ro - p);
        col = pbrLight(p, n, viewDir);
        float fresnel = pow(1.0 - max(dot(n, viewDir), 0.0), 3.0);
        col += u_accent_color * fresnel * 0.3;
        col = (col * (2.51 * col + 0.03)) / (col * (2.43 * col + 0.59) + 0.14);
        col = clamp(col, 0.0, 1.0);
    } else {
        col = bg;
    }
    col = pow(col, vec3(1.0 / 2.2));
    gl_FragColor = vec4(col, 1.0);
}
"""

# Full fragment shader (header + scene).
FRAGMENT_SHADER = _COMMON_HEADER


def build_fragment_shader(family_id: int) -> str:
    """Return the fragment shader source for a given family id.

    The shader is the same for all families (it dispatches via u_family
    uniform), but this helper exists so callers can pre-validate or
    customise per-family if needed in the future.
    """
    return FRAGMENT_SHADER


# Map family names to shader uniform IDs.
FAMILY_SHADER_IDS: dict[str, int] = {
    "orb": 0, "torus": 1, "ribbon": 2, "double_orb": 3, "membrane": 4,
    "comet": 5, "shell": 6, "knot": 7, "hourglass": 8, "coral": 9,
    "gyroid": 10, "mandelbulb": 11, "julia_set": 12, "helix": 13,
    "mobius": 14, "klein_bottle": 15, "dna_helix": 16, "plasma_field": 17,
    "accretion_disk": 18, "superformula": 19, "crystal_lattice": 20,
    "torus_knot": 21, "spiral_galaxy": 22,
}


def family_to_shader_id(family: str) -> int:
    """Return the shader uniform id for a visual family name (0 = orb fallback)."""
    return FAMILY_SHADER_IDS.get(family, 0)
