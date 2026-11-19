import React, { useEffect, useState } from 'react';
interface LegalNoticesProps { onClose: () => void; }
export const LegalNotices: React.FC<LegalNoticesProps> = ({ onClose }) => {
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    fetch('/legal/THIRD_PARTY_NOTICES.md')
      .then((response) => { if (!response.ok) throw new Error('Unable to load legal notices'); return response.text(); })
      .then(setContent).catch(() => setError(true));
  }, []);
  return (
    <div className="fixed inset-0 z-[100] bg-black/40 p-4 flex items-center justify-center" role="presentation">
      <section role="dialog" aria-modal="true" aria-labelledby="legal-notices-title" className="bg-white max-w-3xl w-full max-h-[85vh] overflow-auto rounded-lg p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 id="legal-notices-title" className="text-lg font-semibold">Legal Notices</h2>
          <button onClick={onClose} className="border rounded px-3 py-1 text-sm">Close</button>
        </div>
        {content === null && !error && <p>Loading legal notices…</p>}
        {error && <p role="alert">Legal notices could not be loaded.</p>}
        {content !== null && <pre className="whitespace-pre-wrap break-words text-xs leading-relaxed font-mono">{content}</pre>}
      </section>
    </div>
  );
};
