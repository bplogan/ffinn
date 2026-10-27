'use client'
import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'
import PageHeader from '@/components/ui/PageHeader'
import Badge from '@/components/ui/Badge'
import { Select } from '@/components/ui/Input'
import { Sun, Moon, Monitor } from 'lucide-react'
import toast from 'react-hot-toast'

const themes = [
  { value: 'light', label: 'Light', icon: <Sun size={18} /> },
  { value: 'dark', label: 'Dark', icon: <Moon size={18} /> },
  { value: 'system', label: 'System', icon: <Monitor size={18} /> },
]

const languages = ['English', 'Spanish', 'French', 'German', 'Portuguese', 'Japanese', 'Chinese']
const timezones = Intl.supportedValuesOf ? Intl.supportedValuesOf('timeZone').slice(0, 50) : ['UTC', 'America/New_York', 'Europe/London']

export default function AppSettingsPage() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  const [language, setLanguage] = useState('English')
  const [timezone, setTimezone] = useState('UTC')
  const [emailNotifications, setEmailNotifications] = useState(true)
  const [browserNotifications, setBrowserNotifications] = useState(false)

  useEffect(() => {
    setMounted(true)
    const saved = localStorage.getItem('appSettings')
    if (saved) { try { const s = JSON.parse(saved); setLanguage(s.language ?? 'English'); setTimezone(s.timezone ?? 'UTC'); setEmailNotifications(s.emailNotifications ?? true); setBrowserNotifications(s.browserNotifications ?? false) } catch {} }
  }, [])

  const save = () => {
    localStorage.setItem('appSettings', JSON.stringify({ language, timezone, emailNotifications, browserNotifications }))
    toast.success('Settings saved')
  }

  return (
    <div className="space-y-6 max-w-xl">
      <PageHeader title="Settings" subtitle="Customize your experience" />

      {/* Theme */}
      <div className="card p-6">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Appearance</h2>
        {mounted && (
          <div className="grid grid-cols-3 gap-3">
            {themes.map(t => (
              <button key={t.value} onClick={() => setTheme(t.value)}
                className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-colors ${theme === t.value ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20 text-brand-600 dark:text-brand-400' : 'border-gray-200 dark:border-gray-700 text-gray-500 hover:border-gray-300 dark:hover:border-gray-600'}`}>
                {t.icon}
                <span className="text-xs font-medium">{t.label}</span>
                {theme === t.value && <Badge variant="info" className="text-xs">Active</Badge>}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Localization */}
      <div className="card p-6 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Localization</h2>
        <div>
          <label className="label">Language</label>
          <select value={language} onChange={e => setLanguage(e.target.value)} className="input-field">
            {languages.map(l => <option key={l}>{l}</option>)}
          </select>
        </div>
        <div>
          <label className="label">Timezone</label>
          <select value={timezone} onChange={e => setTimezone(e.target.value)} className="input-field">
            {timezones.map(z => <option key={z}>{z}</option>)}
          </select>
        </div>
      </div>

      {/* Notifications */}
      <div className="card p-6 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Notifications</h2>
        {[
          { id: 'email', label: 'Email notifications', desc: 'Receive updates and alerts via email', value: emailNotifications, onChange: setEmailNotifications },
          { id: 'browser', label: 'Browser notifications', desc: 'Push notifications in your browser', value: browserNotifications, onChange: setBrowserNotifications },
        ].map(n => (
          <div key={n.id} className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">{n.label}</p>
              <p className="text-xs text-gray-500">{n.desc}</p>
            </div>
            <button onClick={() => n.onChange(!n.value)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${n.value ? 'bg-brand-500' : 'bg-gray-300 dark:bg-gray-600'}`}>
              <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${n.value ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>
        ))}
      </div>

      <button onClick={save} className="btn-primary">Save settings</button>
    </div>
  )
}
