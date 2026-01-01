import { api } from '../services/apiClient';
import { getApiBaseUrl } from '../config/environment';

export class ApiTester {
  static async testConnection(): Promise<boolean> {
    try {
      // Test basic connectivity - use getApiBaseUrl() to get the base URL
      const baseURL = getApiBaseUrl();
      const response = await fetch(`${baseURL}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      } as any);
      return response.ok;
    } catch (err) {
      console.error('API connection test failed:', err);
      return false;
    }
  }

  static async testAuth(): Promise<boolean> {
    try {
      await api.getProfile();
      return true;
    } catch (err) {
      console.error('Auth test failed:', err);
      return false;
    }
  }

  static async testPredictions(): Promise<boolean> {
    try {
      await api.getPredictions();
      return true;
    } catch (err) {
      console.error('Predictions test failed:', err);
      return false;
    }
  }

  static async testBrokers(): Promise<boolean> {
    try {
      await api.getBrokers();
      return true;
    } catch (err) {
      console.error('Brokers test failed:', err);
      return false;
    }
  }

  static async runAllTests(): Promise<{
    connection: boolean;
    auth: boolean;
    predictions: boolean;
    brokers: boolean;
  }> {
    const [connection, auth, predictions, brokers] = await Promise.all([
      this.testConnection(),
      this.testAuth(),
      this.testPredictions(),
      this.testBrokers(),
    ]);

    return {
      connection,
      auth,
      predictions,
      brokers,
    };
  }
}

