import cron from 'node-cron'
import { refreshAllTracked } from '../services/navService.js'

let started = false

export function startNavRefreshJob() {
  if (started) return
  started = true
  // Daily 08:00 Asia/Kolkata
  cron.schedule(
    '0 8 * * *',
    async () => {
      try {
        await refreshAllTracked()
        console.info('[navRefreshJob] Daily NAV refresh completed')
      } catch (e) {
        console.error('[navRefreshJob]', e)
      }
    },
    { timezone: 'Asia/Kolkata' }
  )
  console.info('[navRefreshJob] Scheduled daily refresh at 08:00 Asia/Kolkata')
}
