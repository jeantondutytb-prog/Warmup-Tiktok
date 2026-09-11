import { describe, expect, it } from 'vitest'
import { PAUSE_VIDEOS_SCRIPT } from '../src/core/pause-videos-script'

// Garde-fou automatise pour la regle la plus importante du projet : le seul
// script injecte dans une vue de compte met en pause la lecture video locale
// et ne simule jamais une entree utilisateur.
describe('PAUSE_VIDEOS_SCRIPT', () => {
  it('does not send synthetic input events', () => {
    expect(PAUSE_VIDEOS_SCRIPT).not.toContain('sendInputEvent')
  })

  it('does not simulate a click', () => {
    expect(PAUSE_VIDEOS_SCRIPT).not.toContain('.click(')
  })

  it('does not dispatch synthetic DOM events', () => {
    expect(PAUSE_VIDEOS_SCRIPT).not.toContain('dispatchEvent')
  })

  it('does not construct keyboard or mouse events', () => {
    expect(PAUSE_VIDEOS_SCRIPT).not.toMatch(/KeyboardEvent|MouseEvent/)
  })

  it('only pauses video elements', () => {
    expect(PAUSE_VIDEOS_SCRIPT).toContain('querySelectorAll("video")')
    expect(PAUSE_VIDEOS_SCRIPT).toContain('.pause()')
  })
})
