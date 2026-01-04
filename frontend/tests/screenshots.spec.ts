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
    // Increase timeout for this test since AI responses can take a while
    test.setTimeout(120000)

    await page.goto('/')

    // Wait for the app to load
    await page.waitForSelector('[data-testid="chat-input"], textarea, input[type="text"]', { timeout: 10000 })

    // Wait for session to initialize
    await page.waitForTimeout(2000)

    // Find the textarea and type a message
    const textarea = page.locator('textarea').first()
    await textarea.fill('What is the current gold price?')

    // Find and click the send button (or press Enter)
    const sendButton = page.locator('button[type="submit"]').first()
    if (await sendButton.isVisible()) {
      await sendButton.click()
    } else {
      await textarea.press('Enter')
    }

    // Wait for the AI response to complete (look for assistant message that's not streaming)
    // The streaming message has id="streaming", so we wait until it's replaced with a final message
    await page.waitForTimeout(3000) // Initial wait for response to start

    // Wait for streaming to complete - check that no "streaming" element exists
    // and that there's at least one assistant message
    await page.waitForFunction(() => {
      const messages = document.querySelectorAll('[class*="message"], [class*="Message"]')
      // Look for any text content indicating a response (price, dollar sign, gold, etc.)
      const pageText = document.body.innerText
      return pageText.includes('$') || pageText.includes('gold') || pageText.includes('Gold') || pageText.includes('XAU')
    }, { timeout: 60000 })

    // Extra wait to ensure streaming is fully complete
    await page.waitForTimeout(5000)

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
