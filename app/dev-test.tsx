import React, { useState } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { Button } from '../mobile/src/components/Button';
import { useAppStore } from '../mobile/src/stores/appStore';
import { ApiTester } from '../mobile/src/utils/ApiTester';
import { theme } from '../mobile/src/constants/theme';

interface TestResultProps {
  label: string;
  passed: boolean;
}

const TestResult: React.FC<TestResultProps> = ({ label, passed }) => (
  <View style={styles.testResult}>
    <Text style={styles.testLabel}>{label}:</Text>
    <View style={[styles.statusBadge, { backgroundColor: passed ? theme.colors.semantic.success + '20' : theme.colors.semantic.error + '20' }]}>
      <Text style={[styles.statusText, { color: passed ? theme.colors.semantic.success : theme.colors.semantic.error }]}>
        {passed ? '✓ Pass' : '✗ Fail'}
      </Text>
    </View>
  </View>
);

export default function DevTestScreen() {
  const { showToast, showModal } = useAppStore();
  const [testResults, setTestResults] = useState<any>(null);
  const [testing, setTesting] = useState(false);

  const runTests = async () => {
    setTesting(true);
    showToast('Running tests...', 'info');
    
    try {
      const results = await ApiTester.runAllTests();
      setTestResults(results);
      
      const allPassed = Object.values(results).every((v) => v === true);
      showToast(
        allPassed ? 'All tests passed! ✅' : 'Some tests failed ❌',
        allPassed ? 'success' : 'error'
      );
    } catch (error) {
      console.error('Test error:', error);
      showToast('Test execution failed', 'error');
    } finally {
      setTesting(false);
    }
  };

  const testToast = (type: 'success' | 'error' | 'warning' | 'info') => {
    showToast(`This is a ${type} toast!`, type);
  };

  const testModal = () => {
    showModal(
      'Test Modal',
      'This is a test modal. Do you want to proceed?',
      () => {
        showToast('Modal confirmed!', 'success');
      }
    );
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>🧪 Development Testing</Text>

      {/* API Tests */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>API Tests</Text>
        <Button
          title="Run All API Tests"
          onPress={runTests}
          variant="primary"
          size="medium"
          fullWidth
          loading={testing}
        />

        {testResults && (
          <View style={styles.results}>
            <TestResult label="Connection" passed={testResults.connection} />
            <TestResult label="Auth" passed={testResults.auth} />
            <TestResult label="Predictions" passed={testResults.predictions} />
            <TestResult label="Brokers" passed={testResults.brokers} />
          </View>
        )}
      </View>

      {/* Toast Tests */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Toast Tests</Text>
        <View style={styles.buttonRow}>
          <Button
            title="Success Toast"
            onPress={() => testToast('success')}
            variant="primary"
            size="small"
            style={styles.button}
          />
          <Button
            title="Error Toast"
            onPress={() => testToast('error')}
            variant="danger"
            size="small"
            style={styles.button}
          />
        </View>
        <View style={styles.buttonRow}>
          <Button
            title="Warning Toast"
            onPress={() => testToast('warning')}
            variant="secondary"
            size="small"
            style={styles.button}
          />
          <Button
            title="Info Toast"
            onPress={() => testToast('info')}
            variant="ghost"
            size="small"
            style={styles.button}
          />
        </View>
      </View>

      {/* Modal Tests */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Modal Tests</Text>
        <Button
          title="Show Test Modal"
          onPress={testModal}
          variant="secondary"
          size="medium"
          fullWidth
        />
      </View>

      {/* Info */}
      <View style={styles.infoSection}>
        <Text style={styles.infoText}>
          This screen is for development testing only. Use it to test API connectivity, Toast notifications, and Modal dialogs.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.ui.background,
  },
  content: {
    padding: theme.spacing.lg,
  },
  title: {
    fontSize: theme.typography.sizes['3xl'],
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.xl,
    textAlign: 'center',
  },
  section: {
    backgroundColor: theme.colors.ui.cardBackground,
    borderRadius: theme.borderRadius.xl,
    padding: theme.spacing.lg,
    marginBottom: theme.spacing.lg,
  },
  sectionTitle: {
    fontSize: theme.typography.sizes.xl,
    fontWeight: '700',
    color: theme.colors.text.primary,
    marginBottom: theme.spacing.md,
  },
  buttonRow: {
    flexDirection: 'row',
    gap: theme.spacing.sm,
    marginBottom: theme.spacing.sm,
  },
  button: {
    flex: 1,
  },
  results: {
    marginTop: theme.spacing.md,
    gap: theme.spacing.sm,
  },
  testResult: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: theme.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.ui.border,
  },
  testLabel: {
    fontSize: theme.typography.sizes.md,
    color: theme.colors.text.primary,
    fontWeight: '600',
  },
  statusBadge: {
    paddingHorizontal: theme.spacing.md,
    paddingVertical: theme.spacing.xs,
    borderRadius: theme.borderRadius.medium,
  },
  statusText: {
    fontSize: theme.typography.sizes.sm,
    fontWeight: '700',
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

