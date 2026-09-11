import { describe, it, expect } from 'vitest'
import {
  isAllowedProtocol,
  isTikTokHost,
  isLoginProviderHost,
  isAllowedNavigationTarget,
  isAllowedPopupTarget
} from '../src/core/navigation-guard'

describe('isAllowedProtocol', () => {
  it('autorise http et https', () => {
    expect(isAllowedProtocol('https://www.tiktok.com/foo')).toBe(true)
    expect(isAllowedProtocol('http://www.tiktok.com/foo')).toBe(true)
  })

  it('bloque les schemas non web renvoyes vers l OS', () => {
    expect(isAllowedProtocol('itms-apps://apps.apple.com/app/id123')).toBe(false)
    expect(isAllowedProtocol('macappstore://apps.apple.com/app/id123')).toBe(false)
    expect(isAllowedProtocol('tiktok://open')).toBe(false)
    expect(isAllowedProtocol('mailto:someone@example.com')).toBe(false)
  })

  it('bloque un schema arbitraire non enumere (liste blanche, pas liste noire)', () => {
    expect(isAllowedProtocol('whatsapp://send?text=hi')).toBe(false)
    expect(isAllowedProtocol('intent://scan/#Intent;scheme=zxing;end')).toBe(false)
  })

  it('bloque une URL invalide plutot que de lever', () => {
    expect(isAllowedProtocol('not a url')).toBe(false)
  })
})

describe('isTikTokHost', () => {
  it('autorise le domaine racine et www', () => {
    expect(isTikTokHost('https://tiktok.com')).toBe(true)
    expect(isTikTokHost('https://www.tiktok.com/foo')).toBe(true)
  })

  it('autorise un sous-domaine quelconque', () => {
    expect(isTikTokHost('https://m.tiktok.com/@someone')).toBe(true)
    expect(isTikTokHost('https://us.tiktok.com/')).toBe(true)
  })

  it('bloque un domaine attaquant qui contient tiktok.com en sous-chaine', () => {
    expect(isTikTokHost('https://evil-tiktok.com.attacker.net')).toBe(false)
  })

  it('bloque un domaine sans rapport', () => {
    expect(isTikTokHost('https://example.com')).toBe(false)
  })

  it('bloque une URL invalide', () => {
    expect(isTikTokHost('not a url')).toBe(false)
  })
})

describe('isLoginProviderHost', () => {
  it('autorise Google, Apple et Facebook (connexion tierce)', () => {
    expect(isLoginProviderHost('https://accounts.google.com/o/oauth2/auth')).toBe(true)
    expect(isLoginProviderHost('https://appleid.apple.com/auth/authorize')).toBe(true)
    expect(isLoginProviderHost('https://www.facebook.com/dialog/oauth')).toBe(true)
    expect(isLoginProviderHost('https://m.facebook.com/dialog/oauth')).toBe(true)
  })

  it('bloque un domaine qui imite un fournisseur de connexion', () => {
    expect(isLoginProviderHost('https://accounts.google.com.attacker.net')).toBe(false)
    expect(isLoginProviderHost('https://evil-facebook.com')).toBe(false)
  })

  it('bloque un domaine sans rapport', () => {
    expect(isLoginProviderHost('https://example.com')).toBe(false)
  })
})

describe('isAllowedNavigationTarget (garde will-navigate)', () => {
  it('autorise TikTok et ses sous-domaines en http/https', () => {
    expect(isAllowedNavigationTarget('https://www.tiktok.com/foo')).toBe(true)
    expect(isAllowedNavigationTarget('https://tiktok.com')).toBe(true)
    expect(isAllowedNavigationTarget('https://m.tiktok.com/@someone')).toBe(true)
  })

  it('autorise les fournisseurs de connexion tierce', () => {
    expect(isAllowedNavigationTarget('https://accounts.google.com/o/oauth2/auth')).toBe(true)
    expect(isAllowedNavigationTarget('https://appleid.apple.com/auth/authorize')).toBe(true)
    expect(isAllowedNavigationTarget('https://www.facebook.com/dialog/oauth')).toBe(true)
  })

  it('bloque un schema non web meme vers un hote qui ressemble a tiktok', () => {
    expect(isAllowedNavigationTarget('itms-apps://apps.apple.com/app/id123')).toBe(false)
    expect(isAllowedNavigationTarget('tiktok://open')).toBe(false)
  })

  it('bloque un domaine attaquant construit par suffixe', () => {
    expect(isAllowedNavigationTarget('https://evil-tiktok.com.attacker.net')).toBe(false)
  })

  it('bloque un domaine sans rapport', () => {
    expect(isAllowedNavigationTarget('https://example.com')).toBe(false)
  })
})

describe('isAllowedPopupTarget (garde setWindowOpenHandler)', () => {
  it('autorise uniquement les fournisseurs de connexion tierce', () => {
    expect(isAllowedPopupTarget('https://accounts.google.com/o/oauth2/auth')).toBe(true)
    expect(isAllowedPopupTarget('https://appleid.apple.com/auth/authorize')).toBe(true)
    expect(isAllowedPopupTarget('https://www.facebook.com/dialog/oauth')).toBe(true)
  })

  it('refuse TikTok lui-meme : aucun flux legitime n a besoin d une popup TikTok', () => {
    expect(isAllowedPopupTarget('https://www.tiktok.com/foo')).toBe(false)
  })

  it('refuse un schema non web', () => {
    expect(isAllowedPopupTarget('itms-apps://apps.apple.com/app/id123')).toBe(false)
  })

  it('refuse un domaine sans rapport', () => {
    expect(isAllowedPopupTarget('https://evil.com')).toBe(false)
  })
})
