/**
 * Frontend Component Tests for ResumeSelector
 * Tests resume selection, upload, and linking functionality
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ResumeSelector from '../ResumeSelector'
import { resumeService } from '../../services/resumeService'

// Mock resumeService
vi.mock('../../services/resumeService', () => ({
  resumeService: {
    listResumes: vi.fn(),
    linkResumeToApplication: vi.fn(),
    uploadResume: vi.fn(),
    getDefaultResume: vi.fn(),
  },
}))

// Mock toast
vi.mock('../../utils/toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

describe('ResumeSelector', () => {
  const mockResumes = [
    {
      id: 'resume-1',
      file_name: 'Frontend Resume',
      file_type: 'pdf',
      file_size_kb: 150,
      is_default: true,
    },
    {
      id: 'resume-2',
      file_name: 'Backend Resume',
      file_type: 'docx',
      file_size_kb: 200,
      is_default: false,
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    resumeService.listResumes.mockResolvedValue(mockResumes)
    resumeService.getDefaultResume.mockResolvedValue({ resume: mockResumes[0] })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders with default resume selected', async () => {
    const onResumeChange = vi.fn()
    
    render(
      <ResumeSelector
        applicationId="app-1"
        currentResumeId={null}
        onResumeChange={onResumeChange}
      />
    )

    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    // Should show default resume
    expect(screen.getByText(/Frontend Resume/i)).toBeInTheDocument()
  })

  it('shows current resume when provided', async () => {
    render(
      <ResumeSelector
        applicationId="app-1"
        currentResumeId="resume-2"
        onResumeChange={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(screen.getByText(/Backend Resume/i)).toBeInTheDocument()
    })
  })

  it('opens dropdown on click', async () => {
    render(
      <ResumeSelector
        applicationId="app-1"
        currentResumeId={null}
        onResumeChange={vi.fn()}
      />
    )

    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    const button = screen.getByRole('button')
    fireEvent.click(button)

    // Should show dropdown with all resumes
    expect(screen.getByText(/Backend Resume/i)).toBeInTheDocument()
  })

  it('calls onResumeChange when resume is selected', async () => {
    const onResumeChange = vi.fn()
    resumeService.linkResumeToApplication.mockResolvedValue({ message: 'Success' })

    render(
      <ResumeSelector
        applicationId="app-1"
        currentResumeId="resume-1"
        onResumeChange={onResumeChange}
      />
    )

    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    // Open dropdown
    const button = screen.getByRole('button')
    fireEvent.click(button)

    // Select different resume
    await waitFor(() => {
      const backendResume = screen.getByText(/Backend Resume/i)
      fireEvent.click(backendResume.closest('button'))
    })

    await waitFor(() => {
      expect(resumeService.linkResumeToApplication).toHaveBeenCalledWith('app-1', 'resume-2')
      expect(onResumeChange).toHaveBeenCalledWith('resume-2')
    })
  })

  it('shows empty state when no resumes exist', async () => {
    resumeService.listResumes.mockResolvedValue([])
    resumeService.getDefaultResume.mockResolvedValue({ resume: null })

    render(
      <ResumeSelector
        applicationId="app-1"
        currentResumeId={null}
        onResumeChange={vi.fn()}
      />
    )

    // Wait for loading to complete
    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    // Open the dropdown to see the empty state
    const button = screen.getByRole('button')
    fireEvent.click(button)

    // Wait for the dropdown to open and show empty state
    await waitFor(() => {
      expect(screen.getByText(/No resumes uploaded/i)).toBeInTheDocument()
    }, { timeout: 2000 })
  })

  it('disables when disabled prop is true', () => {
    render(
      <ResumeSelector
        applicationId="app-1"
        currentResumeId={null}
        onResumeChange={vi.fn()}
        disabled={true}
      />
    )

    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
  })
})
