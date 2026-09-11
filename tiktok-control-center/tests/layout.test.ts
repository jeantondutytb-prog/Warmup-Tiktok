import { describe, it, expect } from 'vitest'
import { computeLayout, columnsFor } from '../src/core/layout'
import { PORTRAIT_ASPECT } from '../src/core/types'

const viewport = { x: 0, y: 0, width: 1200, height: 800 }
const base = { viewport, gap: 10, cellHeaderHeight: 30 }

describe('columnsFor', () => {
  it('utilise une colonne pour un seul compte', () => {
    expect(columnsFor(1)).toBe(1)
  })

  it('utilise deux colonnes jusqu a quatre comptes', () => {
    expect(columnsFor(2)).toBe(2)
    expect(columnsFor(4)).toBe(2)
  })

  it('utilise trois colonnes au dela de quatre comptes', () => {
    expect(columnsFor(5)).toBe(3)
    expect(columnsFor(6)).toBe(3)
  })
})

describe('computeLayout sans focus', () => {
  it('ne renvoie rien pour une page vide', () => {
    expect(computeLayout({ ...base, ids: [], focusedId: null })).toEqual([])
  })

  it('donne toute la zone a un compte unique, moins son en-tete', () => {
    const [cell] = computeLayout({ ...base, ids: ['a'], focusedId: null })
    expect(cell).toEqual({ id: 'a', x: 0, y: 30, width: 1200, height: 770 })
  })

  it('repartit quatre comptes en deux colonnes egales', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c', 'd'], focusedId: null })
    expect(cells).toHaveLength(4)
    // largeur = (1200 - 1 gap) / 2 = 595 ; hauteur = (800 - 1 gap) / 2 = 395
    expect(cells[0]).toEqual({ id: 'a', x: 0, y: 30, width: 595, height: 365 })
    expect(cells[1]).toEqual({ id: 'b', x: 605, y: 30, width: 595, height: 365 })
    expect(cells[2]).toEqual({ id: 'c', x: 0, y: 435, width: 595, height: 365 })
    expect(cells[3]).toEqual({ id: 'd', x: 605, y: 435, width: 595, height: 365 })
  })

  it('ne laisse aucune cellule deborder de la zone', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c', 'd', 'e', 'f'], focusedId: null })
    for (const cell of cells) {
      expect(cell.x).toBeGreaterThanOrEqual(viewport.x)
      expect(cell.y).toBeGreaterThanOrEqual(viewport.y)
      expect(cell.x + cell.width).toBeLessThanOrEqual(viewport.x + viewport.width)
      expect(cell.y + cell.height).toBeLessThanOrEqual(viewport.y + viewport.height)
    }
  })
})

describe('computeLayout avec focus', () => {
  it('donne les deux tiers gauche a la cellule focalisee', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c'], focusedId: 'a' })
    const focused = cells.find(c => c.id === 'a')!
    expect(focused.x).toBe(0)
    expect(focused.y).toBe(30)
    expect(focused.width).toBe(790) // round(1200 * 2/3) - gap = 800 - 10
    expect(focused.height).toBe(770)
  })

  it('empile les cellules non focalisees dans la colonne de droite', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c'], focusedId: 'a' })
    const others = cells.filter(c => c.id !== 'a')
    expect(others).toHaveLength(2)
    for (const cell of others) {
      expect(cell.x).toBe(800)
      expect(cell.width).toBe(400)
    }
    expect(others[0].y).toBe(30)   // 0 + en-tete
    expect(others[1].y).toBe(435)  // 395 + gap + en-tete
  })

  it('se comporte comme sans focus si l id focalise est absent de la page', () => {
    const withGhost = computeLayout({ ...base, ids: ['a', 'b'], focusedId: 'zzz' })
    const without = computeLayout({ ...base, ids: ['a', 'b'], focusedId: null })
    expect(withGhost).toEqual(without)
  })

  it('donne toute la zone a une cellule focalisee seule sur sa page', () => {
    const cells = computeLayout({ ...base, ids: ['a'], focusedId: 'a' })
    expect(cells[0]).toEqual({ id: 'a', x: 0, y: 30, width: 1200, height: 770 })
  })
})

