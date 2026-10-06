// AURA Security Utilities - Test Suite
// Tests for encryption/decryption functions

// ── Mock native Expo modules (unavailable in Node/Jest CI) ───────────────────
// jest.mock() calls are hoisted to the top of the file by Babel/Jest, so they
// run before any import.  We use jest.requireMock() (not import) to get a
// reference to the mock at runtime, avoiding the import/first lint error.

// SecureStore: in-memory Map that correctly implements the async API.
jest.mock('expo-secure-store', () => {
  const store = new Map();
  return {
    _store: store, // internal handle for beforeEach cleanup
    getItemAsync: jest.fn(async (key) => store.get(key) ?? null),
    setItemAsync: jest.fn(async (key, value) => { store.set(key, value); }),
    deleteItemAsync: jest.fn(async (key) => { store.delete(key); }),
  };
});

// expo-crypto: delegate to Node's built-in `crypto` so:
//   - getRandomBytesAsync returns real random bytes (IV differs per call)
//   - digestStringAsync returns real SHA-256 hex strings
jest.mock('expo-crypto', () => {
  const nodeCrypto = require('crypto');
  return {
    CryptoDigestAlgorithm: { SHA256: 'SHA-256' },
    getRandomBytesAsync: jest.fn(async (length) => {
      const buf = nodeCrypto.randomBytes(length);
      // Return a Uint8Array that also responds to .toString('hex'),
      // mirroring the shape that security.js expects from expo-crypto.
      const arr = new Uint8Array(buf);
      arr.toString = (enc) => {
        if (enc === 'hex') return buf.toString('hex');
        return buf.toString(enc || 'utf8');
      };
      return arr;
    }),
    digestStringAsync: jest.fn(async (_algo, data) =>
      nodeCrypto.createHash('sha256').update(data).digest('hex')
    ),
  };
});

// ─────────────────────────────────────────────────────────────────────────────

import { encryptData, decryptData, storeApiKey, getApiKey, deleteApiKey } from '../security';

beforeEach(() => {
  // Clear the in-memory SecureStore between tests so the device key generated
  // during one test doesn't bleed into the next.  Within a single test,
  // encrypt and decrypt share the same device key (correct behaviour).
  // eslint-disable-next-line no-underscore-dangle
  jest.requireMock('expo-secure-store')._store.clear();
});

describe('Security Utilities', () => {
  describe('encryptData / decryptData', () => {
    it('should encrypt and decrypt simple data', async () => {
      const originalData = { apiKey: 'test-api-key-12345' };

      const encrypted = await encryptData(originalData);
      expect(encrypted).toBeDefined();
      expect(typeof encrypted).toBe('string');
      expect(encrypted).not.toBe(JSON.stringify(originalData));

      const decrypted = await decryptData(encrypted);
      expect(decrypted).toEqual(originalData);
    });

    it('should encrypt and decrypt complex data', async () => {
      const originalData = {
        apiKey: 'test-api-key-12345',
        apiSecret: 'test-secret-67890',
        broker: 'binance',
        testnet: true,
        timestamp: Date.now(),
      };

      const encrypted = await encryptData(originalData);
      const decrypted = await decryptData(encrypted);

      expect(decrypted).toEqual(originalData);
    });

    it('should produce different encrypted output for same data (due to IV)', async () => {
      const originalData = { apiKey: 'test-key' };

      const encrypted1 = await encryptData(originalData);
      const encrypted2 = await encryptData(originalData);

      // Should be different because the IV is random on each call
      expect(encrypted1).not.toBe(encrypted2);

      // But both must decrypt back to the same original data
      const decrypted1 = await decryptData(encrypted1);
      const decrypted2 = await decryptData(encrypted2);
      expect(decrypted1).toEqual(originalData);
      expect(decrypted2).toEqual(originalData);
    });

    it('should detect tampered data (HMAC verification)', async () => {
      const originalData = { apiKey: 'test-key' };
      const encrypted = await encryptData(originalData);

      // Tamper with the base64 payload
      const tampered = Buffer.from(encrypted, 'base64').toString();
      const tamperedBase64 = Buffer.from(`${tampered}tampered`).toString('base64');

      // Must fail to decrypt or return null / something != originalData
      const decrypted = await decryptData(tamperedBase64);
      expect(decrypted).not.toEqual(originalData);
    });
  });

  describe('storeApiKey / getApiKey', () => {
    const testService = 'test_broker';
    const testApiKey = 'test-api-key-1234567890';

    afterEach(async () => {
      await deleteApiKey(testService);
    });

    it('should store and retrieve API key', async () => {
      const stored = await storeApiKey(testService, testApiKey);
      expect(stored).toBe(true);

      const retrieved = await getApiKey(testService);
      expect(retrieved).toBe(testApiKey);
    });

    it('should return null for non-existent key', async () => {
      const retrieved = await getApiKey('non_existent_service');
      expect(retrieved).toBeNull();
    });

    it('should delete stored API key', async () => {
      await storeApiKey(testService, testApiKey);
      const deleted = await deleteApiKey(testService);
      expect(deleted).toBe(true);

      const retrieved = await getApiKey(testService);
      expect(retrieved).toBeNull();
    });
  });
});
