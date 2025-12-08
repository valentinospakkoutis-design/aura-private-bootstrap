import React from 'react';
import { View } from 'react-native';
import { Canvas } from '@react-three/fiber';
import { MeshDistortMaterial, Sphere } from '@react-three/drei';

const AuraOrb = () => {
  return (
    <View style={{ height: 200, width: 200 }}>
      <Canvas>
        <ambientLight intensity={0.5} />
        <pointLight position={[10, 10, 10]} />
        <mesh>
          <Sphere args={[1, 32, 32]} />
          <MeshDistortMaterial color="hotpink" distort={0.4} speed={2} />
        </mesh>
      </Canvas>
    </View>
  );
};

export default AuraOrb;
