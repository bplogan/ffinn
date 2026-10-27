'use client'
import { useEffect, useRef } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation } from '@tanstack/react-query'
import { usersApi } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Badge from '@/components/ui/Badge'
import { Save, Camera, User } from 'lucide-react'
import toast from 'react-hot-toast'
import Link from 'next/link'

interface ProfileForm { firstName: string; lastName: string; email: string; phoneNumber?: string }

export default function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const { register, handleSubmit, reset, formState: { errors, isDirty } } = useForm<ProfileForm>()

  useEffect(() => {
    if (user) reset({ firstName: user.firstName, lastName: user.lastName, email: user.email, phoneNumber: user.phoneNumber })
  }, [user, reset])

  const updateMut = useMutation({
    mutationFn: (d: ProfileForm) => usersApi.updateMe({
      firstName: d.firstName,
      lastName: d.lastName,
      phoneNumber: d.phoneNumber,
    }),
    onSuccess: () => { toast.success('Profile updated'); refreshUser() },
    onError: () => toast.error('Update failed'),
  })

  const avatarMut = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData(); fd.append('file', file)
      return usersApi.uploadMyAvatar(fd)
    },
    onSuccess: () => { toast.success('Avatar updated'); refreshUser() },
    onError: () => toast.error('Avatar upload failed'),
  })

  return (
    <div className="space-y-6 max-w-2xl">
      <PageHeader title="My Profile" subtitle="Manage your personal information" />

      {/* Avatar */}
      <div className="card p-6 flex items-center gap-6">
        <div className="relative">
          <div className="w-20 h-20 rounded-full bg-brand-100 dark:bg-brand-900/30 flex items-center justify-center overflow-hidden">
            {user?.profilePictureUrl
              ? <img src={user.profilePictureUrl} alt="Avatar" className="w-full h-full object-cover" />
              : <User size={32} className="text-brand-500" />}
          </div>
          <button onClick={() => fileInputRef.current?.click()}
            className="absolute bottom-0 right-0 p-1.5 rounded-full bg-brand-500 text-white hover:bg-brand-600 transition">
            <Camera size={12} />
          </button>
          <input ref={fileInputRef} type="file" accept="image/*" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) avatarMut.mutate(f) }} />
        </div>
        <div>
          <p className="font-semibold text-gray-900 dark:text-white">{user?.fullName ?? user?.email}</p>
          <p className="text-sm text-gray-500">{user?.email}</p>
          <div className="flex items-center gap-2 mt-1">
            {user?.roles?.map(r => <Badge key={r} variant="info">{r}</Badge>)}
          </div>
        </div>
      </div>

      {/* Profile form */}
      <div className="card p-6">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">Personal information</h2>
        <form onSubmit={handleSubmit(d => updateMut.mutate(d))} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Input {...register('firstName', { required: 'First name required' })} label="First name" error={errors.firstName?.message} />
            <Input {...register('lastName', { required: 'Last name required' })} label="Last name" error={errors.lastName?.message} />
          </div>
          <Input value={user?.email ?? ''} type="email" label="Email address" disabled readOnly />
          <Input {...register('phoneNumber')} label="Phone number" placeholder="+1 (555) 000-0000" />
          <Button type="submit" icon={<Save size={15} />} loading={updateMut.isPending} disabled={!isDirty}>
            Save changes
          </Button>
        </form>
      </div>

      {/* Quick links */}
      <div className="card p-4 flex flex-col sm:flex-row gap-3">
        <Link href="/app/profile/change-password" className="btn-secondary text-sm flex-1 text-center">Change password</Link>
        <Link href="/app/profile/security" className="btn-secondary text-sm flex-1 text-center">Security settings (2FA)</Link>
      </div>
    </div>
  )
}
