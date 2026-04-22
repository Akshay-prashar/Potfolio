import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';

// --- Configuration ---
const CONFIG = {
    // Colors
    colorBg: new THREE.Color('#0D0D0D'),
    colorPurple: new THREE.Color('#A78BFA'),
    colorBlue: new THREE.Color('#60A5FA'),
    colorHighlight: new THREE.Color('#C084FC'),

    // Mesh
    meshSize: 100,
    meshSegments: 128, // High res for smooth waves

    // Particles
    particleCount: 4000,

    // Animation
    speed: 0.15, // Very slow organic movement

    // Bloom
    bloomStrength: 0.35, // Subtle
    bloomRadius: 0.8,
    bloomThreshold: 0.1
};

// --- Scene Setup ---
const container = document.getElementById('canvas-container');
const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(CONFIG.colorBg, 0.025);
scene.background = CONFIG.colorBg;

const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 15, 40);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({
    antialias: false, // Post-processing handles AA usually, or we trade for perf
    powerPreference: "high-performance"
});
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2)); // Cap pixel ratio for perf
container.appendChild(renderer.domElement);

// --- Simplex Noise Shader Chunk (for Vertex Shader) ---
const noiseShaderChunk = `
    vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
    vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

    float snoise(vec2 v) {
        const vec4 C = vec4(0.211324865405187,  // (3.0-sqrt(3.0))/6.0
                            0.366025403784439,  // 0.5*(sqrt(3.0)-1.0)
                            -0.577350269189626, // -1.0 + 2.0 * C.x
                            0.024390243902439); // 1.0 / 41.0
        vec2 i  = floor(v + dot(v, C.yy) );
        vec2 x0 = v - i + dot(i, C.xx);
        vec2 i1;
        i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
        vec4 x12 = x0.xyxy + C.xxzz;
        x12.xy -= i1;
        i = mod289(i);
        vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 ))
            + i.x + vec3(0.0, i1.x, 1.0 ));
        vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
        m = m*m ;
        m = m*m ;
        vec3 x = 2.0 * fract(p * C.www) - 1.0;
        vec3 h = abs(x) - 0.5;
        vec3 ox = floor(x + 0.5);
        vec3 a0 = x - ox;
        m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );
        vec3 g;
        g.x  = a0.x  * x0.x  + h.x  * x0.y;
        g.yz = a0.yz * x12.xz + h.yz * x12.yw;
        return 130.0 * dot(m, g);
    }
`;

// --- Organic Mesh Surface ---
const meshGeometry = new THREE.PlaneGeometry(CONFIG.meshSize, CONFIG.meshSize, CONFIG.meshSegments, CONFIG.meshSegments);
meshGeometry.rotateX(-Math.PI / 2);

const meshMaterial = new THREE.ShaderMaterial({
    uniforms: {
        uTime: { value: 0 },
        uColor1: { value: CONFIG.colorPurple },
        uColor2: { value: CONFIG.colorBlue },
        uMouse: { value: new THREE.Vector2(0, 0) }
    },
    vertexShader: `
        uniform float uTime;
        uniform vec2 uMouse;
        varying vec2 vUv;
        varying float vElevation;
        
        ${noiseShaderChunk}

        void main() {
            vUv = uv;
            vec3 pos = position;
            
            // Base organic movement
            float noiseFreq = 0.05;
            float noiseAmp = 4.0;
            float noiseVal = snoise(vec2(pos.x * noiseFreq + uTime * 0.5, pos.z * noiseFreq + uTime * 0.2));
            
            // Secondary detail layer
            float noiseVal2 = snoise(vec2(pos.x * 0.1 - uTime * 0.3, pos.z * 0.1 + uTime * 0.1));
            
            float elevation = (noiseVal * noiseAmp) + (noiseVal2 * 1.0);
            
            // Mouse interaction (subtle bulge)
            float dist = distance(pos.xz, uMouse * 40.0); // Map mouse to world space roughly
            float interaction = smoothstep(15.0, 0.0, dist) * 2.0;
            elevation += interaction * sin(uTime * 2.0);

            pos.y += elevation;
            vElevation = elevation;

            gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
        }
    `,
    fragmentShader: `
        uniform vec3 uColor1;
        uniform vec3 uColor2;
        varying float vElevation;
        varying vec2 vUv;

        void main() {
            // Color mixing based on height
            float mixStrength = smoothstep(-4.0, 4.0, vElevation);
            vec3 color = mix(uColor1, uColor2, mixStrength);
            
            // Grid lines logic
            // Create a grid pattern using UVs
            float gridX = step(0.98, fract(vUv.x * 60.0)); // 60 lines
            float gridY = step(0.98, fract(vUv.y * 60.0));
            float grid = max(gridX, gridY);
            
            // Glow at peaks
            float peakGlow = smoothstep(2.0, 5.0, vElevation);
            color += vec3(peakGlow * 0.5);

            // Alpha: more transparent in valleys, solid on grid lines
            float alpha = 0.1 + (grid * 0.4) + (peakGlow * 0.3);
            
            gl_FragColor = vec4(color, alpha);
        }
    `,
    transparent: true,
    side: THREE.DoubleSide,
    wireframe: false, // We simulate wireframe in shader for better control
    blending: THREE.AdditiveBlending,
    depthWrite: false
});

const mesh = new THREE.Mesh(meshGeometry, meshMaterial);
scene.add(mesh);


