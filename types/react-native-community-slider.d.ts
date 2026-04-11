declare module '@react-native-community/slider' {
  import * as React from 'react';
  import { ViewProps } from 'react-native';

  export interface SliderProps extends ViewProps {
    minimumValue?: number;
    maximumValue?: number;
    value?: number;
    step?: number;
    minimumTrackTintColor?: string;
    maximumTrackTintColor?: string;
    thumbTintColor?: string;
    disabled?: boolean;
    onValueChange?: (value: number) => void;
    onSlidingStart?: (value: number) => void;
    onSlidingComplete?: (value: number) => void;
  }

  const Slider: React.ComponentType<SliderProps>;
  export default Slider;
}
