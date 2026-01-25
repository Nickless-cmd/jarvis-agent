export default function Footer() {
  const buildCommit = (import.meta.env.VITE_BUILD_COMMIT as string) || 'dev'
  const buildCommitFull = (import.meta.env.VITE_BUILD_COMMIT_FULL as string) || 'unknown'
  const repoUrl = (import.meta.env.VITE_REPO_URL as string) || 'https://github.com'
  const commitUrl = buildCommitFull !== 'unknown' ? `${repoUrl}/commit/${buildCommitFull}` : '#'
  const year = new Date().getFullYear()

  return (
    <footer className="h-auto shrink-0 border-t border-neutral-800 bg-neutral-900/80 backdrop-blur px-4 py-3 text-xs text-neutral-500">
      <div className="flex items-center justify-between gap-4">
        <div>
          © {year} Jarvis AI ·{' '}
          <a href={commitUrl} target="_blank" rel="noopener noreferrer" className="text-emerald-400 hover:text-emerald-300">
            Build: {buildCommit}
          </a>
        </div>
        <div className="flex items-center justify-center gap-3 flex-1">
          <a href="#support" className="hover:text-neutral-300">Support</a>
          <span>·</span>
          <a href={repoUrl} target="_blank" rel="noopener noreferrer" className="hover:text-neutral-300">GitHub</a>
          <span>·</span>
          <a href={`${repoUrl}/blob/main/LICENSE`} target="_blank" rel="noopener noreferrer" className="hover:text-neutral-300">License</a>
        </div>
        <div className="text-right text-[10px]" title={new Date().toISOString()}>
          Latest
        </div>
      </div>
    </footer>
  )
}
