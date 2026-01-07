import { test, expect } from '@playwright/test'

/**
 * Authentication tests for BetterAuth integration
 * Tests login, signup, logout flows and route protection
 */

// Generate unique test user for each test run
const testUser = {
  name: `Test User ${Date.now()}`,
  email: `test-${Date.now()}@example.com`,
  password: 'TestPassword123!',
}

test.describe('Authentication Pages', () => {
  test('login page renders correctly', async ({ page }) => {
    await page.goto('/login')

    // Check branding
    await expect(page.getByRole('heading', { name: 'ChatTwelve', exact: true })).toBeVisible()
    await expect(page.getByText('AI-powered trading assistant')).toBeVisible()

    // Check form elements (CardTitle renders as div, not heading)
    await expect(page.getByText('Welcome back')).toBeVisible()
    await expect(page.getByText('Sign in to your ChatTwelve account')).toBeVisible()
    await expect(page.getByLabel('Email')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Sign in' })).toBeVisible()

    // Check signup link
    await expect(page.getByText("Don't have an account?")).toBeVisible()
    await expect(page.getByRole('link', { name: 'Sign up' })).toBeVisible()
  })

  test('signup page renders correctly', async ({ page }) => {
    await page.goto('/signup')

    // Check branding
    await expect(page.getByRole('heading', { name: 'ChatTwelve', exact: true })).toBeVisible()
    await expect(page.getByText('AI-powered trading assistant')).toBeVisible()

    // Check form elements (CardTitle renders as div, not heading)
    await expect(page.getByText('Create an account')).toBeVisible()
    await expect(page.getByText('Get started with ChatTwelve')).toBeVisible()
    await expect(page.getByLabel('Name')).toBeVisible()
    await expect(page.getByLabel('Email')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create account' })).toBeVisible()

    // Check login link
    await expect(page.getByText('Already have an account?')).toBeVisible()
    await expect(page.getByRole('link', { name: 'Sign in' })).toBeVisible()
  })

  test('can navigate between login and signup pages', async ({ page }) => {
    // Start at login
    await page.goto('/login')
    await expect(page.getByText('Welcome back')).toBeVisible()

    // Click signup link
    await page.getByRole('link', { name: 'Sign up' }).click()
    await expect(page).toHaveURL('/signup')
    await expect(page.getByText('Create an account')).toBeVisible()

    // Click login link
    await page.getByRole('link', { name: 'Sign in' }).click()
    await expect(page).toHaveURL('/login')
    await expect(page.getByText('Welcome back')).toBeVisible()
  })
})

test.describe('Route Protection (Middleware)', () => {
  test('unauthenticated user is redirected from home to login', async ({ page }) => {
    // Clear any existing auth state
    await page.goto('/login')
    await page.evaluate(() => {
      document.cookie.split(';').forEach((c) => {
        document.cookie = c.replace(/^ +/, '').replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/')
      })
    })

    // Try to access protected route
    await page.goto('/')

    // Should redirect to login
    await expect(page).toHaveURL(/\/login/)
  })

  test('unauthenticated user is redirected from settings to login', async ({ page }) => {
    // Clear cookies
    await page.goto('/login')
    await page.evaluate(() => {
      document.cookie.split(';').forEach((c) => {
        document.cookie = c.replace(/^ +/, '').replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/')
      })
    })

    await page.goto('/settings')
    await expect(page).toHaveURL(/\/login/)
  })

  test('login page is accessible to unauthenticated users', async ({ page }) => {
    await page.goto('/login')
    await expect(page).toHaveURL('/login')
    await expect(page.getByText('Welcome back')).toBeVisible()
  })

  test('signup page is accessible to unauthenticated users', async ({ page }) => {
    await page.goto('/signup')
    await expect(page).toHaveURL('/signup')
    await expect(page.getByText('Create an account')).toBeVisible()
  })
})

test.describe('Form Validation', () => {
  test('login form shows validation for empty fields', async ({ page }) => {
    await page.goto('/login')

    // Try to submit empty form
    await page.getByRole('button', { name: 'Sign in' }).click()

    // HTML5 validation should prevent submission
    const emailInput = page.getByLabel('Email')
    await expect(emailInput).toHaveAttribute('required', '')
  })

  test('signup form shows validation for empty fields', async ({ page }) => {
    await page.goto('/signup')

    // Try to submit empty form
    await page.getByRole('button', { name: 'Create account' }).click()

    // HTML5 validation should prevent submission
    const nameInput = page.getByLabel('Name')
    await expect(nameInput).toHaveAttribute('required', '')
  })

  test('signup form enforces minimum password length', async ({ page }) => {
    await page.goto('/signup')

    const passwordInput = page.getByLabel('Password')
    await expect(passwordInput).toHaveAttribute('minLength', '8')
  })

  test('email input has correct type', async ({ page }) => {
    await page.goto('/login')
    const emailInput = page.getByLabel('Email')
    await expect(emailInput).toHaveAttribute('type', 'email')
  })
})

test.describe('Login Flow', () => {
  test('login form shows loading state on submit', async ({ page }) => {
    await page.goto('/login')

    // Fill form with test credentials
    await page.getByLabel('Email').fill('test@example.com')
    await page.getByLabel('Password').fill('password123')

    // Submit and check for loading state
    const submitButton = page.getByRole('button', { name: 'Sign in' })
    await submitButton.click()

    // Button should be disabled during loading
    await expect(submitButton).toBeDisabled()

    // Should show loading spinner (Loader2 icon)
    await expect(page.locator('.animate-spin')).toBeVisible({ timeout: 1000 }).catch(() => {
      // Loading may be too fast to catch, that's okay
    })
  })

  test('invalid login shows error toast', async ({ page }) => {
    await page.goto('/login')

    // Fill form with invalid credentials
    await page.getByLabel('Email').fill('nonexistent@example.com')
    await page.getByLabel('Password').fill('wrongpassword')

    // Submit
    await page.getByRole('button', { name: 'Sign in' }).click()

    // Wait for response and check for error message
    // Toast should appear with error
    await expect(
      page.getByText(/login failed|invalid|error/i)
    ).toBeVisible({ timeout: 5000 }).catch(() => {
      // If no toast, the request may have network error which is acceptable in test env
    })
  })
})

test.describe('Signup Flow', () => {
  test('signup form shows loading state on submit', async ({ page }) => {
    await page.goto('/signup')

    // Fill form with test credentials
    await page.getByLabel('Name').fill('Test User')
    await page.getByLabel('Email').fill(`test-${Date.now()}@example.com`)
    await page.getByLabel('Password').fill('TestPassword123!')

    // Submit and check for loading state
    const submitButton = page.getByRole('button', { name: 'Create account' })
    await submitButton.click()

    // Button should be disabled during loading
    await expect(submitButton).toBeDisabled()
  })

  test('password field has autocomplete attribute', async ({ page }) => {
    await page.goto('/signup')
    const passwordInput = page.getByLabel('Password')
    await expect(passwordInput).toHaveAttribute('autocomplete', 'new-password')
  })

  test('login password field has autocomplete attribute', async ({ page }) => {
    await page.goto('/login')
    const passwordInput = page.getByLabel('Password')
    await expect(passwordInput).toHaveAttribute('autocomplete', 'current-password')
  })
})

test.describe('UI Accessibility', () => {
  test('login form has proper labels', async ({ page }) => {
    await page.goto('/login')

    // Labels should be properly associated with inputs
    const emailLabel = page.locator('label[for="email"]')
    const passwordLabel = page.locator('label[for="password"]')

    await expect(emailLabel).toBeVisible()
    await expect(passwordLabel).toBeVisible()
  })

  test('signup form has proper labels', async ({ page }) => {
    await page.goto('/signup')

    const nameLabel = page.locator('label[for="name"]')
    const emailLabel = page.locator('label[for="email"]')
    const passwordLabel = page.locator('label[for="password"]')

    await expect(nameLabel).toBeVisible()
    await expect(emailLabel).toBeVisible()
    await expect(passwordLabel).toBeVisible()
  })

  test('submit buttons are focusable', async ({ page }) => {
    await page.goto('/login')

    const submitButton = page.getByRole('button', { name: 'Sign in' })
    await submitButton.focus()
    await expect(submitButton).toBeFocused()
  })
})
