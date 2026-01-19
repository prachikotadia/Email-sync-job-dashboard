/**
 * Frontend Component Tests for Resumes Page
 * Tests resume upload, list, rename, delete, and set-default functionality
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import Resumes from '../Resumes'
import { resumeService } from '../../services/resumeService'
import { useAuth } from '../../context/AuthContext'

// Mock dependencies
vi.mock('../../services/resumeService', () => ({
  resumeService: {
    listResumes: vi.fn(),
    uploadResume: vi.fn(),
    deleteResume: vi.fn(),
    setDefaultResume: vi.fn(),
    renameResume: vi.fn(),
  },
}))
vi.mock('../../context/AuthContext', () => ({
  useAuth: vi.fn(),
}))
vi.mock('../../utils/toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  useLocation: () => ({ pathname: '/resumes' }),
}))

describe('Resumes Page', () => {
  const mockUser = {
    email: 'test@example.com',
  }

  const mockResumes = [
    {
      id: 'resume-1',
      file_name: 'Frontend Resume',
      file_type: 'pdf',
      file_size_kb: 150,
      is_default: true,
      usage_count: 2,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'resume-2',
      file_name: 'Backend Resume',
      file_type: 'docx',
      file_size_kb: 200,
      is_default: false,
      usage_count: 0,
      created_at: '2024-01-02T00:00:00Z',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    useAuth.mockReturnValue({
      user: mockUser,
      isGuest: false,
    })
    resumeService.listResumes.mockResolvedValue(mockResumes)
  })

  it('renders resume list on load', async () => {
    render(<Resumes />)

    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    expect(screen.getByText(/Frontend Resume/i)).toBeInTheDocument()
    expect(screen.getByText(/Backend Resume/i)).toBeInTheDocument()
  })

  it('shows empty state when no resumes', async () => {
    resumeService.listResumes.mockResolvedValue([])

    render(<Resumes />)

    await waitFor(() => {
      expect(screen.getByText(/No resumes uploaded yet/i)).toBeInTheDocument()
    })
  })

  it('handles file upload', async () => {
    const mockFile = new File(['pdf content'], 'resume.pdf', { type: 'application/pdf' })
    resumeService.uploadResume.mockResolvedValue({
      id: 'resume-3',
      file_name: 'resume',
      file_type: 'pdf',
      file_size_kb: 100,
      is_default: false,
    })

    render(<Resumes />)

    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    // Find the file input by its id
    const fileInput = document.getElementById('resume-upload')
    expect(fileInput).toBeInTheDocument()

    // Mock the files property directly
    Object.defineProperty(fileInput, 'files', {
      value: [mockFile],
      writable: false,
      configurable: true,
    })

    fireEvent.change(fileInput)

    await waitFor(() => {
      expect(resumeService.uploadResume).toHaveBeenCalled()
    }, { timeout: 3000 })

    // After upload, listResumes should be called again
    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalledTimes(2) // Initial load + after upload
    }, { timeout: 3000 })
  })

  it('rejects invalid file types', async () => {
    const mockFile = new File(['content'], 'resume.txt', { type: 'text/plain' })

    render(<Resumes />)

    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    const fileInput = screen.getByLabelText(/upload new resume/i)
    Object.defineProperty(fileInput, 'files', {
      value: [mockFile],
      writable: false,
    })

    fireEvent.change(fileInput)

    await waitFor(() => {
      expect(resumeService.uploadResume).not.toHaveBeenCalled()
    })
  })

  it('handles resume deletion', async () => {
    resumeService.deleteResume.mockResolvedValue(true)
    window.confirm = vi.fn(() => true)

    render(<Resumes />)

    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    const deleteButtons = screen.getAllByText(/Delete/i)
    fireEvent.click(deleteButtons[0])

    await waitFor(() => {
      expect(resumeService.deleteResume).toHaveBeenCalledWith('resume-1')
      expect(resumeService.listResumes).toHaveBeenCalledTimes(2) // Reload after delete
    })
  })

  it('handles set default resume', async () => {
    resumeService.setDefaultResume.mockResolvedValue({
      ...mockResumes[1],
      is_default: true,
    })

    render(<Resumes />)

    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    const setDefaultButtons = screen.getAllByText(/Set Default/i)
    fireEvent.click(setDefaultButtons[0])

    await waitFor(() => {
      expect(resumeService.setDefaultResume).toHaveBeenCalledWith('resume-2')
      expect(resumeService.listResumes).toHaveBeenCalledTimes(2) // Reload after set default
    })
  })

  it('handles resume rename', async () => {
    resumeService.renameResume.mockResolvedValue({
      ...mockResumes[0],
      file_name: 'Updated Name',
    })

    render(<Resumes />)

    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    const renameButtons = screen.getAllByText(/Rename/i)
    fireEvent.click(renameButtons[0])

    // Wait for modal to appear
    await waitFor(() => {
      const input = screen.getByPlaceholderText(/Enter resume name/i)
      expect(input).toBeInTheDocument()
    })

    const input = screen.getByPlaceholderText(/Enter resume name/i)
    fireEvent.change(input, { target: { value: 'Updated Name' } })

    const saveButton = screen.getByText(/Save/i)
    fireEvent.click(saveButton)

    await waitFor(() => {
      expect(resumeService.renameResume).toHaveBeenCalledWith('resume-1', 'Updated Name')
      expect(resumeService.listResumes).toHaveBeenCalledTimes(2) // Reload after rename
    })
  })

  it('shows usage count for resumes', async () => {
    render(<Resumes />)

    await waitFor(() => {
      expect(resumeService.listResumes).toHaveBeenCalled()
    })

    expect(screen.getByText(/2 application/i)).toBeInTheDocument()
  })

  it('disables upload in guest mode', () => {
    useAuth.mockReturnValue({
      user: null,
      isGuest: true,
    })

    render(<Resumes />)

    const fileInput = screen.getByLabelText(/upload new resume/i)
    expect(fileInput).toBeDisabled()
  })
})
