export const CONTENT_REFINE_DRAFT_KEY = 'iccp:content-refine-draft'

export const saveRefineDraft = (draft) => {
  localStorage.setItem(CONTENT_REFINE_DRAFT_KEY, JSON.stringify(draft))
}

export const loadRefineDraft = () => {
  const raw = localStorage.getItem(CONTENT_REFINE_DRAFT_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export const getDraftTarget = (draft) => draft?.workspace || 'content'

export const clearRefineDraft = () => {
  localStorage.removeItem(CONTENT_REFINE_DRAFT_KEY)
}
