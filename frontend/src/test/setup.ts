import '@testing-library/jest-dom/vitest'

let messageId = 0

Object.defineProperty(window, 'crypto', {
  value: { randomUUID: () => `test-message-id-${messageId++}` },
})
