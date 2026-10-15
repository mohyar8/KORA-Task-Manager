import type { ReactNode } from 'react'
import { Languages } from 'lucide-react'
import { useI18n } from '@/shared/i18n/i18n'
import lockup from '@/shared/brand/kora-lockup-white.png'
import pattern from '@/shared/brand/pattern-9.svg'
import styles from './AuthLayout.module.css'

/** Standalone page for sign-in and the forced password change: an animated brand panel beside a clean form card. */
export function AuthLayout({ children }: { children: ReactNode }) {
  const { t, locale, setLocale } = useI18n()
  return (
    <div className={styles.page}>
      <aside className={styles.art} aria-hidden="true">
        <span className={`${styles.blob} ${styles.blobA}`} />
        <span className={`${styles.blob} ${styles.blobB}`} />
        <span className={`${styles.blob} ${styles.blobC}`} />
        <img className={styles.pattern} src={pattern} alt="" />
        <img className={styles.lockup} src={lockup} alt="" />
        <p className={styles.tagline}>{t('app.tagline')}</p>
      </aside>
      <main className={styles.main}>
        <div className={styles.tools}>
          <button type="button" className={styles.lang} onClick={() => setLocale(locale === 'ar' ? 'en' : 'ar')} aria-label={t('common.languageLabel')}>
            <Languages size={18} aria-hidden="true" /> {t('common.language')}
          </button>
        </div>
        <div className={styles.formColumn}>
          <div className={styles.mobileBrand}><img src={lockup} alt={t('app.name')} /></div>
          <div className={styles.card}>{children}</div>
        </div>
      </main>
    </div>
  )
}