describe('computeLayout - tailles degenerees', () => {
  it('ne renvoie jamais une hauteur negative sans focus (en-tete plus grand que la zone)', () => {
    const cells = computeLayout({
      ...base,
      viewport: { x: 0, y: 0, width: 1200, height: 20 },
      ids: ['a'],
      focusedId: null
    })
    expect(cells[0].height).toBe(0)
    expect(cells[0].width).toBeGreaterThanOrEqual(0)
  })

  it('ne renvoie jamais une largeur negative sans focus (zone plus etroite que les gaps)', () => {
    const cells = computeLayout({
      ...base,
      viewport: { x: 0, y: 0, width: 5, height: 800 },
      ids: ['a', 'b'],
      focusedId: null
    })
    expect(cells[0].width).toBe(0)
    expect(cells[1].width).toBe(0)
    expect(cells[0].height).toBeGreaterThanOrEqual(0)
    expect(cells[1].height).toBeGreaterThanOrEqual(0)
  })

  it('ne renvoie jamais une hauteur negative avec focus (en-tete plus grand que la zone)', () => {
    const cells = computeLayout({
      ...base,
      viewport: { x: 0, y: 0, width: 1200, height: 20 },
      ids: ['a', 'b', 'c'],
      focusedId: 'a'
    })
    const focused = cells.find(c => c.id === 'a')!
    const others = cells.filter(c => c.id !== 'a')
    expect(focused.height).toBe(0)
    for (const cell of others) {
      expect(cell.height).toBe(0)
    }
  })

  it('ne renvoie jamais une largeur negative avec focus (zone plus etroite que le rail)', () => {
    const cells = computeLayout({
      ...base,
      viewport: { x: 0, y: 0, width: 10, height: 800 },
      ids: ['a', 'b'],
      focusedId: 'a'
    })
    const focused = cells.find(c => c.id === 'a')!
    expect(focused.width).toBe(0)
  })
})

describe('computeLayout - ids en double', () => {
  it('leve une erreur si un id apparait deux fois', () => {
    expect(() => computeLayout({
      ...base,
      ids: ['a', 'a'],
      focusedId: null
    })).toThrowError('ids en double: a')
  })
})

