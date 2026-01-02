import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { AnimatedButton } from '../mobile/src/components/AnimatedButton';
import { AnimatedCard } from '../mobile/src/components/AnimatedCard';
import { AnimatedCounter } from '../mobile/src/components/AnimatedCounter';
import { AnimatedProgressBar } from '../mobile/src/components/AnimatedProgressBar';
import { SkeletonLoader, SkeletonCard } from '../mobile/src/components/SkeletonLoader';
import { SwipeableCard } from '../mobile/src/components/SwipeableCard';
import { AnimatedListItem } from '../mobile/src/components/AnimatedListItem';
import { PageTransition } from '../mobile/src/components/PageTransition';
import { theme } from '../mobile/src/constants/theme';
import { useAppStore } from '../mobile/src/stores/appStore';

export default function AnimationTestScreen() {
  const { showToast } = useAppStore();
  const [counter, setCounter] = useState(1000);
  const [progress, setProgress] = useState(0.5);

  return (
    <PageTransition type="slideUp">
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Text style={styles.title}>🎨 Animation Test Lab</Text>

        {/* Animated Buttons */}
        <AnimatedCard delay={0} animationType="slideUp">
          <Text style={styles.sectionTitle}>Animated Buttons</Text>
          <AnimatedButton
            title="Primary Button"
            onPress={() => showToast('Primary clicked!', 'success')}
            variant="primary"
            size="medium"
            fullWidth
            style={styles.button}
          />
          <AnimatedButton
            title="Secondary Button"
            onPress={() => showToast('Secondary clicked!', 'info')}
            variant="secondary"
            size="medium"
            fullWidth
            style={styles.button}
          />
          <AnimatedButton
            title="Gradient Button"
            onPress={() => showToast('Gradient clicked!', 'success')}
            variant="gradient"
            size="medium"
            fullWidth
            style={styles.button}
          />
          <AnimatedButton
            title="Danger Button"
            onPress={() => showToast('Danger clicked!', 'error')}
            variant="danger"
            size="medium"
            fullWidth
            style={styles.button}
          />
        </AnimatedCard>

        {/* Animated Counter */}
        <AnimatedCard delay={100} animationType="slideUp">
          <Text style={styles.sectionTitle}>Animated Counter</Text>
          <View style={styles.counterContainer}>
            <AnimatedCounter
              value={counter}
              decimals={2}
              prefix="$"
              style={styles.counterValue}
            />
          </View>
          <View style={styles.counterButtons}>
            <AnimatedButton
              title="+100"
              onPress={() => setCounter((prev) => prev + 100)}
              variant="primary"
              size="small"
            />
            <AnimatedButton
              title="+1000"
              onPress={() => setCounter((prev) => prev + 1000)}
              variant="primary"
              size="small"
            />
            <AnimatedButton
              title="Reset"
              onPress={() => setCounter(0)}
              variant="secondary"
              size="small"
            />
          </View>
        </AnimatedCard>

        {/* Animated Progress Bar */}
        <AnimatedCard delay={200} animationType="slideUp">
          <Text style={styles.sectionTitle}>Animated Progress Bar</Text>
          <AnimatedProgressBar
            progress={progress}
            color={theme.colors.brand.primary}
            height={12}
            showLabel
            animated
          />
          <View style={styles.progressButtons}>
            <AnimatedButton
              title="0%"
              onPress={() => setProgress(0)}
              variant="secondary"
              size="small"
            />
            <AnimatedButton
              title="50%"
              onPress={() => setProgress(0.5)}
              variant="secondary"
              size="small"
            />
            <AnimatedButton
              title="100%"
              onPress={() => setProgress(1)}
              variant="secondary"
              size="small"
            />
          </View>
        </AnimatedCard>

        {/* Skeleton Loaders */}
        <AnimatedCard delay={300} animationType="slideUp">
          <Text style={styles.sectionTitle}>Skeleton Loaders</Text>
          <SkeletonLoader width="100%" height={20} style={styles.skeleton} />
          <SkeletonLoader width="80%" height={20} style={styles.skeleton} />
          <SkeletonLoader width="60%" height={20} style={styles.skeleton} />
        </AnimatedCard>

        {/* Swipeable Cards */}
        <Text style={styles.sectionTitle}>Swipeable Cards (Swipe Left)</Text>
        {[1, 2, 3].map((item, index) => (
          <SwipeableCard
            key={item}
            onDelete={() => showToast(`Card ${item} deleted!`, 'success')}
            deleteText="Διαγραφή"
          >
            <View style={styles.swipeableContent}>
              <Text style={styles.swipeableTitle}>Swipeable Card {item}</Text>
              <Text style={styles.swipeableDescription}>
                Swipe left to delete this card
              </Text>
            </View>
          </SwipeableCard>
        ))}

        {/* Animated List Items */}
        <Text style={styles.sectionTitle}>Animated List Items (Staggered)</Text>
        {['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon'].map((item, index) => (
          <AnimatedListItem
            key={item}
            index={index}
            onPress={() => showToast(`${item} clicked!`, 'info')}
          >
            <View style={styles.listItem}>
              <Text style={styles.listItemText}>{item}</Text>
              <Text style={styles.listItemArrow}>→</Text>
            </View>
          </AnimatedListItem>
        ))}

        <View style={styles.bottomPadding} />
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
    paddingBottom: theme.spacing.xl * 2,
  },
  title: {
    fontSize: theme.typography.sizes['3xl'],
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xl,
    textAlign: 'center',
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
    marginTop: theme.spacing.md,
  },
  button: {
    marginBottom: theme.spacing.sm,
  },
  counterContainer: {
    alignItems: 'center',
    paddingVertical: theme.spacing.xl,
    backgroundColor: theme.colors.ui.background,
    borderRadius: theme.borderRadius.large,
    marginBottom: theme.spacing.md,
  },
  counterValue: {
    fontSize: 48,
    fontWeight: '700',
    color: theme.colors.brand.primary,
  },
  counterButtons: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    gap: theme.spacing.sm,
  },
  progressButtons: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    gap: theme.spacing.sm,
    marginTop: theme.spacing.md,
  },
  skeleton: {
    marginBottom: theme.spacing.sm,
  },
  swipeableContent: {
    padding: theme.spacing.md,
  },
  swipeableTitle: {
    fontSize: theme.typography.sizes.lg,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xs,
  },
  swipeableDescription: {
    fontSize: theme.typography.sizes.sm,
    color: theme.colors.text.secondary,
  },
  listItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: theme.colors.ui.cardBackground,
    padding: theme.spacing.lg,
    borderRadius: theme.borderRadius.large,
  },
  listItemText: {
    fontSize: theme.typography.sizes.md,
    fontWeight: '600',
    color: theme.colors.text.primary,
  },
  listItemArrow: {
    fontSize: 18,
    color: theme.colors.text.secondary,
  },
  bottomPadding: {
    height: theme.spacing.xl,
  },
});

