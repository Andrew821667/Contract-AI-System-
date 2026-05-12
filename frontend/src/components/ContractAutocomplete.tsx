'use client'

import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '@/services/api'

interface ContractRef {
  id: string
  file_name: string
  contract_type?: string | null
  status?: string
  contract_number?: string | null
  contract_date?: string | null
}

interface Props {
  value?: ContractRef | null
  onChange: (c: ContractRef | null) => void
  placeholder?: string
  excludeContractId?: string
  onlyMain?: boolean
  disabled?: boolean
}

export default function ContractAutocomplete({
  value,
  onChange,
  placeholder = 'Поиск договора по названию',
  excludeContractId,
  onlyMain = true,
  disabled,
}: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
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
    queryKey: ['contracts-search', debouncedQuery, onlyMain],
    queryFn: () =>
      api.listContracts({
        page: 1,
        limit: 10,
        search: debouncedQuery || undefined,
      }),
    enabled: open,
    staleTime: 10_000,
  })

  const items = (data?.contracts ?? [])
    .filter((c: any) => !excludeContractId || c.id !== excludeContractId)
    .filter((c: any) => !onlyMain || c.document_type === undefined || c.document_type === 'contract')

  return (
    <div ref={containerRef} className="relative">
      {value ? (
        <div className="flex items-center justify-between px-3 py-2 border-2 border-gray-200 rounded-lg bg-gray-50">
          <div className="min-w-0">
            <p className="font-medium truncate">{value.file_name}</p>
            <p className="text-xs text-gray-500">
              {value.contract_number ? `№ ${value.contract_number}` : ''}
              {value.contract_date ? ` от ${new Date(value.contract_date).toLocaleDateString('ru-RU')}` : ''}
            </p>
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
          {items.map((c: any) => (
            <button
              key={c.id}
              type="button"
              onClick={() => {
                onChange({
                  id: c.id,
                  file_name: c.file_name,
                  contract_type: c.contract_type,
                  status: c.status,
                  contract_number: c.contract_number,
                  contract_date: c.contract_date,
                })
                setOpen(false)
                setQuery('')
              }}
              className="w-full text-left px-3 py-2 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
            >
              <p className="font-medium truncate">{c.file_name}</p>
              <p className="text-xs text-gray-500">
                {c.contract_type || '—'}
                {c.status ? ` · ${c.status}` : ''}
              </p>
            </button>
          ))}
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
