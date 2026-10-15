import '@testing-library/jest-dom/vitest'
import { configure } from '@testing-library/react'

// Whole-suite runs load the CPU; the default 1 s findBy/waitFor timeout made tests flaky.
configure({ asyncUtilTimeout: 5000 })
