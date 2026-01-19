/**
 * Simple Toast Notification System
 * Provides showToast function for displaying temporary notifications
 */

let toastContainer = null
let toastTimeout = null

// Initialize toast container
function initToastContainer() {
  if (toastContainer) return toastContainer

  const container = document.createElement('div')
  container.id = 'toast-container'
  container.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 10000;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    pointer-events: none;
  `
  document.body.appendChild(container)
  toastContainer = container
  return container
}

// Show toast notification - function declaration (hoisted)
function showToast(message, type = 'success', duration = 3000) {
  initToastContainer()
  
  // Clear existing timeout
  if (toastTimeout) {
    clearTimeout(toastTimeout)
  }

  // Remove existing toast if any
  const existing = toastContainer.querySelector('.toast')
  if (existing) {
    existing.remove()
  }

  // Create toast element
  const toast = document.createElement('div')
  toast.className = `toast toast-${type}`
  toast.style.cssText = `
    background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
    color: white;
    padding: 0.875rem 1.25rem;
    border-radius: 0.5rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    font-size: 0.875rem;
    font-weight: 500;
    min-width: 250px;
    max-width: 400px;
    pointer-events: auto;
    animation: slideInRight 0.3s ease-out;
    display: flex;
    align-items: center;
    gap: 0.75rem;
  `

  // Add animation keyframes if not already added
  if (!document.getElementById('toast-animations')) {
    const style = document.createElement('style')
    style.id = 'toast-animations'
    style.textContent = `
      @keyframes slideInRight {
        from {
          transform: translateX(100%);
          opacity: 0;
        }
        to {
          transform: translateX(0);
          opacity: 1;
        }
      }
      @keyframes slideOutRight {
        from {
          transform: translateX(0);
          opacity: 1;
        }
        to {
          transform: translateX(100%);
          opacity: 0;
        }
      }
    `
    document.head.appendChild(style)
  }

  toast.textContent = message
  toastContainer.appendChild(toast)

  // Auto-remove after duration
  toastTimeout = setTimeout(() => {
    toast.style.animation = 'slideOutRight 0.3s ease-out'
    setTimeout(() => {
      if (toast.parentNode) {
        toast.remove()
      }
    }, 300)
  }, duration)

  return toast
}

// Export showToast function
export { showToast }

// Convenience functions - defined after showToast to avoid TDZ
// Use function declarations to ensure hoisting works correctly
const toastImpl = {
  success: (message, duration) => showToast(message, 'success', duration),
  error: (message, duration) => showToast(message, 'error', duration),
  info: (message, duration) => showToast(message, 'info', duration),
}

// Export after initialization to ensure showToast is available
export const toast = toastImpl