// --- Particle Field ---
const particlesGeometry = new THREE.BufferGeometry();
const posArray = new Float32Array(CONFIG.particleCount * 3);
const randomArray = new Float32Array(CONFIG.particleCount);

for (let i = 0; i < CONFIG.particleCount; i++) {
    posArray[i * 3] = (Math.random() - 0.5) * 120; // x
    posArray[i * 3 + 1] = (Math.random() - 0.5) * 40 + 10; // y (above mesh)
    posArray[i * 3 + 2] = (Math.random() - 0.5) * 100 - 20; // z
    randomArray[i] = Math.random();
}

particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
particlesGeometry.setAttribute('aRandom', new THREE.BufferAttribute(randomArray, 1));

const particlesMaterial = new THREE.ShaderMaterial({
    uniforms: {
        uTime: { value: 0 },
        uColor: { value: CONFIG.colorHighlight }
    },
    vertexShader: `
        uniform float uTime;
        attribute float aRandom;
        varying float vAlpha;
        
        void main() {
            vec3 pos = position;
            
            // Gentle drift
            pos.y += sin(uTime * 0.5 + aRandom * 10.0) * 2.0;
            pos.x += cos(uTime * 0.3 + aRandom * 5.0) * 1.0;
            
            vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
            gl_Position = projectionMatrix * mvPosition;
            gl_PointSize = (2.0 * aRandom + 1.0) * (30.0 / -mvPosition.z);
            
            // Fade distant particles
            vAlpha = smoothstep(50.0, 0.0, abs(mvPosition.z));
        }
    `,
    fragmentShader: `
        uniform vec3 uColor;
        varying float vAlpha;
        
        void main() {
            float r = distance(gl_PointCoord, vec2(0.5));
            if (r > 0.5) discard;
            
            float glow = 1.0 - (r * 2.0);
            glow = pow(glow, 2.0);
            
            gl_FragColor = vec4(uColor, glow * vAlpha * 0.8);
        }
    `,
    transparent: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false
});

const particles = new THREE.Points(particlesGeometry, particlesMaterial);
scene.add(particles);


// --- Post Processing ---
const composer = new EffectComposer(renderer);
const renderPass = new RenderPass(scene, camera);
composer.addPass(renderPass);

// 1. Bloom
const bloomPass = new UnrealBloomPass(
    new THREE.Vector2(window.innerWidth, window.innerHeight),
    CONFIG.bloomStrength,
    CONFIG.bloomRadius,
    CONFIG.bloomThreshold
);
composer.addPass(bloomPass);

// 2. Cinematic Shader (Vignette, Noise, Color Grading)
const cinematicShader = {
    uniforms: {
        tDiffuse: { value: null },
        uResolution: { value: new THREE.Vector2(window.innerWidth, window.innerHeight) },
        uTime: { value: 0 }
    },
    vertexShader: `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    fragmentShader: `
        uniform sampler2D tDiffuse;
        uniform vec2 uResolution;
        uniform float uTime;
        varying vec2 vUv;

        // Noise function
        float random(vec2 st) {
            return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
        }

        void main() {
            vec4 color = texture2D(tDiffuse, vUv);
            
            // 1. Vignette
            vec2 uv = vUv * (1.0 - vUv.yx);
            float vig = uv.x * uv.y * 15.0;
            vig = pow(vig, 0.25); // Strength
            color.rgb *= vig;
            
            // 2. Color Grading (Cool Tint)
            color.b += 0.02; // Slight blue boost
            color.r -= 0.01;
            
            // Contrast (S-Curve)
            color.rgb = pow(color.rgb, vec3(1.1)); 
            
            // 3. Film Grain
            float noise = random(vUv + uTime);
            color.rgb += (noise - 0.5) * 0.03; // 3% intensity

            gl_FragColor = color;
        }
    `
};

const cinematicPass = new ShaderPass(cinematicShader);
composer.addPass(cinematicPass);


// --- Interaction & Animation ---
const mouse = { x: 0, y: 0 };
const target = { x: 0, y: 0 };

document.addEventListener('mousemove', (e) => {
    // Normalize mouse -1 to 1
    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;

    // Update shader uniform
    meshMaterial.uniforms.uMouse.value.x = mouse.x;
    meshMaterial.uniforms.uMouse.value.y = mouse.y;
});

const clock = new THREE.Clock();

function animate() {
    requestAnimationFrame(animate);

    const time = clock.getElapsedTime();

    // Update Uniforms
    meshMaterial.uniforms.uTime.value = time * CONFIG.speed;
    particlesMaterial.uniforms.uTime.value = time * CONFIG.speed;
    cinematicPass.uniforms.uTime.value = time;

    // Smooth Camera Parallax (Lerp)
    target.x = mouse.x * 2.0; // Max tilt range
    target.y = mouse.y * 1.0;

    camera.position.x += (target.x - camera.position.x) * 0.05;
    camera.position.y += (target.y + 15 - camera.position.y) * 0.05; // +15 is base height
    camera.lookAt(0, 0, 0);

    // Subtle constant rotation
    scene.rotation.y = Math.sin(time * 0.05) * 0.05;

    composer.render();
}

animate();

// --- Resize ---
window.addEventListener('resize', () => {
    const width = window.innerWidth;
    const height = window.innerHeight;

    camera.aspect = width / height;
    camera.updateProjectionMatrix();

    renderer.setSize(width, height);
    composer.setSize(width, height);
    cinematicPass.uniforms.uResolution.value.set(width, height);
});
