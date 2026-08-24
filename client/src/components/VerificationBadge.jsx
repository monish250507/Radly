import React from 'react';

/**
 * VerificationBadge — minimal visual indicator for verification status.
 *
 * Renders an inline badge showing what level of confidence we have in a
 * finding. Does NOT expose internal implementation details (no artifact IDs,
 * no evidence type names in normal mode).
 *
 * Props:
 *   status    {string}  — VerificationStatus value
 *   size      {string}  — 'xs' | 'sm' (default: 'xs')
 *   showLabel {boolean} — show the status label text (default: true)
 */
export default function VerificationBadge({ status, size = 'xs', showLabel = true }) {
  const s = (status || 'UNABLE_TO_VERIFY').toUpperCase();

  const config = {
    VERIFIED: {
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/20',
      text: 'text-emerald-600',
      label: 'VERIFIED',
      icon: '✓',
      title: 'Deterministically verified. Reproducible evidence established this finding.'
    },
    LIKELY: {
      bg: 'bg-sky-500/10',
      border: 'border-sky-500/20',
      text: 'text-sky-600',
      label: 'LIKELY',
      icon: '◎',
      title: 'Multiple converging signals make this finding highly plausible. Not yet deterministically proven.'
    },
    NEEDS_REVIEW: {
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/20',
      text: 'text-amber-600',
      label: 'NEEDS REVIEW',
      icon: '!',
      title: 'A signal was found (keyword overlap or AI suggestion), but human review is required before treating this as confirmed.'
    },
    NO_DEPENDENCY_FOUND: {
      bg: 'bg-gray-500/10',
      border: 'border-gray-500/20',
      text: 'text-gray-500',
      label: 'NO DEPENDENCY',
      icon: '—',
      title: 'Analysis ran but found no dependency between the proposed change and this element.'
    },
    UNABLE_TO_VERIFY: {
      bg: 'bg-orange-500/10',
      border: 'border-orange-500/20',
      text: 'text-orange-500',
      label: 'UNABLE TO VERIFY',
      icon: '?',
      title: 'A signal was found but could not be validated against the actual document (e.g., AI returned a section ID that does not exist).'
    },
    ANALYSIS_FAILED: {
      bg: 'bg-red-500/10',
      border: 'border-red-500/20',
      text: 'text-red-500',
      label: 'ANALYSIS FAILED',
      icon: '✕',
      title: 'Processing error. No reliable finding can be reported.'
    },
    CONFLICTING_EVIDENCE: {
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/20',
      text: 'text-purple-500',
      label: 'CONFLICTING',
      icon: '⇄',
      title: 'Contradictory evidence was found. This finding requires careful human review.'
    }
  };

  const cfg = config[s] || config.UNABLE_TO_VERIFY;
  const sizeClass = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-[10px] px-1.5 py-0.5';

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono font-semibold rounded-full border ${cfg.bg} ${cfg.border} ${cfg.text} ${sizeClass} leading-none cursor-help shadow-sm`}
      title={cfg.title}
      aria-label={`Verification status: ${cfg.label}`}
    >
      <span aria-hidden="true">{cfg.icon}</span>
      {showLabel && <span>{cfg.label}</span>}
    </span>
  );
}
