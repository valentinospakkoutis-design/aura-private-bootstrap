# AURA Animations Guide 🎨

## Overview

Το AURA χρησιμοποιεί **React Native Reanimated** για smooth, 60 FPS animations που κάνουν το app να νιώθει ζωντανό και responsive.

---

## Available Animated Components

### 1. **AnimatedButton**
Κουμπί με scale & opacity animation on press.

**Usage:**
```tsx
import { AnimatedButton } from '@/components/ui/AnimatedButton';

<AnimatedButton
  title="Click Me"
  onPress={() => console.log('Pressed!')}
  variant="primary"
  size="medium"
  fullWidth
/>
```

**Props:**
- `title`: string - Button text
- `onPress`: () => void - Press handler
- `variant`: 'primary' | 'secondary' | 'ghost' | 'gradient' | 'danger'
- `size`: 'small' | 'medium' | 'large'
- `fullWidth`: boolean - Full width button
- `disabled`: boolean - Disabled state
- `loading`: boolean - Loading state
- `icon`: ReactNode - Optional icon

**Features:**
- ✅ Scale animation on press
- ✅ Opacity animation on press
- ✅ Haptic feedback
- ✅ Loading state
- ✅ Disabled state

---

### 2. **AnimatedCard**
Card component με multiple animation types.

**Usage:**
```tsx
import { AnimatedCard } from '@/components/ui/AnimatedCard';

<AnimatedCard delay={0} animationType="slideUp">
  <Text>Card Content</Text>
</AnimatedCard>
```

**Props:**
- `delay`: number - Animation delay in ms (for staggered animations)
- `animationType`: 'slideUp' | 'fade' | 'scale' | 'slide' (default: 'slideUp')
- `style`: ViewStyle - Custom card style
- `children`: ReactNode - Card content

**Animation Types:**
- `slideUp`: Slides up from bottom (default)
- `fade`: Fades in
- `scale`: Scales from 0.9 to 1
- `slide`: Slides from right

**Features:**
- ✅ Multiple animation types
- ✅ Staggered animations support
- ✅ Smooth entrance animations
- ✅ Built-in card styling

---

### 3. **AnimatedCounter**
Smooth number counter με animated transitions.

**Usage:**
```tsx
import { AnimatedCounter } from '@/components/ui/AnimatedCounter';

<AnimatedCounter
  value={1000}
  prefix="$"
  decimals={2}
  duration={1000}
  style={styles.counter}
/>
```

**Props:**
- `value`: number - Counter value (required)
- `prefix`: string - Optional prefix (e.g., "$", "€", "£") (default: "")
- `suffix`: string - Optional suffix (e.g., "%", "kg", "m") (default: "")
- `decimals`: number - Decimal places (default: 0)
- `duration`: number - Animation duration in ms (default: 1000)
- `style`: TextStyle - Custom text style

**Features:**
- ✅ Smooth number transitions
- ✅ Customizable duration
- ✅ Prefix/suffix support
- ✅ Decimal formatting
- ✅ Monospace font for numbers
- ✅ Built-in large font size

**Note:** Το prefix/suffix μπορεί να είναι οποιοδήποτε string. Για currency symbols, χρησιμοποίησε `prefix="$"` (χωρίς escape character).

---

### 4. **AnimatedProgressBar**
Progress bar με smooth animations.

**Usage:**
```tsx
import { AnimatedProgressBar } from '@/components/ui/AnimatedProgressBar';

<AnimatedProgressBar
  progress={0.75}
  color={theme.colors.brand.primary}
  height={12}
  showLabel
  animated
/>
```

**Props:**
- `progress`: number - Progress value (0-1)
- `color`: string - Progress bar color
- `height`: number - Bar height
- `showLabel`: boolean - Show percentage label
- `animated`: boolean - Enable smooth animations

**Features:**
- ✅ Smooth progress animations
- ✅ Customizable colors
- ✅ Optional percentage label
- ✅ Configurable height

---

### 5. **AnimatedListItem**
List item με staggered entrance animations.

