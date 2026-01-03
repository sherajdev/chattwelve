import { test, expect } from '@playwright/test'

test.describe('Smoke Tests', () => {
  test('homepage loads successfully', async ({ page }) => {
    await page.goto('/')

    // Should not show error state
    await expect(page.locator('body')).not.toContainText('Error')

    // Should eventually load (not stuck on initializing)
    await expect(page.getByText('Initializing...')).not.toBeVisible({ timeout: 10000 })
  })

  test('sidebar is visible with New Chat button', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Sidebar should have "New Chat" button with Plus icon (the main button, not session titles)
    const newChatButton = page.locator('button:has-text("New Chat")').filter({ has: page.locator('svg') }).first()
    await expect(newChatButton).toBeVisible()
  })

  test('chat input is visible and enabled', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Chat input should be visible (look for textarea or input)
    const input = page.locator('textarea, input[type="text"]').first()
    await expect(input).toBeVisible()
    await expect(input).toBeEnabled()
  })

  test('header shows health status indicators', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Header uses div with border-b - look for health indicator dots (at least 3)
    const healthDots = page.locator('.rounded-full.h-2.w-2')
    await expect(healthDots.first()).toBeVisible()

    // Should have at least 3 health indicators (API, MCP, AI)
    const count = await healthDots.count()
    expect(count).toBeGreaterThanOrEqual(3)
  })

  test('model badge is visible in header', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Wait for model info to load
    await page.waitForTimeout(3000)

    // Look for badge with model name (contains model text like gpt or loading)
    const badge = page.locator('[data-slot="badge"], span:has-text("gpt"), span:has-text("loading")').first()
    await expect(badge).toBeVisible()
  })

  test('ChatTwelve branding is visible', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Should show ChatTwelve title in sidebar (the h1 specifically)
    await expect(page.getByRole('heading', { name: 'ChatTwelve', exact: true })).toBeVisible()
  })
})

test.describe('Session Management', () => {
  test('session is created on first load', async ({ page }) => {
    // Clear any existing session
    await page.goto('/')
    await page.evaluate(() => localStorage.removeItem('chattwelve_session_id'))

    // Reload and verify session is created
    await page.reload()
    await page.waitForLoadState('networkidle')

    // Wait for session to be stored
    await page.waitForTimeout(3000)

    const sessionId = await page.evaluate(() => localStorage.getItem('chattwelve_session_id'))
    expect(sessionId).toBeTruthy()
    expect(sessionId).toMatch(/^[a-f0-9-]{36}$/) // UUID format
  })

  test('session persists across page reload', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    const sessionId1 = await page.evaluate(() => localStorage.getItem('chattwelve_session_id'))

    await page.reload()
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    const sessionId2 = await page.evaluate(() => localStorage.getItem('chattwelve_session_id'))

    expect(sessionId1).toBe(sessionId2)
  })

  test('new chat button creates new session', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(3000)

    const sessionId1 = await page.evaluate(() => localStorage.getItem('chattwelve_session_id'))

    // Click new chat button (the one with Plus icon)
    const newChatButton = page.locator('button:has-text("New Chat")').filter({ has: page.locator('svg') }).first()
    await newChatButton.click()
    await page.waitForTimeout(2000)

    const sessionId2 = await page.evaluate(() => localStorage.getItem('chattwelve_session_id'))

    expect(sessionId2).toBeTruthy()
    expect(sessionId1).not.toBe(sessionId2)
  })
})
