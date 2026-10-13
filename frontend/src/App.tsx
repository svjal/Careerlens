import { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'
const APPLICATION_STATUSES = ['saved', 'applied', 'interviewing', 'offer', 'rejected', 'withdrawn']
const SESSION_STORAGE_KEY = 'careerlens_access_token'

type AuthResponse = {
  access_token: string
  user: { id: number; email: string }
}

type ResumeParseResult = {
  id: number
  filename: string
  character_count: number
  text: string
  sections: Record<string, string>
  entries: Record<'experience' | 'education' | 'projects', ResumeEntry[]>
  skills: string[]
  resume_score: number
  resume_score_type: string
  resume_score_notes: string[]
}

type ResumeEntry = {
  heading: string
  details: string[]
}

type SavedResume = {
  id: number
  filename: string
  skills: string[]
  resume_score: number
  created_at: string | null
}

type MatchResult = {
  id: number
  resume_id: number
  match_score: number
  matching_skills: string[]
  missing_skills: string[]
  resume_skills: string[]
  job_skills: string[]
  explanation: string
}

type CareerAnalysis = {
  id: number
  match_id: number
  analysis_method: string
  match_score: number
  resume_suggestions: string[]
  recommended_skills: string[]
  roadmap: { timeframe: string; focus: string; action: string }[]
  project_recommendations: { skill: string; idea: string }[]
  interview_questions: string[]
}

type DashboardMatch = {
  id: number
  job_title: string
  resume_filename: string
  match_score: number
  matching_skills: string[]
  missing_skills: string[]
  created_at: string | null
}

type DashboardSummary = {
  resume_count: number
  match_count: number
  average_match_score: number
  application_count: number
  application_counts: Record<string, number>
  skill_coverage: {
    total_matches: number
    matching_skills: { skill: string; match_count: number }[]
    missing_skills: { skill: string; match_count: number }[]
  }
  latest_resume: {
    id: number
    filename: string
    skills: string[]
    resume_score: number
    resume_score_notes: string[]
    created_at: string | null
  } | null
  recent_matches: DashboardMatch[]
}

type Application = {
  id: number
  match_id: number | null
  job_title: string
  company: string | null
  job_url: string | null
  status: string
  notes: string | null
  applied_at: string | null
  created_at: string | null
}

function formatChartDate(value: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('en', { month: 'short', day: 'numeric' }).format(date)
}

function MatchScoreChart({ matches }: { matches: DashboardMatch[] }) {
  if (matches.length === 0) {
    return <p className="chart-empty-state">Compare a role to start a match-score history.</p>
  }

  const orderedMatches = [...matches].reverse()
  const chartWidth = 520
  const chartTop = 14
  const chartBottom = 156
  const chartLeft = 42
  const chartRight = chartWidth - 34
  const points = orderedMatches.map((match, index) => {
    const x = orderedMatches.length === 1
      ? (chartLeft + chartRight) / 2
      : chartLeft + index * (chartRight - chartLeft) / (orderedMatches.length - 1)
    const y = chartBottom - match.match_score / 100 * (chartBottom - chartTop)
    return { match, x, y }
  })
  const linePoints = points.map(({ x, y }) => `${x},${y}`).join(' ')
  const chartDescription = orderedMatches
    .map((match) => `${match.job_title}: ${match.match_score}% on ${formatChartDate(match.created_at)}`)
    .join('; ')

  return (
    <div className="match-score-chart">
      <p className="chart-caption">Your five most recent comparisons, oldest to newest</p>
      <svg
        className="match-score-svg"
        viewBox="0 0 520 190"
        role="img"
        aria-label={`Recent role match scores. ${chartDescription}`}
      >
        {[100, 50, 0].map((score) => {
          const y = chartBottom - score / 100 * (chartBottom - chartTop)
          return (
            <g className="match-chart-gridline" key={score}>
              <line x1={chartLeft} x2={chartRight} y1={y} y2={y} />
              <text x={chartLeft - 8} y={y + 4} textAnchor="end">{score}%</text>
            </g>
          )
        })}
        {points.length > 1 && <polyline className="match-chart-line" points={linePoints} />}
        {points.map(({ match, x, y }) => (
          <g className="match-chart-point" key={match.id}>
            <title>{match.job_title}: {match.match_score}%</title>
            <circle cx={x} cy={y} r="5" />
            <text x={x} y="180" textAnchor="middle">{formatChartDate(match.created_at)}</text>
          </g>
        ))}
      </svg>
    </div>
  )
}

function ApplicationStatusChart({ counts, total }: { counts: Record<string, number>; total: number }) {
  if (total === 0) {
    return <p className="chart-empty-state">Save a role to see application statuses here.</p>
  }

  return (
    <div className="application-status-chart" aria-label="Application counts by status">
      {APPLICATION_STATUSES.map((status) => {
        const count = counts[status] || 0
        const percent = count / total * 100
        return (
          <div className="status-chart-row" key={status}>
            <span className="status-chart-label">{status}</span>
            <div
              className="status-chart-track"
              role="meter"
              aria-label={`${status} applications`}
              aria-valuemin={0}
              aria-valuemax={total}
              aria-valuenow={count}
            >
              <span style={{ width: `${percent}%` }} />
            </div>
            <strong>{count}</strong>
          </div>
        )
      })}
    </div>
  )
}

function SkillCoverageChart({ coverage }: { coverage: DashboardSummary['skill_coverage'] }) {
  const columns = [
    { title: 'Recognized in your resume', skills: coverage.matching_skills, tone: 'strength' },
    { title: 'Missing from your resume', skills: coverage.missing_skills, tone: 'gap' },
  ]

  return (
    <section className="dashboard-panel skill-coverage-panel" aria-labelledby="skill-coverage-title">
      <div className="skill-coverage-heading">
        <div>
          <h3 id="skill-coverage-title">Skill coverage across roles</h3>
          <p className="chart-caption">
            Top recurring keywords from {coverage.total_matches} saved {coverage.total_matches === 1 ? 'comparison' : 'comparisons'}.
          </p>
        </div>
        <span className="skill-coverage-count">{coverage.total_matches} roles</span>
      </div>
      {coverage.total_matches === 0 ? (
        <p className="chart-empty-state">Compare a resume with a job description to start your skill coverage view.</p>
      ) : (
        <div className="skill-coverage-columns">
          {columns.map((column) => (
            <div className="skill-coverage-column" key={column.title}>
              <h4>{column.title}</h4>
              {column.skills.length === 0 ? (
                <p className="skill-coverage-empty">No recognized skills in this category yet.</p>
              ) : (
                <ul className="skill-coverage-list">
                  {column.skills.map(({ skill, match_count }) => {
                    const percent = match_count / coverage.total_matches * 100
                    const label = column.tone === 'strength'
                      ? `${skill}, recognized in resume`
                      : `${skill}, missing from resume`
                    return (
                      <li className={`skill-coverage-row ${column.tone}`} key={skill}>
                        <div className="skill-coverage-row-heading">
                          <span>{skill}</span>
                          <strong>{match_count}/{coverage.total_matches} roles</strong>
                        </div>
                        <div
                          className="skill-coverage-track"
                          role="meter"
                          aria-label={label}
                          aria-valuemin={0}
                          aria-valuemax={coverage.total_matches}
                          aria-valuenow={match_count}
                          aria-valuetext={`${match_count} of ${coverage.total_matches} comparisons`}
                        >
                          <span style={{ width: `${percent}%` }} />
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
      <p className="skill-coverage-note">Keyword overlap helps you spot patterns; it does not measure skill depth or overall qualifications.</p>
    </section>
  )
}

function App() {
  const [accessToken, setAccessToken] = useState<string | null>(
    () => window.sessionStorage.getItem(SESSION_STORAGE_KEY),
  )
  const [authMode, setAuthMode] = useState<'login' | 'register'>('register')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [isAuthenticating, setIsAuthenticating] = useState(false)
  const [jobDescription, setJobDescription] = useState('')
  const [jobTitle, setJobTitle] = useState('')
  const [company, setCompany] = useState('')
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [resumeResult, setResumeResult] = useState<ResumeParseResult | null>(null)
  const [resumeError, setResumeError] = useState('')
  const [resumeMessage, setResumeMessage] = useState('')
  const [isParsingResume, setIsParsingResume] = useState(false)
  const [isDeletingResume, setIsDeletingResume] = useState(false)
  const [showDeleteAccountForm, setShowDeleteAccountForm] = useState(false)
  const [deleteAccountPassword, setDeleteAccountPassword] = useState('')
  const [deleteAccountError, setDeleteAccountError] = useState('')
  const [isDeletingAccount, setIsDeletingAccount] = useState(false)
  const [authNotice, setAuthNotice] = useState('')
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null)
  const [matchError, setMatchError] = useState('')
  const [isMatching, setIsMatching] = useState(false)
  const [careerAnalysis, setCareerAnalysis] = useState<CareerAnalysis | null>(null)
  const [analysisError, setAnalysisError] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [trackerMessage, setTrackerMessage] = useState('')
  const [trackerError, setTrackerError] = useState('')
  const [isSavingApplication, setIsSavingApplication] = useState(false)
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null)
  const [applications, setApplications] = useState<Application[]>([])
  const [savedResumes, setSavedResumes] = useState<SavedResume[]>([])
  const [dashboardError, setDashboardError] = useState('')
  const [dashboardRevision, setDashboardRevision] = useState(0)

  const signOut = useCallback(() => {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY)
    setAccessToken(null)
    setResumeFile(null)
    setResumeResult(null)
    setSavedResumes([])
    setMatchResult(null)
    setMatchError('')
    setCareerAnalysis(null)
    setAnalysisError('')
    setJobDescription('')
    setJobTitle('')
    setCompany('')
    setApplications([])
    setDashboard(null)
    setDashboardError('')
    setResumeError('')
    setResumeMessage('')
    setTrackerMessage('')
    setTrackerError('')
    setShowDeleteAccountForm(false)
    setDeleteAccountPassword('')
    setDeleteAccountError('')
    setAuthNotice('')
  }, [])

  const authenticatedFetch = useCallback(async (input: string, init: RequestInit = {}) => {
    const headers = new Headers(init.headers)
    if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
    const response = await fetch(input, { ...init, headers })
    if (response.status === 401 && accessToken) {
      signOut()
      setAuthError('Your sign-in expired. Please sign in again.')
    }
    return response
  }, [accessToken, signOut])

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsDeletingAccount(true)
    setDeleteAccountError('')
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/auth/account`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: deleteAccountPassword }),
      })
      if (!response.ok) {
        const result = await response.json()
        throw new Error(typeof result.detail === 'string' ? result.detail : 'The account could not be deleted.')
      }
      signOut()
      setAuthMode('register')
      setAuthNotice('Your account and saved CareerLens data were deleted.')
    } catch (error) {
      setDeleteAccountError(error instanceof Error ? error.message : 'Could not reach the CareerLens API.')
    } finally {
      setIsDeletingAccount(false)
    }
  }

  useEffect(() => {
    if (!accessToken) return

    let ignoreResponse = false

    async function loadDashboard() {
      try {
        const [summaryResponse, applicationsResponse, resumesResponse] = await Promise.all([
          authenticatedFetch(`${API_BASE_URL}/api/v1/dashboard/summary`),
          authenticatedFetch(`${API_BASE_URL}/api/v1/applications`),
          authenticatedFetch(`${API_BASE_URL}/api/v1/resumes`),
        ])
        if (!summaryResponse.ok || !applicationsResponse.ok || !resumesResponse.ok) {
          throw new Error('Could not load saved CareerLens data.')
        }

        const [summary, savedApplications, savedResumeList] = await Promise.all([
          summaryResponse.json(),
          applicationsResponse.json(),
          resumesResponse.json(),
        ])
        let latestResume: ResumeParseResult | null = null
        if (summary.latest_resume) {
          const resumeResponse = await authenticatedFetch(
            `${API_BASE_URL}/api/v1/resumes/${summary.latest_resume.id}`,
          )
          if (!resumeResponse.ok) throw new Error('Could not reopen the latest saved resume.')
          latestResume = await resumeResponse.json() as ResumeParseResult
        }
        if (!ignoreResponse) {
          setDashboard(summary as DashboardSummary)
          setApplications(savedApplications as Application[])
          setSavedResumes(savedResumeList as SavedResume[])
          setResumeResult(latestResume)
          setDashboardError('')
        }
      } catch {
        if (!ignoreResponse) {
          setDashboardError('Could not load the dashboard. Check that the backend and PostgreSQL are running.')
        }
      }
    }

    void loadDashboard()
    return () => {
      ignoreResponse = true
    }
  }, [accessToken, dashboardRevision, authenticatedFetch])

  async function submitAuthentication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsAuthenticating(true)
    setAuthError('')
    setAuthNotice('')
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/auth/${authMode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword }),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(typeof result.detail === 'string' ? result.detail : 'Could not sign in.')
      }
      const session = result as AuthResponse
      window.sessionStorage.setItem(SESSION_STORAGE_KEY, session.access_token)
      setAccessToken(session.access_token)
      setAuthPassword('')
      setAuthError('')
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : 'Could not reach the CareerLens API.')
    } finally {
      setIsAuthenticating(false)
    }
  }

  function refreshDashboard() {
    setDashboardRevision((revision) => revision + 1)
  }

  function handleResumeSelection(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0] ?? null
    setResumeFile(selectedFile)
    setResumeResult(null)
    setResumeError('')
    setResumeMessage('')
    setMatchResult(null)
    setTrackerMessage('')
  }

  async function chooseSavedResume(event: ChangeEvent<HTMLSelectElement>) {
    const resumeId = Number(event.target.value)
    setResumeError('')
    setResumeMessage('')
    setMatchError('')
    setAnalysisError('')
    setMatchResult(null)
    setCareerAnalysis(null)
    setResumeFile(null)
    if (!resumeId) {
      setResumeResult(null)
      return
    }

    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/resumes/${resumeId}`)
      const result = await response.json()
      if (!response.ok) {
        throw new Error(typeof result.detail === 'string' ? result.detail : 'The saved resume could not be opened.')
      }
      setResumeResult(result as ResumeParseResult)
    } catch (error) {
      setResumeError(error instanceof Error ? error.message : 'Could not reach the CareerLens API.')
    }
  }

  async function deleteSavedResume() {
    if (!resumeResult) return
    const confirmed = window.confirm(
      `Permanently delete ${resumeResult.filename}, its saved comparisons, and career plans? Application tracker entries will remain.`,
    )
    if (!confirmed) return

    setIsDeletingResume(true)
    setResumeError('')
    setResumeMessage('')
    try {
      const response = await authenticatedFetch(
        `${API_BASE_URL}/api/v1/resumes/${resumeResult.id}`,
        { method: 'DELETE' },
      )
      if (!response.ok) {
        const result = await response.json()
        throw new Error(typeof result.detail === 'string' ? result.detail : 'The resume could not be deleted.')
      }
      setResumeFile(null)
      setResumeResult(null)
      setMatchResult(null)
      setCareerAnalysis(null)
      setAnalysisError('')
      setResumeMessage('Resume deleted. Its saved comparisons and career plans were removed.')
      refreshDashboard()
    } catch (error) {
      setResumeError(error instanceof Error ? error.message : 'Could not reach the CareerLens API.')
    } finally {
      setIsDeletingResume(false)
    }
  }

  async function uploadResume() {
    if (!resumeFile) {
      setResumeError('Choose a PDF or DOCX resume first.')
      return
    }

    const formData = new FormData()
    formData.append('file', resumeFile)
    setIsParsingResume(true)
    setResumeError('')
    setResumeMessage('')

    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/resumes/parse`, {
        method: 'POST',
        body: formData,
      })
      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.detail ?? 'The resume could not be read.')
      }

      setResumeResult(result as ResumeParseResult)
      setMatchResult(null)
      setCareerAnalysis(null)
      setAnalysisError('')
      refreshDashboard()
    } catch (error) {
      setResumeError(
        error instanceof Error
          ? error.message
          : 'Could not reach the backend. Check that it is running.',
      )
    } finally {
      setIsParsingResume(false)
    }
  }

  async function matchJobDescription() {
    if (!resumeResult || !jobDescription.trim()) {
      setMatchError('Upload a resume and add a job description first.')
      return
    }

    setIsMatching(true)
    setMatchError('')
    setCareerAnalysis(null)
    setAnalysisError('')
    setTrackerMessage('')
    setTrackerError('')

    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/jobs/match`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume_id: resumeResult.id,
          job_title: jobTitle.trim() || null,
          job_description: jobDescription,
        }),
      })
      const result = await response.json()

      if (!response.ok) {
        const detail = typeof result.detail === 'string' ? result.detail : 'The match could not be calculated.'
        throw new Error(detail)
      }

      setMatchResult(result as MatchResult)
      setCareerAnalysis(null)
      refreshDashboard()
    } catch (error) {
      setMatchError(
        error instanceof Error
          ? error.message
          : 'Could not reach the backend. Check that it is running.',
      )
    } finally {
      setIsMatching(false)
    }
  }

  async function generateCareerPlan() {
    if (!matchResult) return

    setIsAnalyzing(true)
    setAnalysisError('')
    try {
      const response = await authenticatedFetch(
        `${API_BASE_URL}/api/v1/jobs/matches/${matchResult.id}/analysis`,
        { method: 'POST' },
      )
      const result = await response.json()
      if (!response.ok) {
        throw new Error(typeof result.detail === 'string' ? result.detail : 'The career plan could not be generated.')
      }
      setCareerAnalysis(result as CareerAnalysis)
    } catch (error) {
      setAnalysisError(error instanceof Error ? error.message : 'Could not reach the backend.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  async function addToApplicationTracker() {
    if (!matchResult || !jobTitle.trim()) {
      setTrackerError('Add a job title before saving this role to the tracker.')
      return
    }

    setIsSavingApplication(true)
    setTrackerError('')
    setTrackerMessage('')

    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/applications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          match_id: matchResult.id,
          job_title: jobTitle.trim(),
          company: company.trim() || null,
        }),
      })
      const result = await response.json()
      if (!response.ok) {
        throw new Error(typeof result.detail === 'string' ? result.detail : 'The role could not be saved.')
      }

      setTrackerMessage('Added to your application tracker.')
      refreshDashboard()
    } catch (error) {
      setTrackerError(error instanceof Error ? error.message : 'Could not reach the backend.')
    } finally {
      setIsSavingApplication(false)
    }
  }

  async function updateApplicationStatus(applicationId: number, status: string) {
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/v1/applications/${applicationId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      if (!response.ok) {
        throw new Error('The application status could not be updated.')
      }
      const updated = (await response.json()) as Application
      setApplications((current) => current.map((application) => (
        application.id === updated.id ? updated : application
      )))
      refreshDashboard()
    } catch (error) {
      setDashboardError(error instanceof Error ? error.message : 'Could not update the tracker.')
    }
  }

  if (!accessToken) {
    return (
      <main className="auth-page">
        <section className="auth-card" aria-labelledby="auth-title">
          <a className="brand auth-brand" href="#top">
            <span className="brand-mark" aria-hidden="true">C</span>
            <span>CareerLens</span>
          </a>
          <p className="eyebrow">YOUR LOCAL CAREER WORKSPACE</p>
          <h1 id="auth-title">{authMode === 'register' ? 'Create your account' : 'Welcome back'}</h1>
          <p className="auth-copy">
            Your account keeps your resumes, matches, and application tracker separate from other accounts on this local app.
          </p>
          <form className="auth-form" onSubmit={submitAuthentication}>
            <label htmlFor="auth-email">Email address</label>
            <input
              id="auth-email"
              type="email"
              autoComplete="email"
              value={authEmail}
              onChange={(event) => setAuthEmail(event.target.value)}
              required
            />
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              autoComplete={authMode === 'register' ? 'new-password' : 'current-password'}
              minLength={8}
              maxLength={256}
              value={authPassword}
              onChange={(event) => setAuthPassword(event.target.value)}
              required
            />
            <p className="auth-hint">Use at least 8 characters. This local prototype keeps you signed in for up to 60 minutes per browser tab.</p>
            {authNotice && <p className="success-message" role="status">{authNotice}</p>}
            {authError && <p className="api-status error-message" role="alert">{authError}</p>}
            <button className="check-button" type="submit" disabled={isAuthenticating}>
              {isAuthenticating ? 'Please wait…' : authMode === 'register' ? 'Create account' : 'Sign in'}
            </button>
          </form>
          <p className="auth-switch">
            {authMode === 'register' ? 'Already have an account?' : 'New to CareerLens?'}{' '}
            <button
              type="button"
              onClick={() => {
                setAuthMode(authMode === 'register' ? 'login' : 'register')
                setAuthError('')
              }}
            >
              {authMode === 'register' ? 'Sign in' : 'Create an account'}
            </button>
          </p>
        </section>
      </main>
    )
  }

  return (
    <main className="page">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="CareerLens home">
          <span className="brand-mark" aria-hidden="true">C</span>
          <span>CareerLens</span>
        </a>
        <div className="topbar-actions">
          <a className="topbar-link" href="#dashboard">Your dashboard</a>
          <button className="sign-out-button" type="button" onClick={signOut}>Sign out</button>
        </div>
      </header>

      <section className="hero" id="top" aria-labelledby="hero-title">
        <p className="eyebrow">YOUR CAREER, IN FOCUS</p>
        <h1 id="hero-title">Make your next move <span>with confidence.</span></h1>
        <p className="hero-copy">
          Understand how your experience fits the role you want, then get a
          practical plan for what to do next.
        </p>
        <a className="primary-link" href="#analysis">Start an analysis <span aria-hidden="true">↓</span></a>
      </section>

      <section className="input-section" id="analysis" aria-labelledby="input-title">
        <div className="input-card">
          <p className="eyebrow">START YOUR ANALYSIS</p>
          <h2 id="input-title">Add a resume and a job description</h2>
          <p className="input-description">
            Resumes and comparisons are saved locally. You can reuse a saved resume after reopening the app.
          </p>

          <div className="resume-upload">
            {savedResumes.length > 0 && (
              <div className="saved-resume-picker">
                <label htmlFor="saved-resume">Or choose a saved resume</label>
                <select
                  className="text-input"
                  id="saved-resume"
                  value={resumeResult?.id ?? ''}
                  onChange={chooseSavedResume}
                >
                  <option value="">Choose a saved resume</option>
                  {savedResumes.map((resume) => (
                    <option key={resume.id} value={resume.id}>
                      {resume.filename} · {resume.resume_score}% complete
                    </option>
                  ))}
                </select>
              </div>
            )}
            <label htmlFor="resume-file">Resume file (PDF or DOCX)</label>
            <input
              key={resumeResult?.id ?? 'new-resume'}
              id="resume-file"
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={handleResumeSelection}
            />
            <button
              className="check-button"
              type="button"
              onClick={uploadResume}
              disabled={isParsingResume}
            >
              {isParsingResume ? 'Reading resume...' : 'Upload and read resume'}
            </button>
            {resumeError && <p className="api-status error-message" role="alert">{resumeError}</p>}
            {resumeMessage && <p className="success-message" role="status">{resumeMessage}</p>}
            {resumeResult && (
              <div className="resume-result" role="status">
                <h3>Resume read and saved</h3>
                <p className="result-meta">
                  {resumeResult.filename} · {resumeResult.character_count.toLocaleString()} characters
                </p>
                <p className="resume-score-badge">Completeness score: {resumeResult.resume_score}%</p>
                <p className="result-label">Skills found</p>
                {resumeResult.skills.length > 0 ? (
                  <ul className="skill-list">
                    {resumeResult.skills.map((skill) => <li key={skill}>{skill}</li>)}
                  </ul>
                ) : (
                  <p className="result-meta">No skills from the starter list were found.</p>
                )}
                <div className="resume-entry-groups">
                  <p className="result-label">Experience, education, and project entries</p>
                  <p className="result-meta">
                    These groups are based on common resume formatting. Check the original text below for accuracy.
                  </p>
                  {(['experience', 'education', 'projects'] as const).map((section) => (
                    <details className="resume-entry-group" key={section}>
                      <summary>{section} ({resumeResult.entries[section].length})</summary>
                      {resumeResult.entries[section].length > 0 ? (
                        <ol className="resume-entry-list">
                          {resumeResult.entries[section].map((entry, index) => (
                            <li key={`${section}-${index}`}>
                              <strong>{entry.heading}</strong>
                              {entry.details.map((detail, detailIndex) => (
                                <p key={`${section}-${index}-${detailIndex}`}>{detail}</p>
                              ))}
                            </li>
                          ))}
                        </ol>
                      ) : (
                        <p className="result-meta">No {section} entries were detected.</p>
                      )}
                    </details>
                  ))}
                </div>
                <details className="extracted-sections">
                  <summary>View extracted text and sections</summary>
                  {Object.entries(resumeResult.sections).map(([section, sectionText]) => (
                    <div className="extracted-section" key={section}>
                      <h4>{section}</h4>
                      <pre>{sectionText}</pre>
                    </div>
                  ))}
                  <pre>{resumeResult.text}</pre>
                </details>
                <button
                  className="danger-button"
                  type="button"
                  onClick={deleteSavedResume}
                  disabled={isDeletingResume}
                >
                  {isDeletingResume ? 'Deleting resume…' : 'Delete this saved resume'}
                </button>
              </div>
            )}
          </div>

          <div className="role-fields">
            <div>
              <label htmlFor="job-title">Job title</label>
              <input
                className="text-input"
                id="job-title"
                maxLength={255}
                value={jobTitle}
                onChange={(event) => setJobTitle(event.target.value)}
                placeholder="e.g. Python Developer"
              />
            </div>
            <div>
              <label htmlFor="company">Company (optional)</label>
              <input
                className="text-input"
                id="company"
                maxLength={255}
                value={company}
                onChange={(event) => setCompany(event.target.value)}
                placeholder="e.g. Northstar Learning"
              />
            </div>
          </div>

          <label htmlFor="job-description">Job description</label>
          <textarea
            id="job-description"
            rows={6}
            maxLength={50000}
            value={jobDescription}
            onChange={(event) => {
              setJobDescription(event.target.value)
              setMatchResult(null)
              setMatchError('')
            }}
            placeholder="Paste the job description here..."
          />
          <div className="input-footer">
            <span className="character-count" aria-live="polite">
              {jobDescription.length} characters
            </span>
            <span className="input-note">Saved locally when you compare</span>
          </div>
          <button
            className="check-button match-button"
            type="button"
            onClick={matchJobDescription}
            disabled={isMatching || !resumeResult || !jobDescription.trim()}
          >
            {isMatching ? 'Comparing...' : 'Compare resume with this role'}
          </button>
          {matchError && <p className="api-status" role="alert">{matchError}</p>}
          {matchResult && (
            <section className="match-result" aria-labelledby="match-result-title">
              <div className="score-row">
                <div>
                  <p className="eyebrow">STARTER KEYWORD MATCH</p>
                  <h3 id="match-result-title">Your role comparison</h3>
                </div>
                <strong className="score-value">{matchResult.match_score}%</strong>
              </div>
              <p className="match-explanation">{matchResult.explanation}</p>
              <div className="match-columns">
                <div>
                  <h4>Skills found in both</h4>
                  {matchResult.matching_skills.length > 0 ? (
                    <ul className="skill-list">
                      {matchResult.matching_skills.map((skill) => <li key={skill}>{skill}</li>)}
                    </ul>
                  ) : <p className="result-meta">No shared skills found in the starter list.</p>}
                </div>
                <div>
                  <h4>Skills to explore</h4>
                  {matchResult.missing_skills.length > 0 ? (
                    <ul className="skill-list missing-skills">
                      {matchResult.missing_skills.map((skill) => <li key={skill}>{skill}</li>)}
                    </ul>
                  ) : <p className="result-meta">No missing skills from the starter list.</p>}
                </div>
              </div>
              <p className="match-disclaimer">
                This starter score only compares a small keyword list. It does not judge your overall qualifications.
              </p>
              <div className="career-plan-action">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={generateCareerPlan}
                  disabled={isAnalyzing}
                >
                  {isAnalyzing ? 'Building your plan...' : 'Create a career plan'}
                </button>
                <span>Uses local rules by default; configure Ollama for on-device AI.</span>
              </div>
              {analysisError && <p className="api-status" role="alert">{analysisError}</p>}
              {careerAnalysis && (
                <div className="career-plan" aria-labelledby="career-plan-title">
                  <div className="career-plan-heading">
                    <div>
                      <p className="eyebrow">
                        {careerAnalysis.analysis_method === 'ollama_local'
                          ? 'ON-DEVICE AI CAREER PLAN'
                          : 'LOCAL RULES CAREER PLAN'}
                      </p>
                      <h3 id="career-plan-title">A practical way forward</h3>
                    </div>
                    <span>
                      {careerAnalysis.analysis_method === 'ollama_local'
                        ? 'Ollama model'
                        : 'Rule-based starter'}
                    </span>
                  </div>
                  {careerAnalysis.analysis_method === 'ollama_local' && (
                    <p className="result-meta">AI suggestions can be imperfect. Check every recommendation against your actual experience.</p>
                  )}
                  <div className="plan-section">
                    <h4>Resume improvements</h4>
                    <ul className="plain-list">
                      {careerAnalysis.resume_suggestions.map((suggestion) => <li key={suggestion}>{suggestion}</li>)}
                    </ul>
                  </div>
                  <div className="plan-section">
                    <h4>Skill priorities</h4>
                    {careerAnalysis.recommended_skills.length > 0 ? (
                      <ul className="skill-list">
                        {careerAnalysis.recommended_skills.map((skill) => <li key={skill}>{skill}</li>)}
                      </ul>
                    ) : <p className="result-meta">No gaps from the starter skills list were found.</p>}
                  </div>
                  <div className="plan-section">
                    <h4>Roadmap</h4>
                    <ol className="roadmap-list">
                      {careerAnalysis.roadmap.map((step) => (
                        <li key={step.timeframe}>
                          <strong>{step.timeframe}: {step.focus}</strong>
                          <p>{step.action}</p>
                        </li>
                      ))}
                    </ol>
                  </div>
                  {careerAnalysis.project_recommendations.length > 0 && (
                    <div className="plan-section">
                      <h4>Project ideas</h4>
                      <ul className="plain-list">
                        {careerAnalysis.project_recommendations.map((project) => (
                          <li key={project.skill}><strong>{project.skill}:</strong> {project.idea}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="plan-section">
                    <h4>Interview practice</h4>
                    <ol className="plain-list">
                      {careerAnalysis.interview_questions.map((question) => <li key={question}>{question}</li>)}
                    </ol>
                  </div>
                </div>
              )}
              <div className="tracker-save">
                <button
                  className="secondary-button"
                  type="button"
                  onClick={addToApplicationTracker}
                  disabled={isSavingApplication || !jobTitle.trim()}
                >
                  {isSavingApplication ? 'Saving...' : 'Add role to application tracker'}
                </button>
                {trackerMessage && <p className="success-message" role="status">{trackerMessage}</p>}
                {trackerError && <p className="api-status" role="alert">{trackerError}</p>}
              </div>
            </section>
          )}
        </div>
      </section>

      <section className="dashboard-section" id="dashboard" aria-labelledby="dashboard-title">
        <div className="dashboard-heading">
          <div>
            <p className="eyebrow">YOUR WORKSPACE</p>
            <h2 id="dashboard-title">Career dashboard</h2>
          </div>
          <button className="secondary-button refresh-button" type="button" onClick={refreshDashboard}>
            Refresh data
          </button>
        </div>
        {dashboardError && <p className="api-status" role="alert">{dashboardError}</p>}
        {!dashboard ? (
          <p className="dashboard-loading">Loading your local career data…</p>
        ) : (
          <>
            <div className="dashboard-metrics">
              <article className="metric-card">
                <span>Resumes saved</span>
                <strong>{dashboard.resume_count}</strong>
              </article>
              <article className="metric-card">
                <span>Role comparisons</span>
                <strong>{dashboard.match_count}</strong>
              </article>
              <article className="metric-card">
                <span>Resume completeness</span>
                <strong>{dashboard.latest_resume ? `${dashboard.latest_resume.resume_score}%` : '—'}</strong>
              </article>
              <article className="metric-card">
                <span>Average match</span>
                <strong>{dashboard.match_count ? `${dashboard.average_match_score}%` : '—'}</strong>
              </article>
              <article className="metric-card">
                <span>Applications tracked</span>
                <strong>{dashboard.application_count}</strong>
              </article>
            </div>

            <div className="dashboard-panels">
              <SkillCoverageChart coverage={dashboard.skill_coverage} />
            </div>
            <div className="dashboard-panels">
              <section className="dashboard-panel" aria-labelledby="recent-matches-title">
                <h3 id="recent-matches-title">Match score history</h3>
                <MatchScoreChart matches={dashboard.recent_matches} />
                {dashboard.recent_matches.length > 0 && (
                  <ul className="recent-list">
                    {dashboard.recent_matches.map((match) => (
                      <li className="recent-match" key={match.id}>
                        <div className="recent-match-heading">
                          <div>
                            <strong>{match.job_title}</strong>
                            <span>{match.resume_filename}</span>
                          </div>
                          <strong className="recent-score">{match.match_score}%</strong>
                        </div>
                        <time>{match.created_at ? new Date(match.created_at).toLocaleDateString() : 'Recently'}</time>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="dashboard-panel" aria-labelledby="application-tracker-title">
                <h3 id="application-tracker-title">Application tracker</h3>
                <ApplicationStatusChart counts={dashboard.application_counts} total={dashboard.application_count} />
                {applications.length === 0 ? (
                  <p className="empty-state">Save a role after comparing it to track your applications.</p>
                ) : (
                  <ul className="application-list">
                    {applications.map((application) => (
                      <li className="application-row" key={application.id}>
                        <div>
                          <strong>{application.job_title}</strong>
                          <span>{application.company || 'Company not added'}</span>
                        </div>
                        <select
                          className="status-select"
                          aria-label={`Status for ${application.job_title}`}
                          value={application.status}
                          onChange={(event) => void updateApplicationStatus(application.id, event.target.value)}
                        >
                          {APPLICATION_STATUSES.map((status) => (
                            <option key={status} value={status}>{status}</option>
                          ))}
                        </select>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="dashboard-panel latest-resume-panel" aria-labelledby="latest-resume-title">
                <h3 id="latest-resume-title">Latest resume</h3>
                {dashboard.latest_resume ? (
                  <>
                    <p className="latest-filename">{dashboard.latest_resume.filename}</p>
                    <p className="result-label">Recognized skills</p>
                    <ul className="skill-list">
                      {dashboard.latest_resume.skills.map((skill) => <li key={skill}>{skill}</li>)}
                    </ul>
                    {dashboard.latest_resume.resume_score_notes.length > 0 && (
                      <details className="score-feedback">
                        <summary>Ways to improve completeness</summary>
                        <ul className="plain-list">
                          {dashboard.latest_resume.resume_score_notes.map((note) => <li key={note}>{note}</li>)}
                        </ul>
                      </details>
                    )}
                  </>
                ) : <p className="empty-state">Upload a resume to see its recognized skills here.</p>}
              </section>
            </div>
          </>
        )}
      </section>

      <section className="account-settings" aria-labelledby="account-settings-title">
        <div className="account-settings-card">
          <div className="account-settings-copy">
            <p className="eyebrow">ACCOUNT CONTROLS</p>
            <h2 id="account-settings-title">Manage your local account</h2>
            <p>Delete your account when you are done. CareerLens will remove its resumes, comparisons, career plans, and tracker entries from this database.</p>
          </div>
          <div className="account-settings-action">
            {!showDeleteAccountForm ? (
              <button
                className="danger-button"
                type="button"
                onClick={() => {
                  setDeleteAccountError('')
                  setShowDeleteAccountForm(true)
                }}
              >
                Delete my account
              </button>
            ) : (
              <form className="delete-account-form" onSubmit={deleteAccount}>
                <label htmlFor="delete-account-password">Confirm with your current password</label>
                <input
                  id="delete-account-password"
                  type="password"
                  autoComplete="current-password"
                  minLength={8}
                  maxLength={256}
                  value={deleteAccountPassword}
                  onChange={(event) => setDeleteAccountPassword(event.target.value)}
                  required
                />
                <label className="delete-account-confirm">
                  <input type="checkbox" required />
                  I understand this permanently deletes all of my CareerLens data.
                </label>
                {deleteAccountError && <p className="api-status error-message" role="alert">{deleteAccountError}</p>}
                <div className="delete-account-actions">
                  <button className="danger-button" type="submit" disabled={isDeletingAccount}>
                    {isDeletingAccount ? 'Deleting…' : 'Permanently delete account'}
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    onClick={() => {
                      setShowDeleteAccountForm(false)
                      setDeleteAccountPassword('')
                      setDeleteAccountError('')
                    }}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      </section>

      <section className="steps" id="how-it-works" aria-labelledby="steps-title">
        <div className="section-heading">
          <p className="eyebrow">THREE SIMPLE STEPS</p>
          <h2 id="steps-title">Turn your experience into a plan</h2>
        </div>
        <div className="step-grid">
          <article className="step-card">
            <span className="step-number">01</span>
            <h3>Bring your resume</h3>
            <p>Start with the experience, skills, and projects you already have.</p>
          </article>
          <article className="step-card">
            <span className="step-number">02</span>
            <h3>Choose a role</h3>
            <p>Add a job description to see what the role asks for.</p>
          </article>
          <article className="step-card">
            <span className="step-number">03</span>
            <h3>Get your next steps</h3>
            <p>Find strengths to highlight and skills to build for your goal.</p>
          </article>
        </div>
      </section>

      <footer className="footer">
        <span className="footer-brand">CareerLens</span>
        <span>Built to help you move forward.</span>
      </footer>
    </main>
  )
}

export default App
