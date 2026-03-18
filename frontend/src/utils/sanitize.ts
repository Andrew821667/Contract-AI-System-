/**
 * HTML sanitization utility (L2)
 *
 * Use this instead of dangerouslySetInnerHTML when rendering
 * any content that could contain user-generated HTML.
 */
import DOMPurify from 'dompurify'

/**
 * Sanitize HTML string, removing all potentially dangerous tags/attributes.
 * Safe for rendering via dangerouslySetInnerHTML.
 */
export function sanitizeHTML(dirty: string): string {
  if (typeof window === 'undefined') {
    // SSR: strip all HTML tags as a safe fallback
    return dirty.replace(/<[^>]*>/g, '')
  }
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: [
      'b', 'i', 'em', 'strong', 'u', 'br', 'p', 'span',
      'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3', 'h4',
      'table', 'thead', 'tbody', 'tr', 'th', 'td',
      'blockquote', 'code', 'pre', 'mark', 'del', 'ins',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class'],
  })
}

/**
 * Create a safe dangerouslySetInnerHTML prop.
 *
 * Usage:
 *   <div {...safeHTML(htmlString)} />
 */
export function safeHTML(dirty: string) {
  return { dangerouslySetInnerHTML: { __html: sanitizeHTML(dirty) } }
}
