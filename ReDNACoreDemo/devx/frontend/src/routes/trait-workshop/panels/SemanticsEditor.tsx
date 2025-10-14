import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Editor from '@monaco-editor/react'
import Ajv, { ErrorObject } from 'ajv'
import addFormats from 'ajv-formats'

import semanticsApi, {
  ApplyResponse,
  ProposeResponse,
  SemanticsStoreUnavailableError,
  ValidateResponse,
} from '@/lib/semanticsApi'

const DEFAULT_SCAFFOLD = {
  definition: 'Add a crisp, user-facing definition for this trait.',
  scope_notes: '',
  inclusion_criteria: [],
  exclusion_criteria: [],
  operationalization: {
    description: '',
    temporal: {
      kind: 'trait',
      aggregation: '',
      window: '',
    },
    context_model: {
      required_fields: [],
    },
  },
  examples: [],
  counterexamples: [],
  version: '1.0.0',
  last_reviewed: '',
  reviewers: [],
}

interface SemanticsEditorProps {
  traitPath: string
  initialSemantics?: Record<string, any> | null
  onApplied?: () => Promise<void> | void
}

type ValidatorFn = ((data: unknown) => boolean) & { errors?: ErrorObject[] | null }

export default function SemanticsEditor({ traitPath, initialSemantics, onApplied }: SemanticsEditorProps) {
  const [schema, setSchema] = useState<Record<string, any> | null>(null)
  const [editorValue, setEditorValue] = useState<string>('')
  const [draftObject, setDraftObject] = useState<Record<string, any> | null>(null)
  const [parseError, setParseError] = useState<string | null>(null)
  const [schemaErrors, setSchemaErrors] = useState<string[]>([])
  const [proposalErrors, setProposalErrors] = useState<string[]>([])
  const [apiError, setApiError] = useState<string | null>(null)
  const [crId, setCrId] = useState<string | null>(null)
  const [notes, setNotes] = useState<string>('')
  const [validationResult, setValidationResult] = useState<ValidateResponse | null>(null)
  const [applyResult, setApplyResult] = useState<ApplyResponse | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [storeUnavailable, setStoreUnavailable] = useState<boolean>(false)
  const [scaffoldUsed, setScaffoldUsed] = useState<boolean>(false)
  const [hasStoredSemantics, setHasStoredSemantics] = useState<boolean>(false)
  const [proposing, setProposing] = useState<boolean>(false)
  const [validating, setValidating] = useState<boolean>(false)
  const [applying, setApplying] = useState<boolean>(false)
  const [seedLoading, setSeedLoading] = useState<boolean>(false)
  const [seedMessage, setSeedMessage] = useState<string | null>(null)
  const errorsRef = useRef<HTMLDivElement | null>(null)

  const validator = useMemo<ValidatorFn | null>(() => {
    if (!schema) return null
    const ajv = new Ajv({ allErrors: true, strict: false })
    addFormats(ajv)
    return ajv.compile(schema)
  }, [schema])

  const runSchemaValidation = useCallback(
    (draft: Record<string, any> | null) => {
      if (!draft || !validator) {
        setSchemaErrors([])
        return
      }
      const valid = validator(draft)
      if (!valid && validator.errors) {
        const errors = validator.errors.map(err => {
          const path = err.instancePath || '/'
          return `${path}: ${err.message}`
        })
        setSchemaErrors(errors)
      } else {
        setSchemaErrors([])
      }
    },
    [validator],
  )

  const loadSemantics = useCallback(async () => {
    setLoading(true)
    setApiError(null)
    setStoreUnavailable(false)
    setProposalErrors([])
    setValidationResult(null)
    setApplyResult(null)
    setCrId(null)

    try {
      const response = await semanticsApi.getSemantics(traitPath)
      const semantics = response.semantics ?? initialSemantics ?? null
      const payload = semantics ?? DEFAULT_SCAFFOLD
      setScaffoldUsed(!semantics)
      setHasStoredSemantics(Boolean(semantics))
      const serialized = JSON.stringify(payload, null, 2)
      setEditorValue(serialized)
      setDraftObject(payload)
      runSchemaValidation(payload)
    } catch (err) {
      if (err instanceof SemanticsStoreUnavailableError) {
        setStoreUnavailable(true)
      } else {
        setApiError(err instanceof Error ? err.message : 'Failed to load trait semantics.')
      }
    } finally {
      setLoading(false)
    }
  }, [initialSemantics, runSchemaValidation, traitPath])

  useEffect(() => {
    let cancelled = false
    const loadSchema = async () => {
      try {
        const schemaDoc = await semanticsApi.getSchema()
        if (!cancelled) {
          setSchema(schemaDoc)
        }
      } catch (err) {
        if (err instanceof SemanticsStoreUnavailableError) {
          setStoreUnavailable(true)
        } else {
          setApiError(err instanceof Error ? err.message : 'Failed to load semantics schema.')
        }
      }
    }
    loadSchema()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    loadSemantics()
    setNotes('')
    setSeedMessage(null)
  }, [traitPath, loadSemantics])

  useEffect(() => {
    runSchemaValidation(draftObject)
  }, [draftObject, runSchemaValidation])

  const handleEditorChange = (value: string | undefined) => {
    const text = value ?? ''
    setEditorValue(text)
    setParseError(null)
    setProposalErrors([])
    setApiError(null)
    setValidationResult(null)
    setApplyResult(null)
    setCrId(null)

    try {
      const parsed = JSON.parse(text)
      setDraftObject(parsed)
    } catch (err) {
      setDraftObject(null)
      setParseError(err instanceof Error ? err.message : 'Invalid JSON')
    }
  }

  const handlePropose = async () => {
    if (parseError) {
      setApiError('Resolve JSON parse errors before proposing a change.')
      return
    }
    if (!draftObject) {
      setApiError('No semantics draft available to propose.')
      return
    }
    if (schemaErrors.length > 0) {
      setApiError('Fix schema validation errors before proposing.')
      return
    }

    setProposing(true)
    setApiError(null)
    setProposalErrors([])
    setValidationResult(null)
    setApplyResult(null)
    try {
      const response: ProposeResponse = await semanticsApi.proposeChange(traitPath, draftObject, notes || undefined)
      if (!response.accepted) {
        setProposalErrors(response.errors ?? ['Change request rejected.'])
        setCrId(null)
      } else {
        setCrId(response.cr_id ?? null)
      }
    } catch (err) {
      if (err instanceof SemanticsStoreUnavailableError) {
        setStoreUnavailable(true)
      } else {
        setApiError(err instanceof Error ? err.message : 'Failed to propose change.')
      }
    } finally {
      setProposing(false)
    }
  }

  const handleValidate = async () => {
    if (!crId) return
    setValidating(true)
    setApiError(null)
    try {
      const result: ValidateResponse = await semanticsApi.validateCR(crId)
      setValidationResult(result)
    } catch (err) {
      if (err instanceof SemanticsStoreUnavailableError) {
        setStoreUnavailable(true)
      } else {
        setApiError(err instanceof Error ? err.message : 'Failed to validate change request.')
      }
    } finally {
      setValidating(false)
    }
  }

  const handleApply = async () => {
    if (!crId) return
    setApplying(true)
    setApiError(null)
    setApplyResult(null)
    try {
      const result: ApplyResponse = await semanticsApi.applyCR(crId)
      setApplyResult(result)
      if (result.applied) {
        await loadSemantics()
        if (onApplied) {
          await onApplied()
        }
      }
    } catch (err) {
      if (err instanceof SemanticsStoreUnavailableError) {
      setStoreUnavailable(true)
    } else {
      setApiError(err instanceof Error ? err.message : 'Failed to apply change.')
    }
  } finally {
    setApplying(false)
  }
}

  const handleSeed = async () => {
    setSeedLoading(true)
    setApiError(null)
    try {
      const response = await semanticsApi.seed(traitPath)
      setSeedMessage(`Seeded semantics (${response.status}).`)
      await loadSemantics()
      if (onApplied) {
        await onApplied()
      }
    } catch (err) {
      if (err instanceof SemanticsStoreUnavailableError) {
        setStoreUnavailable(true)
      } else {
        setApiError(err instanceof Error ? err.message : 'Failed to seed semantics.')
      }
    } finally {
      setSeedLoading(false)
    }
  }

  if (storeUnavailable) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-md p-4">
        <h4 className="text-sm font-semibold text-yellow-800 mb-1">Semantics store unavailable</h4>
        <p className="text-sm text-yellow-700">
          Trait semantics storage is offline. You can view existing definitions once the backend store is restored.
        </p>
      </div>
    )
  }

  if (loading || !schema) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-sm text-gray-500">Loading trait semantics editor...</div>
      </div>
    )
  }

  const canPropose = !proposing && !validating && !applying && !parseError && schemaErrors.length === 0 && !!draftObject
  const canValidate = !!crId && !validating && !applying
  const canApply = !!crId && validationResult?.valid && !applying
  const hasSchema = Boolean(schema)
  const hasErrors = schemaErrors.length > 0

  let statusLabel = 'Editor Ready'
  let statusClass = 'bg-green-50 text-green-700 border border-green-200'
  let statusDescription = 'Schema loaded and editor is ready.'
  const showSeeErrors = hasSchema && hasErrors

  if (hasSchema && hasErrors) {
    statusLabel = 'Schema error'
    statusClass = 'bg-red-50 text-red-700 border border-red-200'
    statusDescription = 'Resolve validation errors to continue.'
  } else if (hasSchema && !hasErrors && hasStoredSemantics) {
    statusLabel = 'Store Loaded'
    statusClass = 'bg-green-50 text-green-700 border border-green-200'
    statusDescription = 'Semantics loaded from registry.'
  } else if (hasSchema && !hasErrors && !hasStoredSemantics) {
    statusLabel = 'Draft mode'
    statusClass = 'bg-blue-50 text-blue-700 border border-blue-200'
    statusDescription = 'No stored semantics found; using scaffold draft.'
  } else if (!hasSchema) {
    statusLabel = 'Editor Ready'
    statusClass = 'bg-green-50 text-green-700 border border-green-200'
    statusDescription = 'Waiting for schema to load.'
  }

  const handleScrollToErrors = () => {
    if (errorsRef.current) {
      errorsRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
      errorsRef.current.focus({ preventScroll: true })
    }
  }

  return (
    <div className="space-y-4">
      <div role="status" aria-live="polite" className="mb-2 flex flex-wrap items-center gap-2">
        <span className={`inline-flex items-center gap-2 rounded px-2 py-1 text-xs font-medium ${statusClass}`}>
          {statusLabel}
          {statusDescription && <span className="hidden text-[11px] font-normal sm:inline">{statusDescription}</span>}
        </span>
        {showSeeErrors && (
          <button
            type="button"
            onClick={handleScrollToErrors}
            className="text-xs font-medium text-red-600 hover:underline"
          >
            See errors
          </button>
        )}
      </div>

      {scaffoldUsed && (
        <div className="bg-blue-50 border border-blue-200 rounded-md p-3 text-sm text-blue-700 space-y-2">
          <p>
            No semantics exist for this trait yet. A scaffold has been prefilled to help you author the initial draft.
          </p>
          <button
            type="button"
            onClick={handleSeed}
            disabled={seedLoading}
            className="inline-flex items-center rounded-md bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:bg-blue-300"
          >
            {seedLoading ? 'Seeding…' : 'Seed Example Semantics'}
          </button>
          {seedMessage && <p className="text-xs text-blue-600">{seedMessage}</p>}
        </div>
      )}

      {apiError && (
        <div className="bg-red-50 border border-red-200 rounded-md p-3 text-sm text-red-700">{apiError}</div>
      )}

      <div className="grid grid-cols-12 gap-4">
        <div className="col-span-12 lg:col-span-8 space-y-3">
          <div className="border border-gray-200 rounded-md overflow-hidden">
            <Editor
              height="420px"
              language="json"
              theme="vs-dark"
              value={editorValue}
              onChange={handleEditorChange}
              options={{
                minimap: { enabled: false },
                wordWrap: 'on',
                scrollBeyondLastLine: false,
                automaticLayout: true,
              }}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Author notes</label>
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              rows={3}
              placeholder="Optional context for reviewers."
            />
          </div>
        </div>

        <div className="col-span-12 lg:col-span-4">
          <div className="h-full bg-gray-50 border border-gray-200 rounded-md p-4 space-y-4">
            <div>
              <h4 className="text-sm font-semibold text-gray-800">Live validation</h4>
              {parseError ? (
                <div className="mt-2 text-sm text-red-600">Parse error: {parseError}</div>
              ) : schemaErrors.length > 0 ? (
                <div ref={errorsRef} tabIndex={-1} className="mt-2 space-y-1 outline-none">
                  <ul>
                    {schemaErrors.map((error, index) => (
                      <li key={index} className="text-sm text-red-600">
                        • {error}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="mt-2 text-sm text-green-700">Draft passes JSON schema validation.</p>
              )}
              {proposalErrors.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {proposalErrors.map((error, index) => (
                    <li key={index} className="text-sm text-red-600">
                      • {error}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="space-y-2">
              <button
                type="button"
                onClick={handlePropose}
                disabled={!canPropose}
                className={`w-full inline-flex justify-center rounded-md border border-transparent px-4 py-2 text-sm font-medium text-white ${
                  canPropose ? 'bg-blue-600 hover:bg-blue-700' : 'bg-blue-300 cursor-not-allowed'
                }`}
              >
                {proposing ? 'Proposing…' : 'Propose Change'}
              </button>
              <button
                type="button"
                onClick={handleValidate}
                disabled={!canValidate}
                className={`w-full inline-flex justify-center rounded-md border border-transparent px-4 py-2 text-sm font-medium text-white ${
                  canValidate ? 'bg-gray-700 hover:bg-gray-800' : 'bg-gray-400 cursor-not-allowed'
                }`}
              >
                {validating ? 'Validating…' : 'Validate CR'}
              </button>
              <button
                type="button"
                onClick={handleApply}
                disabled={!canApply}
                className={`w-full inline-flex justify-center rounded-md border border-transparent px-4 py-2 text-sm font-medium text-white ${
                  canApply ? 'bg-green-600 hover:bg-green-700' : 'bg-green-300 cursor-not-allowed'
                }`}
              >
                {applying ? 'Applying…' : 'Apply (low-risk)'}
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <h4 className="text-sm font-semibold text-gray-800">Current CR</h4>
                {crId ? (
                  <p className="mt-1 text-xs font-mono text-gray-700 break-all">{crId}</p>
                ) : (
                  <p className="mt-1 text-sm text-gray-500">No change request proposed.</p>
                )}
              </div>
              <div>
                <h4 className="text-sm font-semibold text-gray-800">Validation result</h4>
                {validationResult ? (
                  validationResult.valid ? (
                    <p className="mt-1 text-sm text-green-700">CR passes backend validation.</p>
                  ) : (
                    <ul className="mt-1 space-y-1">
                      {validationResult.errors.map((error, index) => (
                        <li key={index} className="text-sm text-red-600">
                          • {error}
                        </li>
                      ))}
                    </ul>
                  )
                ) : (
                  <p className="mt-1 text-sm text-gray-500">Run validation after proposing a change.</p>
                )}
              </div>
              <div>
                <h4 className="text-sm font-semibold text-gray-800">Apply status</h4>
                {applyResult ? (
                  applyResult.applied ? (
                    <p className="mt-1 text-sm text-green-700">Change applied to semantics store.</p>
                  ) : applyResult.requires_approval ? (
                    <p className="mt-1 text-sm text-yellow-700">
                      Requires approval. Submit for review through governance.
                    </p>
                  ) : applyResult.errors && applyResult.errors.length > 0 ? (
                    <ul className="mt-1 space-y-1">
                      {applyResult.errors.map((error, index) => (
                        <li key={index} className="text-sm text-red-600">
                          • {error}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-sm text-gray-500">Unable to apply change.</p>
                  )
                ) : (
                  <p className="mt-1 text-sm text-gray-500">Apply is only available after validation succeeds.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
