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
- `progress`: number - Progress value (0-1) (required)
- `color`: string - Progress bar color (default: theme.colors.brand.primary)
- `backgroundColor`: string - Track background color (default: theme.colors.ui.border)
- `height`: number - Bar height in pixels (default: 8)
- `showLabel`: boolean - Show percentage label below bar (default: false)
- `animated`: boolean - Enable smooth spring animations (default: true)

**Features:**
- ✅ Smooth progress animations (spring physics)
- ✅ Customizable colors (fill & background)
- ✅ Optional percentage label
- ✅ Configurable height
- ✅ Rounded corners
- ✅ Spring animation for natural feel

**Note:** Το `progress` πρέπει να είναι μεταξύ 0 και 1. Το label δείχνει το rounded percentage (π.χ., 75% για progress 0.75).

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
import { SkeletonLoader, SkeletonCard, SkeletonList } from '@/components/ui/SkeletonLoader';

// Single skeleton
<SkeletonLoader width="100%" height={20} />

// Predefined card skeleton
<SkeletonCard />

// List of skeletons
<SkeletonList count={5} />
```

**SkeletonLoader Props:**
- `width`: string | number - Skeleton width (default: "100%")
- `height`: number - Skeleton height (default: 20)
- `borderRadius`: number - Border radius (default: theme.borderRadius.medium)
- `style`: ViewStyle - Custom style

**SkeletonCard Props:**
- No props - Predefined card skeleton with title, lines, and button

**SkeletonList Props:**
- `count`: number - Number of skeleton cards to render (default: 5)

**Features:**
- ✅ Shimmer animation (continuous loop)
- ✅ Customizable dimensions
- ✅ Predefined card skeleton
- ✅ List of skeletons support
- ✅ Smooth opacity animation (0.3 → 0.6 → 0.3)
- ✅ 1.5s animation duration

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
- `onDelete`: () => void - Delete handler (optional, card is swipeable even without handler)
- `deleteText`: string - Delete button text (default: "Διαγραφή")
- `children`: ReactNode - Card content

**Features:**
- ✅ Swipe-to-delete gesture (left swipe only)
- ✅ Smooth swipe animations (spring physics)
- ✅ Customizable delete text
- ✅ Haptic feedback on delete
- ✅ Swipe threshold (30% of screen width)
- ✅ Auto-snap back if threshold not reached
- ✅ Built-in card styling
- ✅ Delete background indicator

**Behavior:**
- Swipe left to reveal delete button
- Swipe threshold: 30% of screen width
- If threshold reached: card animates out and `onDelete` is called
- If threshold not reached: card snaps back with spring animation
- Haptic feedback on successful delete

---

### 8. **PageTransition**
Page transition wrapper για smooth screen transitions.

**Usage:**
```tsx
import { PageTransition } from '@/components/ui/PageTransition';
// Or relative path:
// import { PageTransition } from '../mobile/src/components/PageTransition';

export default function MyScreen() {
  return (
    <PageTransition type="fade">
      <View>
        <Text>Screen Content</Text>
      </View>
    </PageTransition>
  );
}
```

**Props:**
- `type`: 'fade' | 'slide' | 'scale' | 'slideUp' (default: 'fade')
- `children`: ReactNode - Screen content

**Animation Types:**
- `fade`: Fades in (default)
- `slide`: Slides from right
- `slideUp`: Slides up from bottom
- `scale`: Scales from 0.9 to 1

**Features:**
- ✅ Smooth page transitions
- ✅ Multiple transition types
- ✅ Consistent animations
- ✅ Spring physics for natural feel
- ✅ 400ms fade duration
- ✅ Full screen container (flex: 1)

**Note:** Χρησιμοποίησε το PageTransition ως wrapper για κάθε screen για consistent transitions. Το component έχει built-in `flex: 1` container.

---

## Animation Presets

Το AURA χρησιμοποιεί **AnimationPresets** για consistent animations across the app.

### Import
```tsx
import { ANIMATION_PRESETS } from '@/utils/AnimationPresets';
// Or relative path:
// import { ANIMATION_PRESETS } from '../mobile/src/utils/AnimationPresets';
```

### Timing Presets
```tsx
ANIMATION_PRESETS.timing.fast      // 200ms
ANIMATION_PRESETS.timing.normal    // 400ms (default)
ANIMATION_PRESETS.timing.slow       // 600ms
ANIMATION_PRESETS.timing.verySlow   // 1000ms
```

**Usage:**
```tsx
withTiming(value, {
  duration: ANIMATION_PRESETS.timing.normal,
  easing: ANIMATION_PRESETS.easing.easeOut,
});
```

### Spring Presets
```tsx
ANIMATION_PRESETS.spring.gentle    // Smooth & natural (damping: 20, stiffness: 90)
ANIMATION_PRESETS.spring.bouncy     // Playful bounce (damping: 10, stiffness: 100)
ANIMATION_PRESETS.spring.stiff      // Quick & snappy (damping: 15, stiffness: 300)
ANIMATION_PRESETS.spring.slow       // Slow animation (damping: 30, stiffness: 50)
```

**Usage:**
```tsx
withSpring(value, ANIMATION_PRESETS.spring.gentle);
```

### Easing Presets
```tsx
ANIMATION_PRESETS.easing.easeIn     // Ease in
ANIMATION_PRESETS.easing.easeOut    // Ease out (most common)
ANIMATION_PRESETS.easing.easeInOut  // Ease in-out
ANIMATION_PRESETS.easing.linear     // Linear (constant speed)
ANIMATION_PRESETS.easing.bounce     // Bounce effect
ANIMATION_PRESETS.easing.elastic    // Elastic effect
ANIMATION_PRESETS.easing.back       // Back effect (overshoot)
ANIMATION_PRESETS.easing.bezier     // Custom bezier curve
```

**Usage:**
```tsx
withTiming(value, {
  duration: 400,
  easing: ANIMATION_PRESETS.easing.easeOut,
});
```

### Common Animation Configs
```tsx
ANIMATION_PRESETS.configs.fadeIn    // { duration: 400, easing: Easing.out(Easing.cubic) }
ANIMATION_PRESETS.configs.slideIn   // { damping: 20, stiffness: 90 }
ANIMATION_PRESETS.configs.scaleIn   // { damping: 15, stiffness: 100 }
ANIMATION_PRESETS.configs.button    // { damping: 15, stiffness: 300 }
```

**Usage:**
```tsx
// For timing animations
withTiming(value, ANIMATION_PRESETS.configs.fadeIn);

