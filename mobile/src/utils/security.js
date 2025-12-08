// AURA Security Utilities
// Basic security functions for MVP

/**
 * Validates email format
 */
export function validateEmail(email) {
  if (!email || typeof email !== 'string') {
    return false;
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

/**
 * Validates password strength
 * Requirements: min 8 chars, 1 uppercase, 1 lowercase, 1 number
 */
export function validatePassword(password) {
  if (!password || typeof password !== 'string') {
    return { valid: false, message: 'Το password είναι υποχρεωτικό' };
  }
  
  if (password.length < 8) {
    return { valid: false, message: 'Τουλάχιστον 8 χαρακτήρες' };
  }
  
  if (!/[A-Z]/.test(password)) {
    return { valid: false, message: 'Τουλάχιστον 1 κεφαλαίο γράμμα' };
  }
  
  if (!/[a-z]/.test(password)) {
    return { valid: false, message: 'Τουλάχιστον 1 πεζό γράμμα' };
  }
  
  if (!/[0-9]/.test(password)) {
    return { valid: false, message: 'Τουλάχιστον 1 αριθμό' };
  }
  
  return { valid: true, message: 'Ισχυρό password' };
}

/**
 * Sanitizes user input to prevent XSS
 */
export function sanitizeInput(input) {
  if (typeof input !== 'string') return input;
  
  return input
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;');
}

/**
 * Generates a random session ID
 */
export function generateSessionId() {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Checks if app is running in secure context
 */
export function isSecureContext() {
  // In production, ensure HTTPS
  return __DEV__ || (typeof window !== 'undefined' && window.location?.protocol === 'https:');
}

/**
 * Rate limiting check (simple client-side)
 */
const requestCounts = new Map();

export function checkRateLimit(identifier, maxRequests = 10, windowMs = 60000) {
  const now = Date.now();
  const windowStart = now - windowMs;
  
  if (!requestCounts.has(identifier)) {
    requestCounts.set(identifier, []);
  }
  
  const requests = requestCounts.get(identifier);
  
  // Remove old requests outside window
  const recentRequests = requests.filter(time => time > windowStart);
  
  if (recentRequests.length >= maxRequests) {
    return {
      allowed: false,
      message: 'Πάρα πολλές προσπάθειες. Δοκιμάστε σε λίγο.'
    };
  }
  
  recentRequests.push(now);
  requestCounts.set(identifier, recentRequests);
  
  return { allowed: true };
}

/**
 * Validates API Key format (για broker connections)
 */
export function validateApiKey(apiKey) {
  if (!apiKey || typeof apiKey !== 'string') {
    return { valid: false, message: 'Μη έγκυρο API key' };
  }
  
  if (apiKey.length < 20) {
    return { valid: false, message: 'Το API key πρέπει να είναι τουλάχιστον 20 χαρακτήρες' };
  }
  
  return { valid: true };
}

/**
 * Basic encryption placeholder
 * ΣΗΜΑΝΤΙΚΟ: Στο production χρησιμοποίησε proper encryption library
 */
export function encryptData(data) {
  // TODO: Implement proper encryption with expo-crypto
  // For now, just base64 encode (NOT SECURE - placeholder only)
  if (__DEV__) {
    console.warn('⚠️ Using placeholder encryption - implement proper encryption for production');
  }
  return Buffer.from(JSON.stringify(data)).toString('base64');
}

export function decryptData(encryptedData) {
  // TODO: Implement proper decryption
  try {
    return JSON.parse(Buffer.from(encryptedData, 'base64').toString());
  } catch {
    return null;
  }
}

