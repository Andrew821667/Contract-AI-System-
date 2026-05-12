'use client'

import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api, { Counterparty } from '@/services/api'

interface Props {
  value?: Counterparty | null
  onChange: (cp: Counterparty | null) => void
  placeholder?: string
  organizationScoped?: boolean
  disabled?: boolean
  allowCreateByInn?: boolean
}

export default function CounterpartyAutocomplete({
  value,
  onChange,
  placeholder = 'Поиск по названию или ИНН',
  disabled,
  allowCreateByInn = true,
}: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [creatingByInn, setCreatingByInn] = useState(false)
  const containerRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const trimmed = query.trim()
  const debouncedQuery = useDebounced(trimmed, 250)

  const { data, isLoading } = useQuery({
    queryKey: ['counterparties-search', debouncedQuery],
    queryFn: () =>
      api.listCounterparties({
        page: 1,
        page_size: 10,
        search: debouncedQuery || undefined,
        status: 'active',
      }),
    enabled: open,
    staleTime: 15_000,
  })

  const items = data?.counterparties ?? []
  const looksLikeInn = /^\d{10}(\d{2})?$/.test(trimmed)
  const showCreateByInn =
    allowCreateByInn && looksLikeInn && !items.some((c) => c.inn === trimmed)

  async function handleCreateByInn() {
    if (!looksLikeInn) return
    setCreatingByInn(true)
    try {
      const res = await api.lookupCounterparty({ inn: trimmed, save: true, check_bankruptcy: true })
      if (res.counterparty) {
        onChange(res.counterparty)
        setOpen(false)
        setQuery('')
      }
    } finally {
      setCreatingByInn(false)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      {value ? (
        <div className="flex items-center justify-between px-3 py-2 border-2 border-gray-200 rounded-lg bg-gray-50">
          <div className="min-w-0">
            <p className="font-medium truncate">{value.name}</p>
            {value.inn && (
              <p className="text-xs font-mono text-gray-500">ИНН {value.inn}</p>
            )}
          </div>
          {!disabled && (
            <button
              type="button"
              onClick={() => onChange(null)}
              className="text-gray-400 hover:text-gray-700 ml-2 text-sm"
            >
              ✕
            </button>
          )}
        </div>
      ) : (
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => setOpen(true)}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full px-3 py-2 border-2 border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
        />
      )}

      {!value && open && (
        <div className="absolute z-30 left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-lg max-h-72 overflow-auto">
          {isLoading && <div className="px-3 py-2 text-sm text-gray-500">Поиск…</div>}
          {!isLoading && items.length === 0 && (
            <div className="px-3 py-2 text-sm text-gray-500">Ничего не найдено</div>
          )}
          {items.map((cp) => (
            <button
              key={cp.id}
              type="button"
              onClick={() => {
                onChange(cp)
                setOpen(false)
                setQuery('')
              }}
              className="w-full text-left px-3 py-2 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
            >
              <p className="font-medium truncate">{cp.name}</p>
              <p className="text-xs text-gray-500">
                {cp.inn ? `ИНН ${cp.inn}` : '—'}
                {cp.short_name ? ` · ${cp.short_name}` : ''}
              </p>
            </button>
          ))}

          {showCreateByInn && (
            <button
              type="button"
              onClick={handleCreateByInn}
              disabled={creatingByInn}
              className="w-full text-left px-3 py-2 bg-primary-50 hover:bg-primary-100 border-t border-primary-100"
            >
              <p className="font-medium text-primary-700">
                {creatingByInn ? 'Запрашиваем ЕГРЮЛ…' : `Создать по ИНН ${trimmed}`}
              </p>
              <p className="text-xs text-primary-600">
                Контрагент будет создан с данными из ФНС.
              </p>
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return debounced
}
