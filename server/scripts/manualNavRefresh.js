import { refreshAllTracked } from '../services/navService.js'

refreshAllTracked()
  .then((p) => {
    console.log('Done. lastSyncedAt:', p.lastSyncedAt, 'ok:', p.lastRefreshOk)
    process.exit(0)
  })
  .catch((e) => {
    console.error(e)
    process.exit(1)
  })
