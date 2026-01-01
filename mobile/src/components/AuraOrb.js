import React, { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { MeshDistortMaterial, Sphere, Float, Stars } from '@react-three/drei';
import { View, StyleSheet, Dimensions } from 'react-native';
import * as Haptics from 'expo-haptics';

const { width, height } = Dimensions.get('window');

// Orb States Configuration
const ORB_STATES = {
  calm: {
    color: '#4ECDC4',
    distort: 0.2,
    speed: 1,
    emissive: '#2C3E50',
    particleCount: 50
  },
  bullish: {
    color: '#00FF88',
    distort: 0.4,
    speed: 3,
    emissive: '#00CC66',
    particleCount: 200
  },
  bearish: {
    color: '#FF3366',
    distort: 0.5,
    speed: 4,
    emissive: '#CC0033',
    particleCount: 150
  },
  thinking: {
    color: '#5B9FFF',
    distort: 0.3,
    speed: 2,
    emissive: '#3366CC',
    particleCount: 100
  },
  alert: {
    color: '#B565FF',
    distort: 0.6,
    speed: 5,
    emissive: '#8833CC',
    particleCount: 300
  }
};

// Animated Orb Core
function AnimatedOrb({ state = 'calm', onTouch }) {
  const meshRef = useRef();
  const config = ORB_STATES[state];

  useFrame(({ clock }) => {
    if (meshRef.current) {
      // Rotation animation
      meshRef.current.rotation.x = Math.sin(clock.getElapsedTime() * 0.3) * 0.2;
      meshRef.current.rotation.y += 0.01 * config.speed;
      
      // Breathing effect (scale pulsing)
      const breathe = Math.sin(clock.getElapsedTime() * config.speed) * 0.1 + 1;
      meshRef.current.scale.set(breathe, breathe, breathe);
    }
  });

  const handlePress = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onTouch?.();
  };

  return (
    <Float speed={config.speed} rotationIntensity={0.5} floatIntensity={0.5}>
      <Sphere 
        ref={meshRef} 
        args={[1, 128, 128]} 
        onClick={handlePress}
      >
        <MeshDistortMaterial
          color={config.color}
          emissive={config.emissive}
          emissiveIntensity={0.5}
          distort={config.distort}
          speed={config.speed}
          roughness={0.2}
          metalness={0.8}
        />
      </Sphere>
    </Float>
  );
}

// Particle System
function Particles({ count = 100, color = '#FFFFFF' }) {
  const particles = useMemo(() => {
    const temp = [];
    for (let i = 0; i < count; i++) {
      const x = (Math.random() - 0.5) * 10;
      const y = (Math.random() - 0.5) * 10;
      const z = (Math.random() - 0.5) * 10;
      temp.push({ position: [x, y, z] });
    }
    return temp;
  }, [count]);

  return (
    <group>
      {particles.map((particle, i) => (
        <mesh key={i} position={particle.position}>
          <sphereGeometry args={[0.02, 8, 8]} />
          <meshBasicMaterial color={color} transparent opacity={0.6} />
        </mesh>
      ))}
    </group>
  );
}

// Main Orb Component
export default function AuraOrb({ 
  state = 'calm', 
  showParticles = true,
  showStars = true,
  onTouch 
}) {
  const config = ORB_STATES[state];

  return (
    <View style={styles.container}>
      <Canvas
        camera={{ position: [0, 0, 3], fov: 75 }}
        gl={{ alpha: true, antialias: true }}
      >
        {/* Ambient Light */}
        <ambientLight intensity={0.3} />
        
        {/* Directional Light */}
        <directionalLight position={[5, 5, 5]} intensity={1} />
        
        {/* Point Light (follows orb) */}
        <pointLight position={[0, 0, 0]} intensity={2} color={config.color} />
        
        {/* Background Stars */}
        {showStars && <Stars radius={100} depth={50} count={5000} factor={4} />}
        
        {/* The Orb */}
        <AnimatedOrb state={state} onTouch={onTouch} />
        
        {/* Particle System */}
        {showParticles && <Particles count={config.particleCount} color={config.color} />}
      </Canvas>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: width,
    height: height * 0.5,
    backgroundColor: 'transparent'
  }
});