describe('computeLayout - aspectRatio', () => {
  it('PORTRAIT_ASPECT vaut 9/16', () => {
    expect(PORTRAIT_ASPECT).toBeCloseTo(9 / 16)
  })

  it('omettre aspectRatio reproduit exactement le comportement actuel (undefined)', () => {
    const withUndefined = computeLayout({ ...base, ids: ['a', 'b', 'c', 'd'], focusedId: null, aspectRatio: undefined })
    const without = computeLayout({ ...base, ids: ['a', 'b', 'c', 'd'], focusedId: null })
    expect(withUndefined).toEqual(without)
    // Reproduit aussi les valeurs historiques verifiees plus haut.
    expect(withUndefined[0]).toEqual({ id: 'a', x: 0, y: 30, width: 595, height: 365 })
    expect(withUndefined[1]).toEqual({ id: 'b', x: 605, y: 30, width: 595, height: 365 })
    expect(withUndefined[2]).toEqual({ id: 'c', x: 0, y: 435, width: 595, height: 365 })
    expect(withUndefined[3]).toEqual({ id: 'd', x: 605, y: 435, width: 595, height: 365 })
  })

  it('aspectRatio: null reproduit aussi exactement le comportement actuel', () => {
    const withNull = computeLayout({ ...base, ids: ['a', 'b', 'c', 'd'], focusedId: null, aspectRatio: null })
    const without = computeLayout({ ...base, ids: ['a', 'b', 'c', 'd'], focusedId: null })
    expect(withNull).toEqual(without)
  })

  it('cellule large : la hauteur est le facteur limitant, centrage horizontal avec marges egales', () => {
    const cells = computeLayout({
      viewport: { x: 0, y: 0, width: 1000, height: 500 },
      gap: 0,
      cellHeaderHeight: 0,
      ids: ['a'],
      focusedId: null,
      aspectRatio: PORTRAIT_ASPECT
    })
    // h*r = 500 * 9/16 = 281.25 <= 1000 => la hauteur est le facteur limitant.
    // width = floor(281.25) = 281 ; marge totale = 1000 - 281 = 719 ; offset = round(719/2) = 360.
    expect(cells[0]).toEqual({ id: 'a', x: 360, y: 0, width: 281, height: 500 })
    const marginLeft = cells[0].x
    const marginRight = 1000 - (cells[0].x + cells[0].width)
    expect(Math.abs(marginLeft - marginRight)).toBeLessThanOrEqual(1)
  })

  it('cellule etroite et haute : la largeur est le facteur limitant, centrage vertical', () => {
    const cells = computeLayout({
      viewport: { x: 0, y: 0, width: 300, height: 1000 },
      gap: 0,
      cellHeaderHeight: 0,
      ids: ['a'],
      focusedId: null,
      aspectRatio: PORTRAIT_ASPECT
    })
    // h*r = 1000 * 9/16 = 562.5, pas <= 300 => la largeur est le facteur limitant.
    // height = floor(300 / (9/16)) = floor(533.33..) = 533 ; marge totale = 1000-533=467 ; offset = round(467/2) = 234 (233.5 arrondi a 234).
    expect(cells[0]).toEqual({ id: 'a', x: 0, y: 234, width: 300, height: 533 })
    const marginTop = cells[0].y
    const marginBottom = 1000 - (cells[0].y + cells[0].height)
    expect(Math.abs(marginTop - marginBottom)).toBeLessThanOrEqual(1)
  })

  it('layout focalise : la cellule principale et le rail sont ajustes et centres independamment', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c'], focusedId: 'a', aspectRatio: PORTRAIT_ASPECT })
    const focused = cells.find(c => c.id === 'a')!
    const others = cells.filter(c => c.id !== 'a')

    // Zone vue de la cellule principale (avant aspect) : x=0,y=30,width=790,height=770.
    // h*r = 770*9/16 = 433.125 <= 790 => hauteur limitante.
    // width = floor(433.125) = 433 ; marge = 790-433=357 ; offset = round(357/2) = round(178.5) = 179.
    expect(focused).toEqual({ id: 'a', x: 179, y: 30, width: 433, height: 770 })

    // Zone vue de chaque cellule du rail (avant aspect) : x=800,width=400,height=365.
    // h*r = 365*9/16 = 205.3125 <= 400 => hauteur limitante.
    // width = floor(205.3125) = 205 ; marge = 400-205=195 ; offset = round(195/2) = round(97.5) = 98.
    expect(others).toHaveLength(2)
    for (const cell of others) {
      expect(cell.width).toBe(205)
      expect(cell.height).toBe(365)
      expect(cell.x).toBe(898) // 800 + 98
    }
    expect(others[0].y).toBe(30)
    expect(others[1].y).toBe(435)
  })

  it('une zone degeneree (hauteur nulle apres en-tete) reste a largeur/hauteur non negatives', () => {
    const cells = computeLayout({
      ...base,
      viewport: { x: 0, y: 0, width: 1200, height: 20 },
      ids: ['a'],
      focusedId: null,
      aspectRatio: PORTRAIT_ASPECT
    })
    expect(cells[0].width).toBeGreaterThanOrEqual(0)
    expect(cells[0].height).toBeGreaterThanOrEqual(0)
    expect(cells[0]).toEqual({ id: 'a', x: 600, y: 30, width: 0, height: 0 })
  })

  it('une zone tres etroite (largeur 5) empile desormais sur 1 colonne car c est plus grand que 2 colonnes ecrasees a 0', () => {
    const cells = computeLayout({
      ...base,
      viewport: { x: 0, y: 0, width: 5, height: 800 },
      ids: ['a', 'b'],
      focusedId: null,
      aspectRatio: PORTRAIT_ASPECT
    })
    // cols=2 ecraserait chaque slot a largeur 0 (aire 0). cols=1 (empile, 2 lignes)
    // donne un slot 5x365 par cellule (aire 40 apres ajustement) : le choix qui
    // maximise l aire retient donc cols=1, evitant l ecrasement a zero.
    // width=5 (largeur limitante), height=floor(5/(9/16))=floor(8.888)=8.
    for (const cell of cells) {
      expect(cell.width).toBeGreaterThanOrEqual(0)
      expect(cell.height).toBeGreaterThanOrEqual(0)
    }
    expect(cells[0]).toEqual({ id: 'a', x: 0, y: 209, width: 5, height: 8 })
    expect(cells[1]).toEqual({ id: 'b', x: 0, y: 614, width: 5, height: 8 })
  })

  it('les rectangles ajustes ne debordent jamais de la zone qui leur a ete allouee', () => {
    const ratios = [PORTRAIT_ASPECT, 16 / 9, 1]
    const scenarios = [
      { viewport: { x: 0, y: 0, width: 1200, height: 800 }, gap: 10, cellHeaderHeight: 30, ids: ['a', 'b', 'c', 'd', 'e'], focusedId: null as string | null },
      { viewport: { x: 40, y: 20, width: 1400, height: 900 }, gap: 12, cellHeaderHeight: 28, ids: ['a', 'b', 'c'], focusedId: 'b' },
      { viewport: { x: 0, y: 0, width: 37, height: 53 }, gap: 3, cellHeaderHeight: 30, ids: ['a', 'b'], focusedId: null }
    ]

    for (const scenario of scenarios) {
      for (const ratio of ratios) {
        const fitted = computeLayout({ ...scenario, aspectRatio: ratio })
        for (const cell of fitted) {
          expect(cell.x).toBeGreaterThanOrEqual(scenario.viewport.x)
          expect(cell.y).toBeGreaterThanOrEqual(scenario.viewport.y)
          expect(cell.x + cell.width).toBeLessThanOrEqual(scenario.viewport.x + scenario.viewport.width)
          expect(cell.y + cell.height).toBeLessThanOrEqual(scenario.viewport.y + scenario.viewport.height)
        }
      }
    }
  })

  it('trois comptes dans un viewport large se rangent maintenant sur 3 colonnes (pas 2)', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c'], focusedId: null, aspectRatio: PORTRAIT_ASPECT })
    // columnsFor(3) donnerait 2 colonnes / 2 lignes (2 abscisses, 2 ordonnees).
    // Le choix qui maximise l aire doit retenir 3 colonnes / 1 ligne.
    const xs = new Set(cells.map(c => c.x))
    const ys = new Set(cells.map(c => c.y))
    expect(xs.size).toBe(3)
    expect(ys.size).toBe(1)
  })

  it('la cellule choisie est plus grande que ce que l ancien choix columnsFor aurait produit', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c'], focusedId: null, aspectRatio: PORTRAIT_ASPECT })
    // Ancien choix : columnsFor(3) = 2 colonnes / 2 lignes -> slot 595x395, vue 595x365 ;
    // 365 * 9/16 = 205.3125 <= 595 => hauteur limitante -> cellule 205x365 (aire 74825).
    const oldArea = 205 * 365
    for (const cell of cells) {
      expect(cell.width * cell.height).toBeGreaterThan(oldArea)
    }
  })

  it('en cas d egalite d aire, le choix privilegie moins de lignes (cote a cote)', () => {
    const cells = computeLayout({
      ids: ['a', 'b', 'c', 'd'],
      focusedId: null,
      viewport: { x: 0, y: 0, width: 430, height: 270 },
      gap: 10,
      cellHeaderHeight: 30,
      aspectRatio: 1
    })
    // cols=2 (2 lignes), cols=3 (2 lignes) et cols=4 (1 ligne) produisent tous
    // une cellule carree de 100x100 (meme aire) : le choix doit retenir
    // cols=4 (1 ligne), pas cols=2 ou 3 (2 lignes).
    const ys = new Set(cells.map(c => c.y))
    expect(ys.size).toBe(1)
    for (const cell of cells) {
      expect(cell.width).toBe(100)
      expect(cell.height).toBe(100)
    }
  })

  it('une cellule seule remplit toujours la zone de facon sensee', () => {
    const cells = computeLayout({ ...base, ids: ['a'], focusedId: null, aspectRatio: PORTRAIT_ASPECT })
    // Zone vue : 1200x770 (apres en-tete). h*ratio=770*9/16=433.125<=1200 => hauteur limitante.
    // width=floor(433.125)=433 ; marge=1200-433=767 ; offset=round(767/2)=384 (383.5 arrondi a 384).
    expect(cells[0]).toEqual({ id: 'a', x: 384, y: 30, width: 433, height: 770 })
  })

  it('les cellules ajustees ne se chevauchent jamais', () => {
    const ratios = [PORTRAIT_ASPECT, 16 / 9, 1]
    const scenarios = [
      { viewport: { x: 0, y: 0, width: 1400, height: 844 }, gap: 10, cellHeaderHeight: 30, ids: ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j'], focusedId: null as string | null },
      { viewport: { x: 0, y: 0, width: 1200, height: 800 }, gap: 10, cellHeaderHeight: 30, ids: ['a', 'b', 'c'], focusedId: null as string | null },
      { viewport: { x: 40, y: 20, width: 1400, height: 900 }, gap: 12, cellHeaderHeight: 28, ids: ['a', 'b', 'c'], focusedId: 'b' }
    ]

    const overlaps = (a: { x: number, y: number, width: number, height: number }, b: { x: number, y: number, width: number, height: number }): boolean =>
      a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height

    for (const scenario of scenarios) {
      for (const ratio of ratios) {
        const cells = computeLayout({ ...scenario, aspectRatio: ratio })
        for (let i = 0; i < cells.length; i++) {
          for (let j = i + 1; j < cells.length; j++) {
            expect(overlaps(cells[i], cells[j])).toBe(false)
          }
        }
      }
    }
  })

  it('une largeur de viewport nulle reste a largeur/hauteur non negatives (0), quel que soit le nombre de colonnes choisi', () => {
    const cells = computeLayout({
      ...base,
      viewport: { x: 0, y: 0, width: 0, height: 800 },
      ids: ['a', 'b'],
      focusedId: null,
      aspectRatio: PORTRAIT_ASPECT
    })
    for (const cell of cells) {
      expect(cell.width).toBeGreaterThanOrEqual(0)
      expect(cell.height).toBeGreaterThanOrEqual(0)
      expect(cell.width).toBe(0)
      expect(cell.height).toBe(0)
    }
  })
})