**Usage:**
```tsx
import { AnimatedListItem } from '@/components/ui/AnimatedListItem';

<AnimatedListItem
  index={0}
  onPress={() => console.log('Pressed!')}
>
  <Text>List Item</Text>
</AnimatedListItem>
```

**Props:**
- `index`: number - Item index (for staggered animations, 100ms delay per item)
- `onPress`: () => void - Optional press handler
- `children`: ReactNode - Item content
- `style`: ViewStyle - Custom style

**Features:**
- ✅ Staggered entrance animations (100ms delay per item)
- ✅ Press animations (scale on press)
- ✅ Haptic feedback on press
- ✅ Smooth transitions
- ✅ Auto-disabled if no onPress handler

---

### 6. **SkeletonLoader**
Loading skeleton με shimmer animation.

**Usage:**
```tsx
import { SkeletonLoader, SkeletonCard } from '@/components/ui/SkeletonLoader';

<SkeletonLoader width="100%" height={20} />
<SkeletonCard />
```

**Props:**
- `width`: string | number - Skeleton width
- `height`: number - Skeleton height
- `style`: ViewStyle - Custom style
- `SkeletonCard`: Predefined card skeleton

**Features:**
- ✅ Shimmer animation
- ✅ Customizable dimensions
- ✅ Predefined card skeleton

---

### 7. **SwipeableCard**
Card με swipe-to-delete gesture.

**Usage:**
```tsx
import { SwipeableCard } from '@/components/ui/SwipeableCard';

<SwipeableCard
  onDelete={() => console.log('Deleted!')}
  deleteText="Διαγραφή"
>
  <Text>Card Content</Text>
</SwipeableCard>
```

**Props:**
- `onDelete`: () => void - Delete handler
- `deleteText`: string - Delete button text
- `children`: ReactNode - Card content

**Features:**
- ✅ Swipe-to-delete gesture
- ✅ Smooth swipe animations
- ✅ Customizable delete text

---

### 8. **PageTransition**
Page transition wrapper για smooth screen transitions.

**Usage:**
```tsx
import { PageTransition } from '@/components/ui/PageTransition';

<PageTransition type="slideUp">
  <View>Screen Content</View>
</PageTransition>
```

**Props:**
- `type`: 'fade' | 'slideUp' | 'slideDown' | 'slideLeft' | 'slideRight'
- `children`: ReactNode - Screen content

**Features:**
- ✅ Smooth page transitions
- ✅ Multiple transition types
- ✅ Consistent animations

---

## Animation Presets

Το AURA χρησιμοποιεί **AnimationPresets** για consistent animations across the app.

### Timing Presets
```tsx
import { ANIMATION_PRESETS } from '@/utils/AnimationPresets';

ANIMATION_PRESETS.timing.fast      // 200ms
ANIMATION_PRESETS.timing.normal    // 400ms
ANIMATION_PRESETS.timing.slow       // 600ms
ANIMATION_PRESETS.timing.verySlow   // 1000ms
```

### Spring Presets
```tsx
ANIMATION_PRESETS.spring.gentle    // Gentle bounce
ANIMATION_PRESETS.spring.bouncy     // Bouncy animation
ANIMATION_PRESETS.spring.stiff      // Stiff animation
ANIMATION_PRESETS.spring.slow       // Slow animation
```

### Easing Presets
```tsx
ANIMATION_PRESETS.easing.easeIn     // Ease in
ANIMATION_PRESETS.easing.easeOut    // Ease out
ANIMATION_PRESETS.easing.easeInOut  // Ease in-out
ANIMATION_PRESETS.easing.linear     // Linear
```

---

## useAnimation Hook

Custom hook για simplified animation management.

**Usage:**
```tsx
import { useAnimation } from '@/hooks/useAnimation';
import { useAnimatedStyle } from 'react-native-reanimated';

function MyComponent() {
  const { animatedValue, animateWithSpring, animateWithTiming, reset } = useAnimation();

  useEffect(() => {
    // Spring animation
    animateWithSpring(1, 'gentle');
    
    // Or timing animation
    animateWithTiming(1, 400, 'easeOut');
  }, []);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: animatedValue.value,
    transform: [{ scale: animatedValue.value }],
  }));

  return <Animated.View style={animatedStyle}>...</Animated.View>;
}
```

