import {
  IconGrid,
  IconBriefcase,
  IconPie,
  IconFile,
  IconSpark,
} from '../ui/icons'

export const NAV_IDS = {
  dashboard: 'dashboard',
  holdings: 'holdings',
  explorer: 'explorer',
  statements: 'statements',
  assistant: 'assistant',
}

export const SIDEBAR_ITEMS = [
  { id: NAV_IDS.dashboard, Icon: IconGrid, label: 'Dashboard' },
  { id: NAV_IDS.holdings, Icon: IconBriefcase, label: 'My holdings' },
  { id: NAV_IDS.explorer, Icon: IconPie, label: 'Fund explorer' },
  { id: NAV_IDS.statements, Icon: IconFile, label: 'Statements' },
  { id: NAV_IDS.assistant, Icon: IconSpark, label: 'Fund assistant', accent: true },
]
