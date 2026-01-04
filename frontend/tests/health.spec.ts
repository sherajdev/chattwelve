import { test, expect } from '@playwright/test'

test.describe('Health Status', () => {
  test('backend API is reachable', async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/health')
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data.status).toBe('ok')
  })

  test('AI service health check', async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/ai-health')
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toHaveProperty('status')
    expect(data).toHaveProperty('primary_model')
    expect(data).toHaveProperty('fallback_model')
  })

  test('MCP server health check', async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/mcp-health')
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toHaveProperty('status')
    expect(data).toHaveProperty('mcp_server_url')
  })

  test('health indicators update in UI', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('networkidle')

    // Wait for health check to complete
    await page.waitForTimeout(3000)

    // Look for health indicator dots (uses div not header)
    const healthDots = page.locator('.rounded-full.h-2.w-2')
    await expect(healthDots.first()).toBeVisible()

    // Should have at least 3 health indicators
    const count = await healthDots.count()
    expect(count).toBeGreaterThanOrEqual(3)
  })
})

test.describe('API Integration', () => {
  test('session endpoint works', async ({ request }) => {
    // Create a new session
    const createResponse = await request.post('http://localhost:8000/api/session', {
      data: {},
    })
    expect(createResponse.ok()).toBeTruthy()

    const session = await createResponse.json()
    expect(session).toHaveProperty('session_id')
    expect(session.session_id).toMatch(/^[a-f0-9-]{36}$/)

    // Get session info
    const getResponse = await request.get(`http://localhost:8000/api/session/${session.session_id}`)
    expect(getResponse.ok()).toBeTruthy()

    // Delete session
    const deleteResponse = await request.delete(`http://localhost:8000/api/session/${session.session_id}`)
    expect(deleteResponse.ok()).toBeTruthy()
  })

  test('chat endpoint works', async ({ request }) => {
    // Create session first
    const sessionResponse = await request.post('http://localhost:8000/api/session', {
      data: {},
    })
    const session = await sessionResponse.json()

    // Send chat message
    const chatResponse = await request.post('http://localhost:8000/api/chat', {
      data: {
        session_id: session.session_id,
        query: 'What is 2 + 2?',
      },
    })
    expect(chatResponse.ok()).toBeTruthy()

    const chat = await chatResponse.json()
    expect(chat).toHaveProperty('answer')
    expect(chat.answer.length).toBeGreaterThan(0)

    // Cleanup
    await request.delete(`http://localhost:8000/api/session/${session.session_id}`)
  })

  test('prompts endpoint works', async ({ request }) => {
    const response = await request.get('http://localhost:8000/api/prompts')
    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data).toHaveProperty('prompts')
    expect(data).toHaveProperty('count')
    expect(Array.isArray(data.prompts)).toBeTruthy()
  })
})
