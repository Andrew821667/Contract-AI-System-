'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import type { Comment } from '@/services/api'
import { useComments, useCreateComment, useReplyToComment, useResolveComment } from '@/hooks/useComments'

interface CommentThreadProps {
  documentId: string
  anchorType?: string
}

export default function CommentThread({ documentId, anchorType }: CommentThreadProps) {
  const { data: comments = [], isLoading } = useComments(documentId, anchorType)
  const createComment = useCreateComment()
  const replyTo = useReplyToComment()
  const resolve = useResolveComment()
  const [newContent, setNewContent] = useState('')
  const [replyingTo, setReplyingTo] = useState<string | null>(null)
  const [replyContent, setReplyContent] = useState('')

  const handleCreate = async () => {
    if (!newContent.trim()) return
    await createComment.mutateAsync({
      documentId,
      content: newContent.trim(),
      anchor_type: anchorType || 'document',
    })
    setNewContent('')
  }

  const handleReply = async (commentId: string) => {
    if (!replyContent.trim()) return
    await replyTo.mutateAsync({ commentId, content: replyContent.trim() })
    setReplyingTo(null)
    setReplyContent('')
  }

  // Group into threads (top-level comments + their replies)
  const topLevel = comments.filter((c: Comment) => !c.parent_comment_id)
  const childrenOf = (parentId: string) =>
    comments.filter((c: Comment) => c.parent_comment_id === parentId)

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200 flex items-center gap-2">
        <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
        </svg>
        Комментарии ({comments.length})
      </h3>

      {/* New comment */}
      <div className="flex gap-2">
        <input
          type="text"
          value={newContent}
          onChange={(e) => setNewContent(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          placeholder="Добавить комментарий..."
          className="flex-1 bg-white dark:bg-dark-800 border border-gray-200 dark:border-dark-700 rounded-lg px-3 py-2 text-sm text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
        />
        <button
          onClick={handleCreate}
          disabled={!newContent.trim() || createComment.isPending}
          className="px-3 py-2 bg-primary-600 hover:bg-primary-700 disabled:opacity-40 text-white text-xs font-medium rounded-lg transition-colors"
        >
          Отправить
        </button>
      </div>

      {isLoading && (
        <p className="text-xs text-gray-400 text-center py-4">Загрузка...</p>
      )}

      {/* Comment threads */}
      <div className="space-y-3">
        {topLevel.map((comment: Comment) => (
          <motion.div
            key={comment.id}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            className={`rounded-xl border p-3 ${
              comment.status === 'resolved'
                ? 'border-green-200 dark:border-green-900/30 bg-green-50/50 dark:bg-green-900/10'
                : 'border-gray-200 dark:border-dark-700 bg-white dark:bg-dark-800'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-gray-700 dark:text-gray-300">
                    {comment.author_id.slice(0, 8)}
                  </span>
                  <span className="text-[10px] text-gray-400">
                    {new Date(comment.created_at).toLocaleString('ru-RU')}
                  </span>
                  {comment.status === 'resolved' && (
                    <span className="text-[10px] text-green-600 dark:text-green-400 font-medium">Закрыт</span>
                  )}
                </div>
                <p className="text-sm text-gray-800 dark:text-gray-200">{comment.content}</p>
              </div>

              {comment.status !== 'resolved' && (
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    onClick={() => setReplyingTo(replyingTo === comment.id ? null : comment.id)}
                    className="p-1 text-gray-400 hover:text-primary-500 transition-colors"
                    title="Ответить"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6" />
                    </svg>
                  </button>
                  <button
                    onClick={() => resolve.mutate(comment.id)}
                    className="p-1 text-gray-400 hover:text-green-500 transition-colors"
                    title="Закрыть"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </button>
                </div>
              )}
            </div>

            {/* Reply input */}
            {replyingTo === comment.id && (
              <div className="mt-2 flex gap-2">
                <input
                  type="text"
                  value={replyContent}
                  onChange={(e) => setReplyContent(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleReply(comment.id)}
                  placeholder="Ответ..."
                  autoFocus
                  className="flex-1 bg-gray-50 dark:bg-dark-900 border border-gray-200 dark:border-dark-700 rounded-lg px-2.5 py-1.5 text-xs text-gray-800 dark:text-gray-200 placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-primary-500"
                />
                <button
                  onClick={() => handleReply(comment.id)}
                  disabled={!replyContent.trim()}
                  className="px-2.5 py-1.5 bg-primary-600 text-white text-[10px] font-medium rounded-lg disabled:opacity-40"
                >
                  Отправить
                </button>
              </div>
            )}

            {/* Replies */}
            {childrenOf(comment.id).length > 0 && (
              <div className="mt-2 ml-4 border-l-2 border-gray-100 dark:border-dark-700 pl-3 space-y-2">
                {childrenOf(comment.id).map((reply: Comment) => (
                  <div key={reply.id}>
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-[10px] font-medium text-gray-600 dark:text-gray-400">
                        {reply.author_id.slice(0, 8)}
                      </span>
                      <span className="text-[10px] text-gray-400">
                        {new Date(reply.created_at).toLocaleString('ru-RU')}
                      </span>
                    </div>
                    <p className="text-xs text-gray-700 dark:text-gray-300">{reply.content}</p>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        ))}
      </div>

      {!isLoading && comments.length === 0 && (
        <p className="text-xs text-gray-400 dark:text-gray-500 text-center py-4">
          Нет комментариев
        </p>
      )}
    </div>
  )
}