// For spring animations
withSpring(value, ANIMATION_PRESETS.configs.slideIn);
```

### Helper Functions
```tsx
import { getStaggerDelay, interpolateColor } from '@/utils/AnimationPresets';

// Calculate stagger delay for list items
const delay = getStaggerDelay(index, 100); // index * 100ms

// Interpolate colors
const color = interpolateColor(progress, [0, 1], ['#000', '#fff']);
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
// ✅ Good - Smooth animated counter
<AnimatedCounter value={balance} prefix="$" decimals={2} />

// ✅ Good - With suffix
<AnimatedCounter value={percentage} suffix="%" decimals={1} />

// ✅ Good - Custom duration
<AnimatedCounter value={count} duration={500} />

// ❌ Bad - No animation
<Text>${balance.toFixed(2)}</Text>
```

---

## Performance Tips

1. **Use `useSharedValue`** instead of `useState` for animated values
   ```tsx
   // ✅ Good - runs on UI thread
   const translateX = useSharedValue(0);
   
   // ❌ Bad - causes re-renders
   const [translateX, setTranslateX] = useState(0);
   ```

2. **Use `useAnimatedStyle`** instead of inline styles
   ```tsx
   // ✅ Good - optimized for animations
   const animatedStyle = useAnimatedStyle(() => ({
     transform: [{ translateX: translateX.value }],
   }));
   
   // ❌ Bad - causes re-renders
   <View style={{ transform: [{ translateX }] }} />
   ```

3. **Avoid animating layout properties** (width, height, padding) - prefer transforms
   ```tsx
   // ✅ Good - transforms are GPU-accelerated
   transform: [{ scale: scale.value }, { translateX: x.value }]
   
   // ❌ Bad - layout animations are expensive
   width: width.value, height: height.value
   ```

4. **Use `FlatList`** with `getItemLayout` for large lists
   ```tsx
   <FlatList
     data={items}
     getItemLayout={(data, index) => ({
       length: ITEM_HEIGHT,
       offset: ITEM_HEIGHT * index,
       index,
     })}
     renderItem={({ item, index }) => (
       <AnimatedListItem index={index} item={item} />
     )}
   />
   ```

5. **Memoize components** that don't need to re-render
   ```tsx
   const MemoizedItem = React.memo(({ item }) => (
     <AnimatedCard>
       <ItemContent item={item} />
     </AnimatedCard>
   ));
   ```

6. **Test on real devices**, not just simulators
   - Real devices show actual performance
   - Simulators can be misleading
   - Test on low-end devices too

7. **Use `runOnJS`** for JavaScript functions in animations
   ```tsx
   // ✅ Good - runs JS function on JS thread
   runOnJS(handleAnimationComplete)();
   
   // ❌ Bad - can block UI thread
   handleAnimationComplete();
   ```

8. **Use `withSpring`** for natural animations
   ```tsx
   // ✅ Good - feels natural
   withSpring(value, ANIMATION_PRESETS.spring.gentle);
   
   // ❌ Bad - can feel robotic
   withTiming(value, { duration: 300 });
   ```

9. **Limit concurrent animations**
   - Too many animations at once can cause jank
   - Use staggered animations instead
   - Consider reducing animation complexity on low-end devices

10. **Use `cancelAnimation`** to stop animations early
    ```tsx
    const cancelAnimation = () => {
      cancelAnimation(translateX);
    };
    ```

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

