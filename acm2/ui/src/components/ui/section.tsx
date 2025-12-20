import * as React from 'react'
import { cn } from '../../lib/utils'
import { ChevronDown } from 'lucide-react'

interface SectionProps {
  title: string
  icon?: React.ReactNode
  defaultExpanded?: boolean
  className?: string
  children: React.ReactNode
}

export function Section({
  title,
  icon,
  defaultExpanded = true,
  className,
  children,
}: SectionProps) {
  const [expanded, setExpanded] = React.useState(defaultExpanded)

  return (
    <div
      className={cn(
        'rounded-lg border border-gray-700 bg-gray-800/50',
        className
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-800 hover:bg-gray-750 transition-colors"
      >
        <div className="flex items-center gap-2">
          {icon && <span className="text-blue-400">{icon}</span>}
          <span className="font-semibold text-gray-200">{title}</span>
        </div>
        <ChevronDown
          className={cn(
            'w-5 h-5 text-gray-400 transition-transform',
            expanded && 'rotate-180'
          )}
        />
      </button>
      {expanded && <div className="p-4 space-y-4">{children}</div>}
    </div>
  )
}

interface SectionGridProps {
  cols?: 1 | 2 | 3 | 4
  className?: string
  children: React.ReactNode
}

export function SectionGrid({ cols = 2, className, children }: SectionGridProps) {
  const gridCols = {
    1: 'grid-cols-1',
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
  }

  return (
    <div className={cn('grid gap-4', gridCols[cols], className)}>
      {children}
    </div>
  )
}
