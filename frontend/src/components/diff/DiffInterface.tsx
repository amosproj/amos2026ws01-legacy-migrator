import React, { useEffect, useState } from 'react'
import { AlertTriangle, ChevronDown, FileCode2, GitCompare, Loader2, Play } from 'lucide-react'
import { explainDiff, listRepositories } from '../../services/diffApi'
import { DiffExplanation, Repository } from '../../types/diff'

export const DiffInterface: React.FC = () => {
  const [repositories, setRepositories] = useState<Repository[]>([])
  const [repository, setRepository] = useState('')
  const [base, setBase] = useState('')
  const [head, setHead] = useState('main')
  const [result, setResult] = useState<DiffExplanation | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isLoadingRepositories, setIsLoadingRepositories] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    listRepositories(controller.signal)
      .then((items) => {
        setRepositories(items)
        if (items[0]) {
          setRepository(items[0].fullName)
          setBase(items[0].defaultBranch)
          setHead(items[0].branches?.find((branch) => branch !== items[0].defaultBranch) ?? items[0].defaultBranch)
        }
      })
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted) setError(requestError instanceof Error ? requestError.message : 'Repositories could not be loaded.')
      })
      .finally(() => setIsLoadingRepositories(false))
    return () => controller.abort()
  }, [])

  const selectedRepository = repositories.find((item) => item.fullName === repository)
  const branches = selectedRepository?.branches?.length
    ? selectedRepository.branches
    : selectedRepository ? [selectedRepository.defaultBranch] : []

  const selectRepository = (value: string) => {
    const nextRepository = repositories.find((item) => item.fullName === value)
    const nextBranches = nextRepository?.branches?.length
      ? nextRepository.branches
      : nextRepository ? [nextRepository.defaultBranch] : []
    setRepository(value)
    setBase(nextRepository?.defaultBranch ?? '')
    setHead(nextBranches.find((branch) => branch !== nextRepository?.defaultBranch) ?? nextRepository?.defaultBranch ?? '')
    setResult(null)
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!selectedRepository || !base.trim() || !head.trim() || isLoading) return
    setError(null)
    setResult(null)
    setIsLoading(true)
    try {
      setResult(await explainDiff({ repository, provider: selectedRepository.provider, base: base.trim(), head: head.trim() }))
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : 'The comparison could not be completed.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <section className="max-w-5xl mx-auto w-full space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-[6px] bg-[#171717] text-white flex items-center justify-center"><GitCompare className="w-4 h-4" /></div>
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Change explanations</h1>
          <p className="text-xs text-[#737373]">Compare GitHub revisions and understand migration risk.</p>
        </div>
      </div>

      <form onSubmit={submit} className="grid gap-3 md:grid-cols-[1.5fr_1fr_1fr_auto] items-end border border-[#ebebeb] bg-white rounded-[6px] p-4">
        <label className="text-xs font-mono text-[#525252]">Repository
          <select value={repository} onChange={(event) => selectRepository(event.target.value)} disabled={isLoadingRepositories} className="mt-1 block w-full border border-[#ebebeb] rounded-[5px] px-2 py-2 text-sm bg-white">
            <option value="">{isLoadingRepositories ? 'Loading repositories...' : 'Select repository'}</option>
            {repositories.map((item) => <option key={`${item.provider}:${item.id}`} value={item.fullName}>{item.fullName}</option>)}
          </select>
        </label>
        <label className="text-xs font-mono text-[#525252]">Base branch
          <select value={base} onChange={(event) => setBase(event.target.value)} disabled={!branches?.length} className="mt-1 block w-full border border-[#ebebeb] rounded-[5px] px-2 py-2 text-sm bg-white">
            {!branches?.length && <option value="">Select repository first</option>}
            {branches?.map((branch) => <option key={branch} value={branch}>{branch}</option>)}
          </select>
        </label>
        <label className="text-xs font-mono text-[#525252]">Head branch
          <select value={head} onChange={(event) => setHead(event.target.value)} disabled={!branches?.length} className="mt-1 block w-full border border-[#ebebeb] rounded-[5px] px-2 py-2 text-sm bg-white">
            {!branches?.length && <option value="">Select repository first</option>}
            {branches?.map((branch) => <option key={branch} value={branch}>{branch}</option>)}
          </select>
        </label>
        <button type="submit" disabled={!selectedRepository || !base.trim() || !head.trim() || isLoading} className="h-9 px-3 rounded-[5px] bg-[#171717] text-white text-xs font-medium flex items-center justify-center gap-1.5 disabled:opacity-30">
          {isLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />} Explain changes
        </button>
      </form>

      {error && <div role="alert" className="flex items-center gap-2 p-3 rounded-[6px] bg-[#fef2f2] border border-[#fecaca] text-xs text-[#991b1b]"><AlertTriangle className="w-4 h-4" />{error}</div>}
      {isLoading && <div className="flex items-center justify-center gap-2 p-10 border border-[#ebebeb] rounded-[6px] text-xs font-mono text-[#737373]"><Loader2 className="w-4 h-4 animate-spin" />Analyzing changed files...</div>}
      {result && <DiffResult result={result} />}
    </section>
  )
}

function DiffResult({ result }: { result: DiffExplanation }) {
  return <div className="space-y-3">
    <div className="flex items-start justify-between gap-4 p-4 rounded-[6px] border border-[#dbeafe] bg-[#eff6ff]">
      <div><span className="text-[10px] uppercase tracking-wider font-mono text-[#2563eb]">Comparison summary</span><p className="mt-1 text-sm leading-relaxed">{result.summary}</p></div>
      <span className="shrink-0 text-[10px] uppercase font-mono font-semibold px-2 py-1 rounded-[4px] bg-white border border-[#bfdbfe]">{result.risk} risk</span>
    </div>
    {result.warnings.map((warning) => <div key={warning} className="flex gap-2 p-3 rounded-[6px] bg-[#fffbeb] border border-[#fde68a] text-xs text-[#92400e]"><AlertTriangle className="w-4 h-4 shrink-0" />{warning}</div>)}
    <div className="space-y-2">
      {result.files.map((file) => <details key={file.path} className="group border border-[#ebebeb] rounded-[6px] bg-white overflow-hidden">
        <summary className="flex items-center gap-2 px-3 py-3 cursor-pointer list-none text-xs">
          <ChevronDown className="w-3.5 h-3.5 group-open:rotate-180 transition-transform" /><FileCode2 className="w-3.5 h-3.5 text-[#737373]" /><code className="flex-1">{file.path}</code><span className="text-[#059669]">+{file.additions}</span><span className="text-[#dc2626]">-{file.deletions}</span><span className="text-[#737373] capitalize">{file.status}</span>
        </summary>
        <div className="px-10 pb-3 space-y-2"><p className="text-xs text-[#525252]">{file.explanation}</p><pre className="p-3 rounded-[4px] bg-[#171717] text-[#f5f5f5] text-[11px] overflow-x-auto"><code>{file.patch}</code></pre></div>
      </details>)}
    </div>
  </div>
}
