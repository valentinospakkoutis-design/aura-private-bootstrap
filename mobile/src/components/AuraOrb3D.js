import React, { useRef, useState } from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import { Canvas, useFrame } from '@react-three/fiber';

const { width } = Dimensions.get('window');

// The 3D Orb Mesh
function Orb({ color = '#4CAF50', speed = 1 }) {
  const meshRef = useRef();
  const [hovered, setHovered] = useState(false);

  useFrame((state) => {
    if (meshRef.current) {
      // Rotate the orb
      meshRef.current.rotation.x += 0.01 * speed;
      meshRef.current.rotation.y += 0.01 * speed;
      
      // Pulsating effect
      const scale = 1 + Math.sin(state.clock.elapsedTime * 2) * 0.1;
      meshRef.current.scale.set(scale, scale, scale);
    }
  });

  return (
    <mesh
      ref={meshRef}
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
      scale={hovered ? 1.2 : 1}
    >
      <sphereGeometry args={[1, 32, 32]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.5}
        roughness={0.3}
        metalness={0.8}
      />
    </mesh>
  );
}

// Main AuraOrb Component
export default function AuraOrb3D({ 
  size = width * 0.5, 
  color = '#4CAF50',
  speed = 1,
  style 
}) {
  return (
    <View style={[styles.container, { width: size, height: size }, style]}>
      <Canvas
        camera={{ position: [0, 0, 3], fov: 50 }}
        style={styles.canvas}
      >
        {/* Lights */}
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} intensity={1} />
        <pointLight position={[-10, -10, -10]} intensity={0.5} color="#4CAF50" />
        
        {/* The Orb */}
        <Orb color={color} speed={speed} />
      </Canvas>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignSelf: 'center',
    backgroundColor: 'transparent',
  },
  canvas: {
    width: '100%',
    height: '100%',
  },
});

