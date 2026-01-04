import { test, expect } from '@playwright/test'
import path from 'path'
import fs from 'fs'

/**
 * Screenshot generation script for README.md
 * Run with: npx playwright test tests/screenshots.spec.ts --project=chromium
 *
 * Screenshots are saved to: ../screenshots/
 */

const SCREENSHOTS_DIR = path.join(__dirname, '../../screenshots')

// Ensure screenshots directory exists
test.beforeAll(async () => {
  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true })
  }
})

test.describe('README Screenshots', () => {
  test.beforeEach(async ({ page }) => {
    // Set viewport for consistent screenshots
    await page.setViewportSize({ width: 1400, height: 900 })
  })

  test('capture main interface - dark mode', async ({ page }) => {
    await page.goto('/')

    // Wait for the app to load
    await page.waitForSelector('[data-testid="chat-input"], textarea, input[type="text"]', { timeout: 10000 })

    // Wait for health indicators to load
    await page.waitForTimeout(2000)

    // Take screenshot
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'dark-mode.png'),
      fullPage: false,
    })
  })

  test('capture main interface - light mode', async ({ page }) => {
    await page.goto('/')

    // Wait for the app to load
    await page.waitForSelector('[data-testid="chat-input"], textarea, input[type="text"]', { timeout: 10000 })

    // Switch to light mode by modifying the HTML class
    await page.evaluate(() => {
      document.documentElement.classList.remove('dark')
      document.documentElement.classList.add('light')
    })

    // Wait for styles to apply
    await page.waitForTimeout(1000)

    // Take screenshot
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'light-mode.png'),
      fullPage: false,
    })
  })

  test('capture chat with sample conversation', async ({ page }) => {
    await page.goto('/')

    // Wait for the app to load
    await page.waitForSelector('[data-testid="chat-input"], textarea, input[type="text"]', { timeout: 10000 })

    // Add sample messages via JavaScript to simulate a conversation
    await page.evaluate(() => {
      // Find the chat area and inject sample messages
      const chatArea = document.querySelector('[class*="flex-1"][class*="overflow-y-auto"]')
      if (chatArea) {
        chatArea.innerHTML = `
          <div style="padding: 1rem; display: flex; flex-direction: column; gap: 1rem;">
            <!-- User message -->
            <div style="display: flex; justify-content: flex-end;">
              <div style="background: hsl(var(--primary)); color: hsl(var(--primary-foreground)); padding: 0.75rem 1rem; border-radius: 1rem; max-width: 70%;">
                What is the current gold price?
              </div>
            </div>
            <!-- Assistant message -->
            <div style="display: flex; justify-content: flex-start;">
              <div style="background: hsl(var(--muted)); color: hsl(var(--foreground)); padding: 0.75rem 1rem; border-radius: 1rem; max-width: 70%;">
                <p style="margin: 0;">The current gold price is <strong>$2,634.50</strong> per ounce (XAU/USD).</p>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.875rem; opacity: 0.7;">Price is up 0.42% from yesterday's close.</p>
              </div>
            </div>
            <!-- User message -->
            <div style="display: flex; justify-content: flex-end;">
              <div style="background: hsl(var(--primary)); color: hsl(var(--primary-foreground)); padding: 0.75rem 1rem; border-radius: 1rem; max-width: 70%;">
                Show me the RSI for Bitcoin
              </div>
            </div>
            <!-- Assistant message -->
            <div style="display: flex; justify-content: flex-start;">
              <div style="background: hsl(var(--muted)); color: hsl(var(--foreground)); padding: 0.75rem 1rem; border-radius: 1rem; max-width: 70%;">
                <p style="margin: 0;">The current <strong>RSI (14-period)</strong> for BTC/USD is <strong>58.3</strong>.</p>
                <p style="margin: 0.5rem 0 0 0; font-size: 0.875rem;">This indicates a neutral market condition, neither overbought nor oversold.</p>
              </div>
            </div>
          </div>
        `
      }
    })

    await page.waitForTimeout(500)

    // Take screenshot
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'chat-conversation.png'),
      fullPage: false,
    })
  })

  test('capture prompt modal', async ({ page }) => {
    await page.goto('/')

    // Wait for the app to load
    await page.waitForSelector('[data-testid="chat-input"], textarea, input[type="text"]', { timeout: 10000 })

    // Look for the settings/prompt button and click it
    const settingsButton = page.locator('button').filter({ has: page.locator('svg') }).first()

    // Try to find and click a settings button
    const buttons = await page.locator('button').all()
    for (const button of buttons) {
      const text = await button.textContent()
      const ariaLabel = await button.getAttribute('aria-label')
      if (text?.toLowerCase().includes('prompt') ||
          text?.toLowerCase().includes('settings') ||
          ariaLabel?.toLowerCase().includes('prompt') ||
          ariaLabel?.toLowerCase().includes('settings')) {
        await button.click()
        break
      }
    }

    // Wait for modal to appear
    await page.waitForTimeout(500)

    // Check if modal opened, if not try clicking the cog/settings icon
    const modal = page.locator('[role="dialog"]')
    if (!await modal.isVisible()) {
      // Try finding a button with settings icon (usually has Cog or Settings in class)
      const iconButtons = await page.locator('button:has(svg)').all()
      for (const button of iconButtons) {
        // Click buttons that might be settings
        try {
          await button.click()
          await page.waitForTimeout(300)
          if (await modal.isVisible()) break
        } catch {
          continue
        }
      }
    }

    // Wait for modal animation
    await page.waitForTimeout(500)

    // Take screenshot
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'prompt-modal.png'),
      fullPage: false,
    })
  })

  test('capture mobile view', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 390, height: 844 })

    await page.goto('/')

    // Wait for the app to load
    await page.waitForSelector('[data-testid="chat-input"], textarea, input[type="text"]', { timeout: 10000 })

    await page.waitForTimeout(1000)

    // Take screenshot
    await page.screenshot({
      path: path.join(SCREENSHOTS_DIR, 'mobile-view.png'),
      fullPage: false,
    })
  })
})
