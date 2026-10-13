import { expect, test, type Page } from '@playwright/test'
import { mkdirSync, renameSync, rmSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendDirectory = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const sampleResume = resolve(
  dirname(fileURLToPath(import.meta.url)),
  '../../backend/sample_data/sample_resume.docx',
)
const recordDemo = process.env.CAREERLENS_RECORD_DEMO === 'true'
const demoVideoPath = resolve(frontendDirectory, '../docs/assets/careerlens-demo.webm')

async function showDemoCaption(page: Page, caption: string) {
  await page.evaluate((text: string) => {
    let element = document.getElementById('careerlens-demo-caption')
    if (!element) {
      element = document.createElement('div')
      element.id = 'careerlens-demo-caption'
      element.setAttribute('aria-hidden', 'true')
      element.style.cssText = [
        'position:fixed',
        'left:50%',
        'bottom:14px',
        'transform:translateX(-50%)',
        'max-width:calc(100vw - 48px)',
        'padding:10px 18px',
        'border-radius:12px',
        'background:rgba(17, 28, 46, 0.86)',
        'color:#fff',
        'font:600 16px/1.35 system-ui, sans-serif',
        'text-align:center',
        'box-shadow:0 8px 32px rgba(5, 15, 29, 0.28)',
        'z-index:2147483647',
      ].join(';')
      document.body.append(element)
    }
    element.textContent = text
  }, caption)
  await page.waitForTimeout(2200)
}

test('registers, parses a resume, compares a role, creates a plan, and tracks the application', async ({ page }) => {
  const email = `careerlens-e2e-${Date.now()}@example.com`

  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
  if (recordDemo) {
    await showDemoCaption(page, 'CareerLens — resume and role insights, stored locally.')
  }
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill('CareerLens-Test-Password-42')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()

  await expect(page.getByRole('heading', { name: 'Add a resume and a job description' })).toBeVisible()
  if (recordDemo) {
    await showDemoCaption(page, 'Create a local account for a private career workspace.')
  }
  await page.getByLabel('Resume file (PDF or DOCX)').setInputFiles(sampleResume)
  await page.getByRole('button', { name: 'Upload and read resume' }).click()
  await expect(page.getByRole('heading', { name: 'Resume read and saved' })).toBeVisible()
  await expect(page.locator('.resume-result .skill-list').first()).toContainText('Python')
  const entryGroups = page.locator('.resume-entry-group')
  await expect(entryGroups).toHaveCount(3)
  await entryGroups.nth(0).locator('summary').click()
  await expect(entryGroups.nth(0)).toContainText('Software Engineering Intern')
  await entryGroups.nth(1).locator('summary').click()
  await expect(entryGroups.nth(1)).toContainText('Computer Science')
  await entryGroups.nth(2).locator('summary').click()
  await expect(entryGroups.nth(2)).toContainText('Career Dashboard')
  if (recordDemo) {
    await entryGroups.first().scrollIntoViewIfNeeded()
    await showDemoCaption(page, 'Review the likely experience, education, and project entries.')
  }

  await page.getByLabel('Job title').fill('Software Engineer')
  await page.getByLabel('Company (optional)').fill('Northstar Learning')
  await page.getByRole('textbox', { name: 'Job description' }).fill(
    'We are looking for Python, React, and Kubernetes experience.',
  )
  await page.getByRole('button', { name: 'Compare resume with this role' }).click()

  await expect(page.getByRole('heading', { name: 'Your role comparison' })).toBeVisible()
  await expect(page.locator('.score-value')).toHaveText('67%')
  await expect(page.locator('.missing-skills')).toContainText('Kubernetes')
  await expect(page.getByRole('img', { name: /Recent role match scores/ }))
    .toHaveAttribute('aria-label', /Software Engineer: 67%/)
  const skillCoverage = page.getByRole('region', { name: 'Skill coverage across roles' })
  await expect(skillCoverage.getByRole('meter', { name: 'Python, recognized in resume' }))
    .toHaveAttribute('aria-valuenow', '1')
  await expect(skillCoverage.getByRole('meter', { name: 'Kubernetes, missing from resume' }))
    .toHaveAttribute('aria-valuenow', '1')
  if (recordDemo) {
    await page.getByRole('heading', { name: 'Your role comparison' }).scrollIntoViewIfNeeded()
    await showDemoCaption(page, '67% match: Python and React overlap; Kubernetes is a gap to explore.')
  }

  await page.getByRole('button', { name: 'Create a career plan' }).click()
  await expect(page.getByRole('heading', { name: 'A practical way forward' })).toBeVisible()
  await expect(page.getByText('Rule-based starter')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Interview practice' })).toBeVisible()
  if (recordDemo) {
    await page.getByRole('heading', { name: 'A practical way forward' }).scrollIntoViewIfNeeded()
    await showDemoCaption(page, 'Local rules build skill priorities, project ideas, and interview practice.')
  }

  await page.getByRole('button', { name: 'Add role to application tracker' }).click()
  await expect(page.getByText('Added to your application tracker.')).toBeVisible()
  const applicationStatus = page.getByLabel('Status for Software Engineer')
  await expect(applicationStatus).toHaveValue('saved')
  await applicationStatus.selectOption('applied')
  await expect(applicationStatus).toHaveValue('applied')
  await expect(page.getByRole('meter', { name: 'applied applications' }))
    .toHaveAttribute('aria-valuenow', '1')

  if (recordDemo) {
    await applicationStatus.scrollIntoViewIfNeeded()
    await showDemoCaption(page, 'Track the role and update its application status.')
    await skillCoverage.scrollIntoViewIfNeeded()
    await showDemoCaption(page, 'Spot recurring recognized skills and missing requirements across roles.')

    const video = page.video()
    if (!video) throw new Error('Playwright did not create a demo recording.')
    const pendingVideoPath = demoVideoPath + '.pending'
    mkdirSync(dirname(demoVideoPath), { recursive: true })
    rmSync(pendingVideoPath, { force: true })
    await page.close()
    await video.saveAs(pendingVideoPath)
    renameSync(pendingVideoPath, demoVideoPath)
    await video.delete()
  }
})

test('rejects unsupported files and keeps the tracker entry after deleting a resume', async ({ page }) => {
  const email = `careerlens-resume-delete-e2e-${Date.now()}@example.com`

  await page.goto('/')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill('CareerLens-Test-Password-42')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Career dashboard' })).toBeVisible()

  await page.getByLabel('Resume file (PDF or DOCX)').setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('This is not a supported resume file.'),
  })
  await page.getByRole('button', { name: 'Upload and read resume' }).click()
  await expect(page.getByRole('alert')).toContainText('Please upload a PDF or DOCX resume.')

  await page.getByLabel('Resume file (PDF or DOCX)').setInputFiles(sampleResume)
  await page.getByRole('button', { name: 'Upload and read resume' }).click()
  await expect(page.getByRole('heading', { name: 'Resume read and saved' })).toBeVisible()

  await page.getByLabel('Job title').fill('Software Engineer')
  await page.getByLabel('Company (optional)').fill('Northstar Learning')
  await page.getByRole('textbox', { name: 'Job description' }).fill(
    'We are looking for Python and React experience.',
  )
  await page.getByRole('button', { name: 'Compare resume with this role' }).click()
  await expect(page.getByRole('heading', { name: 'Your role comparison' })).toBeVisible()
  await page.getByRole('button', { name: 'Add role to application tracker' }).click()
  await expect(page.getByText('Added to your application tracker.')).toBeVisible()

  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toContain('Permanently delete sample_resume.docx')
    await dialog.accept()
  })
  await page.getByRole('button', { name: 'Delete this saved resume' }).click()
  await expect(page.getByText('Resume deleted. Its saved comparisons and career plans were removed.'))
    .toBeVisible()

  const metric = (label: string) => page.locator('.metric-card').filter({ hasText: label }).locator('strong')
  await expect(metric('Resumes saved')).toHaveText('0')
  await expect(metric('Role comparisons')).toHaveText('0')
  await expect(metric('Applications tracked')).toHaveText('1')
  await expect(page.getByLabel('Status for Software Engineer')).toHaveValue('saved')
})

