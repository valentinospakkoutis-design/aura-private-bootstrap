import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { AnimatedButton } from '../mobile/src/components/AnimatedButton';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { AnimatedCounter } from '../mobile/src/components/AnimatedCounter';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { SkeletonLoader, SkeletonCard } from '../mobile/src/components/SkeletonLoader';
import { SwipeableCard } from '../mobile/src/components/SwipeableCard';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { theme } from '../mobile/src/constants/theme';
import { useAppStore } from '../mobile/src/stores/appStore';

export default function AnimationTestScreen() {
  const { showToast } = useAppStore();
  const [counter, setCounter] = useState(0);
  const [progress, setProgress] = useState(0.5);

  return (
    <PageTransition type="slideUp">
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Text style={styles.title}>🎬 Animation Test Screen</Text>

        {/* Animated Button */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Animated Button</Text>
          <AnimatedButton
            title="Press Me"
            onPress={() => {
              setCounter(counter + 1);
              showToast('Button pressed!', 'success');
            }}
            variant="primary"
            size="medium"
            fullWidth
          />
        </View>

        {/* Animated Card */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Animated Card</Text>
          <AnimatedCard delay={0} animationType="slideUp">
            <Text style={styles.cardText}>This is an animated card with slideUp animation</Text>
          </AnimatedCard>
          <AnimatedCard delay={100} animationType="fade">
            <Text style={styles.cardText}>This is an animated card with fade animation</Text>
          </AnimatedCard>
          <AnimatedCard delay={200} animationType="scale">
            <Text style={styles.cardText}>This is an animated card with scale animation</Text>
          </AnimatedCard>
        </View>

        {/* Animated Counter */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Animated Counter</Text>
          <View style={styles.counterContainer}>
            <AnimatedCounter
              value={counter}
              prefix="Count: "
              duration={500}
              style={styles.counterText}
            />
          </View>
          <AnimatedButton
            title="Increment Counter"
            onPress={() => setCounter(counter + 1)}
            variant="secondary"
            size="small"
            fullWidth
          />
        </View>

        {/* Animated Progress Bar */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Animated Progress Bar</Text>
          <AnimatedProgressBar
            progress={progress}
            color={theme.colors.brand.primary}
            height={12}
            showLabel={true}
          />
          <View style={styles.progressControls}>
            <AnimatedButton
              title="0%"
              onPress={() => setProgress(0)}
              variant="ghost"
              size="small"
            />
            <AnimatedButton
              title="50%"
              onPress={() => setProgress(0.5)}
              variant="ghost"
              size="small"
            />
            <AnimatedButton
              title="100%"
              onPress={() => setProgress(1)}
              variant="ghost"
              size="small"
            />
          </View>
        </View>

        {/* Skeleton Loader */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Skeleton Loader</Text>
          <SkeletonLoader width="100%" height={40} />
          <SkeletonLoader width="80%" height={20} style={styles.skeletonMargin} />
          <SkeletonLoader width="60%" height={20} style={styles.skeletonMargin} />
          <SkeletonCard />
        </View>

        {/* Swipeable Card */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Swipeable Card</Text>
          <SwipeableCard
            onDelete={() => {
              showToast('Card deleted!', 'success');
            }}
            deleteText="Διαγραφή"
          >
            <Text style={styles.cardText}>Swipe left to delete this card</Text>
          </SwipeableCard>
        </View>

        {/* Info */}
        <View style={styles.infoSection}>
          <Text style={styles.infoText}>
            This screen is for testing all animated components. Use it to verify animations work correctly.
          </Text>
        </View>
      </ScrollView>
    </PageTransition>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    padding: theme.spacing.md,
  },
  title: {
    fontSize: theme.typography.sizes['3xl'],
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xl,
    textAlign: 'center',
  },
  section: {
    marginBottom: theme.spacing.xl,
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  cardText: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
  },
  counterContainer: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.md,
    alignItems: 'center',
  },
  counterText: {
    fontSize: theme.typography.sizes['3xl'],
  },
  progressControls: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginTop: theme.spacing.md,
    gap: theme.spacing.sm,
  },
  skeletonMargin: {
    marginTop: theme.spacing.sm,
  },
  infoSection: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginTop: theme.spacing.md,
  },
  infoText: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
    lineHeight: 20,
    textAlign: 'center',
  },
});

