import { expect, test, type Page } from '@playwright/test'

// Set SCREENSHOTS=1 to save portfolio screenshots of the real running application.
const SCREENSHOTS = process.env.SCREENSHOTS === '1'

async function snap(page: Page, name: string) {
  if (SCREENSHOTS) await page.screenshot({ path: `../docs/screenshots/${name}.png`, fullPage: true })
}

async function createTask(page: Page, example: string, mode: 'Structured' | 'Baseline' = 'Structured') {
  await page.goto('/')
  await page.getByRole('button', { name: example }).click()
  await page.getByLabel(mode).check()
  await page.getByRole('button', { name: 'Create task and generate plan' }).click()
  await expect(page).toHaveURL(/\/tasks\//)
}

function actionCard(page: Page, description: RegExp) {
  return page.getByRole('article').filter({ has: page.getByRole('heading', { name: description }) })
}

test('structured review: risky deletion is revised into an approved archive', async ({ page }) => {
  await createTask(page, 'Risky irreversible proposal')

  const deletion = actionCard(page, /Permanently delete billing events/)
  await expect(page.getByText('Awaiting review').first()).toBeVisible()
  await expect(deletion.getByText('High risk')).toBeVisible()
  await expect(deletion.getByText('The effect cannot be undone.')).toBeVisible()
  await expect(page.getByText('Unsupported', { exact: true })).toBeVisible()
  await snap(page, '01-structured-review')

  // Ask for a revision instead of approving the deletion.
  await page.getByPlaceholder('What should change in the plan?').fill('Do not delete. Archive records beyond the 365-day retention period.')
  await page.getByRole('button', { name: 'Send and re-plan' }).click()
  await expect(page.getByRole('heading', { name: 'Plan, attempt 2' })).toBeVisible()

  const archive = actionCard(page, /Archive billing events older than 365 days/)
  await archive.getByRole('button', { name: 'Approve action' }).click()
  await expect(archive.getByText('Approved')).toBeVisible()
  await expect(archive.getByText('Not executed')).toBeVisible() // approval is not execution

  await page.getByRole('button', { name: 'Run approved actions' }).click()
  await expect(page.getByText('Task status: Completed')).toBeVisible()
  await expect(archive.getByText('Authorized')).toBeVisible()
  await expect(archive.getByText('Executed')).toBeVisible()
  await expect(archive.getByText('Verified')).toBeVisible()
  await expect(page.getByRole('list', { name: 'Audit events' })).toContainText('Authorization granted')
  await snap(page, '02-completed-with-audit')
})

test('prompt injection: the unlisted shell tool is blocked and never runs', async ({ page }) => {
  await createTask(page, 'Prompt injection in task text')
  const shell = actionCard(page, /pre-approved maintenance command/)
  await expect(shell.getByText('Forbidden')).toBeVisible()
  await expect(shell.getByText('Blocked by policy')).toBeVisible()
  await expect(shell.getByText('Skipped')).toBeVisible()
  await expect(shell.getByRole('button', { name: 'Approve action' })).toHaveCount(0)
  await snap(page, '03-prompt-injection-blocked')
})

test('missing information: clarification is required before approval', async ({ page }) => {
  await createTask(page, 'Missing information')
  await expect(page.getByText('The agent needs information before anything can run')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Approve action' })).toHaveCount(0)

  await page.getByLabel('Answer or ask (clarification)').check()
  await page.getByPlaceholder(/Answer the agent/).fill('Post it in #billing-team')
  await page.getByRole('button', { name: 'Send and re-plan' }).click()
  const notify = actionCard(page, /#billing-team/)
  await notify.getByRole('button', { name: 'Approve action' }).click()
  await page.getByRole('button', { name: 'Run approved actions' }).click()
  await expect(page.getByText('Task status: Completed')).toBeVisible()
})

test('baseline: approve-or-stop gate for the whole plan', async ({ page }) => {
  await createTask(page, 'Risky irreversible proposal', 'Baseline')
  await expect(page.getByText(/Assumptions and per-action risk are not shown/)).toBeVisible()
  await snap(page, '04-baseline-review')
  await page.getByRole('button', { name: 'Stop task' }).click()
  await expect(page.getByText('Task status: Cancelled')).toBeVisible()
})

test('execution failure is explained and not offered for retry', async ({ page }) => {
  await createTask(page, 'Execution failure')
  await expect(page.getByText(/Failed during execution/)).toBeVisible()
  await expect(page.getByText(/cannot be retried automatically/)).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry planning' })).toHaveCount(0)
})

test('task list is usable on a phone @mobile', async ({ page }) => {
  await createTask(page, 'Straightforward read-only calculation')
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Tasks' })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)
  expect(overflow).toBe(false)
  await snap(page, '05-mobile-task-list')
})
