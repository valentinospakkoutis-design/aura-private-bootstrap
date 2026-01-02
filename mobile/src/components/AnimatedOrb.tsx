import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import { Canvas, useFrame } from '@react-three/fiber';
import { MeshStandardMaterial, Sphere } from '@react-three/drei';
import { theme } from '../constants/theme';

const { width } = Dimensions.get('window');

interface AnimatedOrbProps {
  state?: 'calm' | 'bullish' | 'bearish' | 'thinking' | 'alert';
  size?: number;
}

// Orb component with animations
function Orb({ state }: { state: string }) {
  const meshRef = useRef<any>(null);
  const scaleRef = useRef(1);
  const scaleDirection = useRef(1);

  const getOrbColor = () => {
    switch (state) {
      case 'bullish':
        return theme.colors.market.bullish;
      case 'bearish':
        return theme.colors.market.bearish;
      case 'thinking':
        return theme.colors.brand.secondary;
      case 'alert':
        return theme.colors.semantic.warning;
      case 'calm':
      default:
        return theme.colors.brand.primary;
    }
  };

  useFrame(({ clock }) => {
    if (meshRef.current) {
      // Continuous rotation
      meshRef.current.rotation.y = clock.getElapsedTime() * 0.5;
      meshRef.current.rotation.x = Math.sin(clock.getElapsedTime() * 0.3) * 0.2;

      // Breathing effect
      const time = clock.getElapsedTime();
      scaleRef.current = 1 + Math.sin(time * 2) * 0.1;
      meshRef.current.scale.set(
        scaleRef.current,
        scaleRef.current,
        scaleRef.current
      );
    }
  });

  const color = getOrbColor();

  return (
    <Sphere ref={meshRef} args={[1, 64, 64]}>
      <MeshStandardMaterial
        color={color}
        metalness={0.8}
        roughness={0.2}
        emissive={color}
        emissiveIntensity={0.3}
      />
    </Sphere>
  );
}

export const AnimatedOrb: React.FC<AnimatedOrbProps> = ({
  state = 'calm',
  size = width * 0.6,
}) => {
  return (
    <View style={[styles.container, { width: size, height: size }]}>
      <Canvas
        camera={{ position: [0, 0, 3], fov: 75 }}
        gl={{ alpha: true, antialias: true }}
      >
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} />
        <Orb state={state} />
      </Canvas>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    alignSelf: 'center',
  },
});

