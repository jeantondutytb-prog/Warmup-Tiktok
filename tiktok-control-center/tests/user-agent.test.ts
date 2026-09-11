import { describe, it, expect } from 'vitest'
import { stripElectronTokens, toMobileUserAgent } from '../src/core/user-agent'

const ELECTRON_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) tiktok-control-center/0.1.0 Chrome/142.0.0.0 ' +
  'Electron/43.3.0 Safari/537.36'

describe('stripElectronTokens', () => {
  it('retire le jeton Electron et le jeton de l application', () => {
    expect(stripElectronTokens(ELECTRON_UA, 'tiktok-control-center')).toBe(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
      '(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
    )
  })

  it('conserve la version de Chrome intacte', () => {
    expect(stripElectronTokens(ELECTRON_UA, 'tiktok-control-center')).toContain('Chrome/142.0.0.0')
  })

  it('ne laisse aucune trace du mot Electron', () => {
    expect(stripElectronTokens(ELECTRON_UA, 'tiktok-control-center')).not.toContain('Electron')
  })

  it('laisse intact un user-agent Chrome deja propre', () => {
    const clean = 'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36'
    expect(stripElectronTokens(clean, 'tiktok-control-center')).toBe(clean)
  })

  it('echappe les caracteres speciaux du nom d application', () => {
    const ua = 'Mozilla/5.0 my.app+v2/1.0 Chrome/142.0.0.0 Safari/537.36'
    expect(stripElectronTokens(ua, 'my.app+v2')).toBe(
      'Mozilla/5.0 Chrome/142.0.0.0 Safari/537.36'
    )
  })

  it('ne laisse pas de double espace', () => {
    expect(stripElectronTokens(ELECTRON_UA, 'tiktok-control-center')).not.toContain('  ')
  })

  it('gere un user-agent Electron sans jeton de nom d application (observe sur cette machine)', () => {
    const ua =
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
      '(KHTML, like Gecko) Chrome/150.0.7871.212 Electron/43.3.0 Safari/537.36'
    expect(stripElectronTokens(ua, 'tiktok-control-center')).toBe(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
      '(KHTML, like Gecko) Chrome/150.0.7871.212 Safari/537.36'
    )
  })
})

describe('toMobileUserAgent', () => {
  const REAL_DESKTOP_UA =
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
    '(KHTML, like Gecko) Chrome/150.0.7871.212 Safari/537.36'

  it('produit le user-agent Android Chrome attendu, avec la version reelle', () => {
    expect(toMobileUserAgent(REAL_DESKTOP_UA)).toBe(
      'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) ' +
      'Chrome/150.0.7871.212 Mobile Safari/537.36'
    )
  })

  it('reprend une autre version de Chrome telle quelle', () => {
    const ua =
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
      '(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
    expect(toMobileUserAgent(ua)).toContain('Chrome/142.0.0.0')
    expect(toMobileUserAgent(ua)).not.toContain('150.0.7871.212')
  })

  it('retombe sur une version par defaut sensee si aucun jeton Chrome n est present', () => {
    const ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36'
    const result = toMobileUserAgent(ua)
    expect(result).not.toContain('undefined')
    expect(result).toMatch(/Chrome\/\d+\.\d+\.\d+\.\d+/)
  })

  it('contient Mobile et ne contient ni Macintosh, ni Electron, ni la plateforme de bureau', () => {
    const result = toMobileUserAgent(REAL_DESKTOP_UA)
    expect(result).toContain('Mobile')
    expect(result).not.toContain('Macintosh')
    expect(result).not.toContain('Electron')
    expect(result).not.toContain('Intel Mac OS X')
  })
})
