import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { en } from './messages.en'
import { ar } from './messages.ar'
import { I18nProvider, useI18n } from './i18n'
import { translate } from './translate'

describe('i18n', () => {
  it('Arabic provides exactly the English key set', () => {
    expect(Object.keys(ar).sort()).toEqual(Object.keys(en).sort())
  })

  it('looks up per locale', () => {
    expect(translate('en', 'app.name')).toBe('KORA')
    expect(translate('ar', 'app.name')).toBe('كورة')
  })

  it('defaults to Arabic RTL and flips the document on switch', async () => {
    function Probe() {
      const { locale, setLocale, t } = useI18n()
      return (
        <button onClick={() => setLocale(locale === 'ar' ? 'en' : 'ar')}>{t('app.name')}</button>
      )
    }
    render(
      <I18nProvider>
        <Probe />
      </I18nProvider>,
    )
    expect(document.documentElement.dir).toBe('rtl')
    expect(document.documentElement.lang).toBe('ar')
    await userEvent.click(screen.getByRole('button'))
    expect(document.documentElement.dir).toBe('ltr')
    expect(screen.getByRole('button')).toHaveTextContent('KORA')
  })
})
