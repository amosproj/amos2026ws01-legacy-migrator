import type { FormEvent } from 'react'
import { AlertTriangle, ChevronDown, FileCode2, GitCompare, Loader2, Play, ShieldAlert } from 'lucide-react'
import type { DiffExplanation, DiffFile } from '../../lib/diffAdapter'
import type { Repository } from '../../lib/repositoryAdapter'
import { RepositoryPicker } from '../repositories/RepositoryPicker'
import { useDiffReview, type Comparison } from './useDiffReview'

export function DiffReview() {
  const review = useDiffReview()

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    void review.explainComparison()
  }

  return (
    <section className="diff-page">
      <DiffHeader />
      <DiffControls
        comparison={review.comparison}
        isLoading={review.isLoading}
        onChange={review.updateComparison}
        onRepositorySelect={review.selectRepository}
        onSubmit={handleSubmit}
      />
      {review.error && <div className="error-banner" role="alert">{review.error}</div>}
      {review.isLoading && <LoadingState />}
      {review.result && !review.isLoading && <DiffResults result={review.result} />}
      {!review.result && !review.isLoading && <EmptyState />}
    </section>
  )
}

function DiffHeader() {
  return (
    <div className="diff-title">
      <div className="bot-avatar"><GitCompare size={22} /></div>
      <div>
        <h1>Change explanations</h1>
        <p>Understand what changed between two migration milestones.</p>
      </div>
    </div>
  )
}

type DiffControlsProps = {
  comparison: Comparison
  isLoading: boolean
  onChange: (updates: Partial<Comparison>) => void
  onRepositorySelect: (repository: Repository) => void
  onSubmit: (event: FormEvent) => void
}

function DiffControls({ comparison, isLoading, onChange, onRepositorySelect, onSubmit }: DiffControlsProps) {
  const isSubmitDisabled = isLoading || !comparison.repository || !comparison.base || !comparison.head

  return (
    <form className="diff-toolbar" onSubmit={onSubmit}>
      <label>
        Repository
        <RepositoryPicker value={comparison.repository} onSelect={onRepositorySelect} />
      </label>
      <label htmlFor="base-ref">
        Base
        <input id="base-ref" value={comparison.base} onChange={(event) => onChange({ base: event.target.value })} />
      </label>
      <label htmlFor="head-ref">
        Compare with
        <input id="head-ref" value={comparison.head} onChange={(event) => onChange({ head: event.target.value })} />
      </label>
      <button className="explain-button" type="submit" disabled={isSubmitDisabled}>
        {isLoading ? <Loader2 className="spin" size={16} /> : <Play size={15} />}
        Explain changes
      </button>
    </form>
  )
}

function LoadingState() {
  return <div className="diff-loading"><Loader2 className="spin" size={18} /> Analyzing changed files...</div>
}

function EmptyState() {
  return (
    <div className="diff-empty">
      <GitCompare size={28} />
      <strong>Choose a comparison to get started</strong>
      <span>We’ll summarize the code changes and flag migration risks.</span>
    </div>
  )
}

function DiffResults({ result }: { result: DiffExplanation }) {
  return (
    <div className="diff-results">
      <SummaryCard result={result} />
      <Warnings warnings={result.warnings} />
      <DiffStats files={result.files} />
      <div className="changed-files">
        {result.files.map((file) => <ChangedFile key={file.path} file={file} />)}
      </div>
    </div>
  )
}

function SummaryCard({ result }: { result: DiffExplanation }) {
  return (
    <div className="diff-summary-card">
      <div>
        <span className="eyebrow">AI-generated summary</span>
        <p>{result.summary}</p>
      </div>
      <span className={`risk-badge ${result.risk}`}><ShieldAlert size={14} /> {result.risk} risk</span>
    </div>
  )
}

function Warnings({ warnings }: { warnings: string[] }) {
  return (
    <>
      {warnings.map((warning) => (
        <div className="diff-warning" key={warning}>
          <AlertTriangle size={16} />
          {warning}
        </div>
      ))}
    </>
  )
}

function DiffStats({ files }: { files: DiffFile[] }) {
  const additions = files.reduce((total, file) => total + file.additions, 0)
  const deletions = files.reduce((total, file) => total + file.deletions, 0)

  return (
    <div className="diff-stats">
      <strong>{files.length} changed files</strong>
      <span>{additions} additions</span>
      <span>{deletions} deletions</span>
    </div>
  )
}

function ChangedFile({ file }: { file: DiffFile }) {
  return (
    <details className="changed-file" open>
      <summary>
        <FileCode2 size={16} />
        <span className="file-path">{file.path}</span>
        <span className={`file-status ${file.status}`}>{file.status}</span>
        <span className="file-count additions">+{file.additions}</span>
        <span className="file-count deletions">-{file.deletions}</span>
        <ChevronDown size={16} />
      </summary>
      <div className="file-detail">
        <p>{file.explanation}</p>
        <pre>{file.patch}</pre>
      </div>
    </details>
  )
}