test('keeps account data private and fits a phone-sized viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  const metric = (label: string) => page.locator('.metric-card').filter({ hasText: label }).locator('strong')

  await page.getByLabel('Email address').fill(`careerlens-owner-e2e-${Date.now()}@example.com`)
  await page.getByLabel('Password').fill('CareerLens-Test-Password-42')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Career dashboard' })).toBeVisible()
  await page.getByLabel('Resume file (PDF or DOCX)').setInputFiles(sampleResume)
  await page.getByRole('button', { name: 'Upload and read resume' }).click()
  await expect(page.getByRole('heading', { name: 'Resume read and saved' })).toBeVisible()
  await page.getByLabel('Job title').fill('Private Owner Role')
  await page.getByRole('textbox', { name: 'Job description' }).fill('Python and React experience.')
  await page.getByRole('button', { name: 'Compare resume with this role' }).click()
  await expect(page.getByRole('heading', { name: 'Your role comparison' })).toBeVisible()
  await expect(metric('Resumes saved')).toHaveText('1')
  await expect(metric('Role comparisons')).toHaveText('1')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBeTruthy()

  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
  await page.getByLabel('Email address').fill(`careerlens-other-e2e-${Date.now()}@example.com`)
  await page.getByLabel('Password').fill('CareerLens-Test-Password-42')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Career dashboard' })).toBeVisible()

  await expect(metric('Resumes saved')).toHaveText('0')
  await expect(metric('Role comparisons')).toHaveText('0')
  await expect(page.getByRole('region', { name: 'Skill coverage across roles' }))
    .toContainText('Compare a resume with a job description to start your skill coverage view.')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    .toBeTruthy()
})

test('requires a password and confirmation before deleting the local account', async ({ page }) => {
  const email = `careerlens-delete-e2e-${Date.now()}@example.com`

  await page.goto('/')
  await page.getByLabel('Email address').fill(email)
  await page.getByLabel('Password').fill('CareerLens-Test-Password-42')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Career dashboard' })).toBeVisible()

  await page.getByRole('heading', { name: 'Manage your local account' }).scrollIntoViewIfNeeded()
  await page.getByRole('button', { name: 'Delete my account' }).click()
  await page.getByLabel('Confirm with your current password').fill('CareerLens-Test-Password-42')
  await page.getByRole('checkbox', { name: 'I understand this permanently deletes all of my CareerLens data.' }).check()
  await page.getByRole('button', { name: 'Permanently delete account' }).click()

  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
  await expect(page.getByRole('status')).toContainText('Your account and saved CareerLens data were deleted.')
})
