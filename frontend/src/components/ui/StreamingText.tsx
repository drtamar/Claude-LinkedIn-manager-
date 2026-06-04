import { cn } from '../../lib/utils'

interface StreamingTextProps {
  text: string
  isStreaming?: boolean
  className?: string
  placeholder?: string
}

export function StreamingText({ text, isStreaming, className, placeholder }: StreamingTextProps) {
  if (!text && !isStreaming) {
    return (
      <span className={cn('text-gray-400 italic', className)}>
        {placeholder || 'Waiting for AI response...'}
      </span>
    )
  }
  return (
    <span className={cn('whitespace-pre-wrap', isStreaming && 'streaming-cursor', className)}>
      {text}
    </span>
  )
}
