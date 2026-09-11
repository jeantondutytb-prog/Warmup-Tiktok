import type { Rect, CellRect } from './types'

export interface LayoutInput {
  /** Comptes de la page courante, dans l'ordre d'affichage. */
  ids: string[]
  /** Compte focalise, ou null. Ignore s'il n'est pas dans `ids`. */
  focusedId: string | null
  /** Zone disponible pour les cellules, en-tete d'application deja deduit. */
  viewport: Rect
  /** Espacement entre cellules, en pixels. */
  gap: number
  /** Bandeau dessine par le chassis au-dessus de chaque vue. */
  cellHeaderHeight: number
  /**
   * Ratio largeur/hauteur (largeur divisee par hauteur) impose a chaque vue.
   * Omis ou `null` : comportement par defaut, la vue remplit sa zone (letterbox).
   * Sinon, chaque vue devient le plus grand rectangle de ce ratio qui tient
   * dans la zone qu'elle aurait occupee, centre horizontalement et verticalement.
   */
  aspectRatio?: number | null
}

export function columnsFor (count: number): number {
  if (count <= 1) return 1
  if (count <= 4) return 2
  return 3
}

/**
 * Les rectangles renvoyes sont ceux des *vues*, pas des cellules : le bandeau
 * d'en-tete est deja retranche du haut. Le chassis dessine ce bandeau dans
 * l'espace ainsi libere.
 */
function clamp (n: number): number {
  return Math.max(0, n)
}

export function computeLayout (input: LayoutInput): CellRect[] {
  const { ids, viewport, gap, cellHeaderHeight, aspectRatio } = input

  const seen = new Set<string>()
  for (const id of ids) {
    if (seen.has(id)) {
      throw new Error(`ids en double: ${id}`)
    }
    seen.add(id)
  }

  if (ids.length === 0) return []

  const focusedId = ids.includes(input.focusedId ?? '') ? input.focusedId : null

  const cells = (focusedId === null || ids.length === 1)
    ? uniformGrid(ids, viewport, gap, cellHeaderHeight, aspectRatio ?? undefined)
    : focusedGrid(ids, focusedId, viewport, gap, cellHeaderHeight)

  return (aspectRatio === null || aspectRatio === undefined)
    ? cells
    : cells.map(cell => fitAspect(cell, aspectRatio))
}

/**
 * Reduit `cell` au plus grand rectangle de ratio `ratio` (largeur/hauteur)
 * qui tient dans sa zone actuelle, centre sur cette zone.
 *
 * Arrondis : les *dimensions* calculees (celle qui n'est pas directement
 * recopiee depuis la zone) utilisent Math.floor, pour garantir qu'elles ne
 * depassent jamais la zone disponible meme si l'entree n'est pas entiere -
 * une marge de manoeuvre pour depasser d'une fraction de pixel serait le
 * genre de decalage silencieux qui produit un seam visible entre le cadre
 * CSS et la vue native. Les *decalages* de centrage utilisent Math.round,
 * pour repartir la marge restante aussi egalement que possible de part et
 * d'autre (comme railWidth plus haut) ; comme la marge est toujours >= 0,
 * round(marge / 2) reste toujours <= marge, donc ce choix ne peut jamais
 * faire deborder le rectangle de sa zone.
 */
function fitAspect (cell: CellRect, ratio: number): CellRect {
  const { width: w, height: h } = cell

  let width: number
  let height: number
  if (h * ratio <= w) {
    height = h
    width = Math.floor(h * ratio)
  } else {
    width = w
    height = Math.floor(w / ratio)
  }

  const offsetX = Math.round((w - width) / 2)
  const offsetY = Math.round((h - height) / 2)

  return {
    ...cell,
    x: cell.x + offsetX,
    y: cell.y + offsetY,
    width,
    height
  }
}

function uniformGrid (
  ids: string[], viewport: Rect, gap: number, headerHeight: number, aspectRatio?: number
): CellRect[] {
  const cols = aspectRatio === undefined
    ? columnsFor(ids.length)
    : bestColumnsForAspect(ids.length, viewport, gap, headerHeight, aspectRatio)
  const rows = Math.ceil(ids.length / cols)
  const cellWidth = Math.floor((viewport.width - gap * (cols - 1)) / cols)
  const cellHeight = Math.floor((viewport.height - gap * (rows - 1)) / rows)

  return ids.map((id, index) => {
    const col = index % cols
    const row = Math.floor(index / cols)
    return {
      id,
      x: viewport.x + col * (cellWidth + gap),
      y: viewport.y + row * (cellHeight + gap) + headerHeight,
      width: clamp(cellWidth),
      height: clamp(cellHeight - headerHeight)
    }
  })
}

/**
 * Choisit, parmi 1..count colonnes, le nombre de colonnes qui maximise
 * l'aire de la plus grande vue de ratio `ratio` tenant dans chaque case de
 * la grille resultante (apres deduction des gaps puis du bandeau d'en-tete).
 * En cas d'egalite d'aire, privilegie le nombre de lignes le plus petit :
 * les cellules restent cote a cote plutot que de s'empiler, ce qui est le
 * rendu recherche pour un "mur de telephones".
 */
function bestColumnsForAspect (
  count: number, viewport: Rect, gap: number, headerHeight: number, ratio: number
): number {
  let bestCols = 1
  let bestRows = Infinity
  let bestArea = -1

  for (let cols = 1; cols <= count; cols++) {
    const rows = Math.ceil(count / cols)
    const slotWidth = clamp(Math.floor((viewport.width - gap * (cols - 1)) / cols))
    const rawSlotHeight = Math.floor((viewport.height - gap * (rows - 1)) / rows)
    const viewHeight = clamp(rawSlotHeight - headerHeight)

    const area = fittedArea(slotWidth, viewHeight, ratio)

    if (area > bestArea || (area === bestArea && rows < bestRows)) {
      bestArea = area
      bestCols = cols
      bestRows = rows
    }
  }

  return bestCols
}

/** Aire du plus grand rectangle de ratio `ratio` (largeur/hauteur) tenant dans w x h. */
function fittedArea (w: number, h: number, ratio: number): number {
  if (h * ratio <= w) {
    return h * Math.floor(h * ratio)
  }
  return w * Math.floor(w / ratio)
}

function focusedGrid (
  ids: string[], focusedId: string, viewport: Rect, gap: number, headerHeight: number
): CellRect[] {
  const railWidth = Math.round(viewport.width / 3)
  const mainWidth = viewport.width - railWidth - gap
  const others = ids.filter(id => id !== focusedId)
  const railCellHeight = Math.floor((viewport.height - gap * (others.length - 1)) / others.length)

  const focused: CellRect = {
    id: focusedId,
    x: viewport.x,
    y: viewport.y + headerHeight,
    width: clamp(mainWidth),
    height: clamp(viewport.height - headerHeight)
  }

  const rail: CellRect[] = others.map((id, index) => ({
    id,
    x: viewport.x + mainWidth + gap,
    y: viewport.y + index * (railCellHeight + gap) + headerHeight,
    width: clamp(railWidth),
    height: clamp(railCellHeight - headerHeight)
  }))

  // L'ordre suit `ids` pour que le chassis et les vues restent alignes.
  return ids.map(id => (id === focusedId ? focused : rail.find(c => c.id === id)!))
}