**Methods:**
- `animateWithSpring(toValue, preset?)`: Animates με spring physics
- `animateWithTiming(toValue, duration?, easing?)`: Animates με timing
- `reset()`: Resets animated value to 0
- `animatedValue`: Shared value για use in animated styles

---

## Best Practices

### 1. **Use Staggered Animations**
```tsx
{[1, 2, 3].map((item, index) => (
  <AnimatedCard key={item} delay={index * 100} animationType="slideUp">
    <Text>Item {item}</Text>
  </AnimatedCard>
))}
```

### 2. **Use Animation Presets**
```tsx
// ✅ Good
animateWithSpring(1, 'gentle');

// ❌ Bad
animateWithSpring(1, { damping: 20, stiffness: 90 });
```

### 3. **Use Page Transitions**
```tsx
// ✅ Good
<PageTransition type="slideUp">
  <View>Screen Content</View>
</PageTransition>

// ❌ Bad
<View>Screen Content</View>
```

### 4. **Use Skeleton Loaders**
```tsx
// ✅ Good
{loading ? <SkeletonCard /> : <Content />}

// ❌ Bad
{loading ? <ActivityIndicator /> : <Content />}
```

### 5. **Use Animated Counters**
```tsx
// ✅ Good
<AnimatedCounter value={balance} prefix="$" decimals={2} />

// ❌ Bad
<Text>${balance.toFixed(2)}</Text>
```

---

## Performance Tips

1. **Use `useAnimatedStyle`** για animated styles
2. **Avoid unnecessary re-renders** με `useMemo` και `useCallback`
3. **Use `runOnJS`** για JavaScript functions in animations
4. **Use `withSpring`** για natural animations
5. **Use `withTiming`** για precise timing

---

## Testing

Χρησιμοποίησε το **AnimationTestScreen** για testing όλων των animated components:

```tsx
// Navigate to /animation-test
import { useRouter } from 'expo-router';

const router = useRouter();
router.push('/animation-test');
```

---

## Examples

### Example 1: Animated Button with Counter
```tsx
function MyComponent() {
  const [count, setCount] = useState(0);

  return (
    <View>
      <AnimatedCounter value={count} />
      <AnimatedButton
        title="Increment"
        onPress={() => setCount(count + 1)}
        variant="primary"
      />
    </View>
  );
}
```

### Example 2: Staggered List
```tsx
function MyList() {
  const items = ['Alpha', 'Beta', 'Gamma'];

  return (
    <View>
      {items.map((item, index) => (
        <AnimatedListItem
          key={item}
          index={index}
          onPress={() => console.log(item)}
        >
          <Text>{item}</Text>
        </AnimatedListItem>
      ))}
    </View>
  );
}
```

### Example 3: Progress Bar with Controls
```tsx
function MyProgress() {
  const [progress, setProgress] = useState(0.5);

  return (
    <View>
      <AnimatedProgressBar
        progress={progress}
        color={theme.colors.brand.primary}
        showLabel
      />
      <AnimatedButton
        title="50%"
        onPress={() => setProgress(0.5)}
        variant="secondary"
      />
    </View>
  );
}
```

---

## Troubleshooting

### Animation not working?
1. Check ότι έχεις `react-native-reanimated` installed
2. Check ότι έχεις `babel.config.js` με `react-native-reanimated/plugin`
3. Restart Metro bundler

### Performance issues?
1. Use `useAnimatedStyle` instead of `StyleSheet`
2. Avoid complex calculations in animations
3. Use `runOnJS` για JavaScript functions

### Staggered animations not working?
1. Check ότι έχεις unique `key` prop
2. Check ότι έχεις correct `index` prop
3. Check ότι έχεις correct `delay` prop

---

## Resources

- [React Native Reanimated Docs](https://docs.swmansion.com/react-native-reanimated/)
- [Animation Presets](./AnimationPresets.ts)
- [Animation Test Screen](../app/animation-test.tsx)

---

**Happy Animating! 🎨✨**

