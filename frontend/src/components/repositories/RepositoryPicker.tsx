import { Check, ChevronDown, GitBranch, Loader2, Search } from 'lucide-react'
import type { Repository } from '../../lib/repositoryAdapter'
import { useRepositoryPicker } from './useRepositoryPicker'

type RepositoryPickerProps = {
  value: string
  onSelect: (repository: Repository) => void
}

export function RepositoryPicker({ value, onSelect }: RepositoryPickerProps) {
  const {
    error,
    filteredRepositories,
    isLoading,
    isOpen,
    search,
    closeMenu,
    toggleMenu,
    updateSearch,
  } = useRepositoryPicker()

  if (error) return <div className="repository-error" role="alert">{error}</div>

  return (
    <div className="repository-picker">
      <button className="repository-trigger" type="button" onClick={toggleMenu} aria-expanded={isOpen}>
        <GitBranch size={16} />
        <span>{value || (isLoading ? 'Loading repositories...' : 'Select repository')}</span>
        {isLoading ? <Loader2 className="spin" size={14} /> : <ChevronDown size={15} />}
      </button>
      {isOpen && !isLoading && <div className="repository-menu">
        <div className="repository-search"><Search size={14} /><input autoFocus value={search} onChange={(event) => updateSearch(event.target.value)} placeholder="Search repositories" aria-label="Search repositories" /></div>
        <div role="listbox" aria-label="Repositories">
          {filteredRepositories.map((repository) => <button role="option" aria-selected={repository.fullName === value} key={`${repository.provider}:${repository.id}`} onClick={() => { onSelect(repository); closeMenu() }}><span><strong>{repository.fullName}</strong><small>{repository.providerLabel} · {repository.description ?? 'No description'}</small></span>{repository.fullName === value && <Check size={15} />}</button>)}
        </div>
      </div>}
    </div>
  )
}
