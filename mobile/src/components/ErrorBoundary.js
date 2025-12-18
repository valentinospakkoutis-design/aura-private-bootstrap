import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { 
      hasError: false, 
      error: null,
      errorInfo: null
    };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ errorInfo });
    
    // In production, you might want to log this to an error reporting service
    // e.g., Sentry, LogRocket, etc.
    if (!__DEV__) {
      // TODO: Send to error reporting service
      // errorReportingService.logError(error, errorInfo);
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  handleReload = () => {
    // Force app reload (if possible)
    if (typeof window !== 'undefined' && window.location) {
      window.location.reload();
    } else {
      this.handleReset();
    }
  };

  render() {
    if (this.state.hasError) {
      return (
        <ScrollView 
          style={styles.container}
          contentContainerStyle={styles.contentContainer}
        >
          <View style={styles.content}>
            <Text style={styles.emoji}>😕</Text>
            <Text style={styles.title}>Κάτι πήγε στραβά</Text>
            <Text style={styles.message}>
              Συνέβη ένα σφάλμα. Παρακαλώ δοκιμάστε ξανά.
            </Text>
            
            {__DEV__ && this.state.error && (
              <View style={styles.errorBox}>
                <Text style={styles.errorTitle}>Error Details (Dev Only):</Text>
                <Text style={styles.errorDetails}>
                  {this.state.error.toString()}
                </Text>
                {this.state.errorInfo && (
                  <Text style={styles.errorStack}>
                    {this.state.errorInfo.componentStack}
                  </Text>
                )}
              </View>
            )}
            
            <View style={styles.buttonGroup}>
              <TouchableOpacity
                style={[styles.button, styles.buttonPrimary]}
                onPress={this.handleReset}
              >
                <Text style={styles.buttonText}>Δοκιμάστε Ξανά</Text>
              </TouchableOpacity>
              
              <TouchableOpacity
                style={[styles.button, styles.buttonSecondary]}
                onPress={this.handleReload}
              >
                <Text style={styles.buttonTextSecondary}>Επαναφόρτωση</Text>
              </TouchableOpacity>
            </View>
          </View>
        </ScrollView>
      );
    }

    return this.props.children;
  }
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0f0f',
  },
  contentContainer: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 20,
  },
  content: {
    alignItems: 'center',
  },
  emoji: {
    fontSize: 64,
    marginBottom: 20,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#fff',
    marginBottom: 10,
    textAlign: 'center',
  },
  message: {
    fontSize: 16,
    color: '#999',
    textAlign: 'center',
    marginBottom: 20,
    lineHeight: 22,
  },
  errorBox: {
    backgroundColor: '#1a1a1a',
    borderRadius: 8,
    padding: 16,
    marginBottom: 20,
    width: '100%',
    borderWidth: 1,
    borderColor: '#2a2a2a',
  },
  errorTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#ff6b6b',
    marginBottom: 8,
  },
  errorDetails: {
    fontSize: 11,
    color: '#999',
    fontFamily: 'monospace',
    marginBottom: 8,
  },
  errorStack: {
    fontSize: 10,
    color: '#666',
    fontFamily: 'monospace',
    marginTop: 8,
  },
  buttonGroup: {
    width: '100%',
    gap: 12,
  },
  button: {
    paddingHorizontal: 24,
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonPrimary: {
    backgroundColor: '#4CAF50',
  },
  buttonSecondary: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#4CAF50',
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  buttonTextSecondary: {
    color: '#4CAF50',
    fontSize: 16,
    fontWeight: 'bold',
  },
});

export default ErrorBoundary;

