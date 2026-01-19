/**
 * Frontend URL Validation and Normalization
 * Mirrors backend validation logic for real-time feedback
 */

// Allowed URL schemes
const ALLOWED_SCHEMES = ['http', 'https']

// Blocked patterns (security)
const BLOCKED_PATTERNS = [
  /javascript:/i,
  /data:/i,
  /vbscript:/i,
  /file:/i,
  /about:/i,
]

/**
 * Normalize URL by adding https:// if missing scheme
 */
export function normalizeUrl(url) {
  if (!url || typeof url !== 'string') {
    return null
  }

  const trimmed = url.trim()
  if (!trimmed) {
    return null
  }

  // Check for blocked patterns
  for (const pattern of BLOCKED_PATTERNS) {
    if (pattern.test(trimmed)) {
      return null
    }
  }

  // Already has scheme
  if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
    try {
      const urlObj = new URL(trimmed)
      if (!ALLOWED_SCHEMES.includes(urlObj.protocol.replace(':', ''))) {
        return null
      }
      // Normalize to https for security
      if (urlObj.protocol === 'http:') {
        urlObj.protocol = 'https:'
      }
      return urlObj.toString()
    } catch {
      return null
    }
  }

  // Protocol-relative URL (//example.com)
  if (trimmed.startsWith('//')) {
    try {
      const urlObj = new URL(`https:${trimmed}`)
      return urlObj.toString()
    } catch {
      return null
    }
  }

  // No scheme - add https://
  try {
    const urlObj = new URL(`https://${trimmed}`)
    if (!urlObj.hostname) {
      return null
    }
    return urlObj.toString()
  } catch {
    return null
  }
}

/**
 * Validate URL and return { isValid, error, normalizedUrl }
 */
export function validateUrl(url) {
  if (!url || typeof url !== 'string') {
    return { isValid: false, error: 'URL is required', normalizedUrl: null }
  }

  const trimmed = url.trim()
  if (!trimmed) {
    return { isValid: false, error: 'URL cannot be empty', normalizedUrl: null }
  }

  // Normalize URL
  const normalized = normalizeUrl(trimmed)
  if (!normalized) {
    return {
      isValid: false,
      error: 'Invalid URL format. Please enter a valid URL (e.g., linkedin.com/in/yourprofile)',
      normalizedUrl: null,
    }
  }

  // Parse normalized URL to validate
  try {
    const urlObj = new URL(normalized)

    // Must have hostname (domain)
    if (!urlObj.hostname) {
      return { isValid: false, error: 'Invalid URL: missing domain', normalizedUrl: null }
    }

    // Must use allowed scheme
    if (!ALLOWED_SCHEMES.includes(urlObj.protocol.replace(':', ''))) {
      return {
        isValid: false,
        error: 'Invalid URL scheme. Only http:// and https:// are allowed',
        normalizedUrl: null,
      }
    }

    // Domain must be valid
    const domainParts = urlObj.hostname.split('.')
    if (domainParts.length < 2 || domainParts.some(part => !part)) {
      return { isValid: false, error: 'Invalid URL: invalid domain name', normalizedUrl: null }
    }

    // Success
    return { isValid: true, error: null, normalizedUrl: normalized }
  } catch (e) {
    return {
      isValid: false,
      error: 'Invalid URL format. Please check your URL and try again.',
      normalizedUrl: null,
    }
  }
}

/**
 * Auto-detect platform type from URL
 */
export function detectPlatformFromUrl(url) {
  if (!url) return null

  const urlLower = url.toLowerCase()

  if (urlLower.includes('linkedin.com')) {
    return 'linkedin'
  } else if (urlLower.includes('github.com')) {
    return 'github'
  } else if (
    urlLower.includes('portfolio') ||
    urlLower.includes('personal') ||
    urlLower.includes('website') ||
    urlLower.includes('site')
  ) {
    return 'portfolio'
  }

  return null
}
