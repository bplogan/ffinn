'use client'

import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { get, post, put, del, postForm } from '@/lib/api'
import PageHeader from '@/components/ui/PageHeader'
import Button from '@/components/ui/Button'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import Modal from '@/components/ui/Modal'
import Input from '@/components/ui/Input'
import Badge from '@/components/ui/Badge'
import toast from 'react-hot-toast'
import { Plus, Edit3, Trash2, UploadCloud } from 'lucide-react'

// Inline interfaces for this feature
interface FileAttachment { id: string; fileName?: string | null; url?: string | null; label?: string | null }
interface Project { id: string; title: string; description?: string | null; status: string; createdAt: string; updatedAt: string; attachments: FileAttachment[] }
interface ProjectCreate { title: string; description?: string; status?: string; attachmentIds?: string[] }
interface ProjectUpdate { title?: string; description?: string; status?: string; attachmentIds?: string[] }

export default function ProjectsPage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery<Project[]>({
    queryKey: ['projects'],
    queryFn: () => get<Project[]>('/api/projects'),
  })

  const createMutation = useMutation({
    mutationFn: (payload: ProjectCreate) => post<Project>('/api/projects', payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Project created') }
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: ProjectUpdate }) => put<Project>(`/api/projects/${id}`, payload),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Project updated') }
  })
  const deleteMutation = useMutation({
    mutationFn: (id: string) => del(`/api/projects/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Project deleted') }
  })
  const attachMutation = useMutation({
    mutationFn: ({ projectId, fileId }: { projectId: string; fileId: string }) => post(`/api/projects/${projectId}/attachments/${fileId}`, {}),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Attachment added') }
  })
  const detachMutation = useMutation({
    mutationFn: ({ projectId, fileId }: { projectId: string; fileId: string }) => del(`/api/projects/${projectId}/attachments/${fileId}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['projects'] }); toast.success('Attachment removed') }
  })

  // UI state
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Project | null>(null)
  const [formTitle, setFormTitle] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formStatus, setFormStatus] = useState('active')
  const [selectedProjectForDelete, setSelectedProjectForDelete] = useState<Project | null>(null)
  const [uploading, setUploading] = useState(false)

  const projects = data ?? []

  function openCreate() {
    setEditing(null)
    setFormTitle('')
    setFormDescription('')
    setFormStatus('active')
    setShowModal(true)
  }

  function openEdit(p: Project) {
    setEditing(p)
    setFormTitle(p.title)
    setFormDescription(p.description ?? '')
    setFormStatus(p.status)
    setShowModal(true)
  }

  async function submitForm(e?: React.FormEvent) {
    e?.preventDefault()
    if (!formTitle || formTitle.trim().length === 0) {
      toast.error('Title is required')
      return
    }
    try {
      if (editing) {
        await updateMutation.mutateAsync({ id: editing.id, payload: { title: formTitle, description: formDescription, status: formStatus } })
      } else {
        await createMutation.mutateAsync({ title: formTitle, description: formDescription, status: formStatus })
      }
      setShowModal(false)
    } catch (err) {
      toast.error('Failed to save project')
    }
  }

  async function confirmDelete() {
    if (!selectedProjectForDelete) return
    try {
      await deleteMutation.mutateAsync(selectedProjectForDelete.id)
      setSelectedProjectForDelete(null)
    } catch (err) {
      toast.error('Failed to delete project')
    }
  }

  // file upload handler — relies on existing files API. We use the shared post helper which the app provides.
  async function handleFileUpload(projectId: string, file: File) {
    try {
      setUploading(true)
      const form = new FormData()
      form.append('file', file)
      // The app's /api/files endpoint typically handles uploads — using the post helper per conventions
      const uploaded = await postForm<{ id: string; fileName: string; url?: string }>('/api/files/upload', form)
      if (uploaded?.id) {
        await attachMutation.mutateAsync({ projectId, fileId: uploaded.id })
      }
    } catch (err) {
      toast.error('Upload failed')
    } finally {
      setUploading(false)
    }
  }

  function ProjectCard({ project }: { project: Project }) {
    return (
      <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4 flex flex-col">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{project.title}</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">{new Date(project.createdAt).toLocaleString()}</p>
          </div>
          <div className="flex items-center gap-2">
            <Badge className="bg-gray-100 dark:bg-gray-800 text-gray-800 dark:text-white">{project.status}</Badge>
            <button onClick={() => openEdit(project)} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300"><Edit3 size={14} /></button>
            <button onClick={() => setSelectedProjectForDelete(project)} className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 text-red-600 dark:text-red-400"><Trash2 size={14} /></button>
          </div>
        </div>

        <p className="mt-3 text-sm text-gray-700 dark:text-gray-300 flex-1">{project.description}</p>

        <div className="mt-4 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="file" className="hidden" onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) handleFileUpload(project.id, f)
              }} />
              <span className="inline-flex items-center gap-2 px-3 py-1 rounded text-sm bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-300">
                <UploadCloud size={14} /> Attach
              </span>
            </label>
          </div>
          <div className="flex items-center gap-2">
            {project.attachments?.slice(0, 3).map(a => (
              <a key={a.id} href={a.url ?? '#'} className="text-xs text-gray-600 dark:text-gray-300 hover:underline" target="_blank" rel="noreferrer">{a.fileName ?? 'file'}</a>
            ))}
            {project.attachments && project.attachments.length > 3 && (
              <span className="text-xs text-gray-500 dark:text-gray-400">+{project.attachments.length - 3}</span>
            )}
          </div>
        </div>
      </div>
    )
  }

  const grid = useMemo(() => (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {projects.map(p => <ProjectCard key={p.id} project={p} />)}
    </div>
  ), [projects])

  return (
    <div className="p-6">
      <PageHeader title="Projects" subtitle="Manage tenant projects and attachments." />

      <div className="mt-6 flex items-center justify-between">
        <div />
        <div>
          <Button onClick={openCreate} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-900 dark:text-white">
            <Plus size={14} />
            <span className="ml-2">New Project</span>
          </Button>
        </div>
      </div>

      <div className="mt-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <LoadingSpinner />
          </div>
        ) : (
          grid
        )}
      </div>

      <Modal open={showModal} onClose={() => setShowModal(false)} title={editing ? 'Edit Project' : 'New Project'}>
        <form onSubmit={submitForm} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Title</label>
            <Input value={formTitle} onChange={(e) => setFormTitle((e.target as HTMLInputElement).value)} required className="mt-1 w-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-900 dark:text-white" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Description</label>
            <textarea value={formDescription} onChange={(e) => setFormDescription(e.target.value)} className="mt-1 w-full min-h-[100px] p-2 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded text-gray-900 dark:text-white" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-200">Status</label>
            <select value={formStatus} onChange={(e) => setFormStatus(e.target.value)} className="mt-1 w-full bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded p-2 text-gray-900 dark:text-white">
              <option value="draft">Draft</option>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="archived">Archived</option>
            </select>
          </div>

          <div className="flex items-center justify-end gap-2">
            <Button type="button" onClick={() => setShowModal(false)} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300">Cancel</Button>
            <Button type="submit" className="bg-brand-600 dark:bg-brand-500 text-white">{editing ? 'Save changes' : 'Create project'}</Button>
          </div>
        </form>
      </Modal>

      <ConfirmDialog
        open={!!selectedProjectForDelete}
        title="Delete project"
        message={`Are you sure you want to delete "${selectedProjectForDelete?.title ?? ''}"? This action cannot be undone.`}
        onConfirm={confirmDelete}
        onClose={() => setSelectedProjectForDelete(null)}
      />
    </div>
  )
}
